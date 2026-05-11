# Python CLI 集成 llama.cpp 作为 Embedding/Reranker 运行时调研

## 结论

对于 Python 编写 CLI 程序的场景，建议把 `llama.cpp` 集成拆成两个层次：

1. Embedding：优先使用 `llama-cpp-python` 做进程内集成，调用简单、无需本地 HTTP 端口，适合 CLI 内部直接生成向量。
2. Reranker：优先使用 `llama-server` 子进程集成，通过 HTTP 调用 `/v1/rerank`、`/reranking` 或 `/v1/reranking`。`llama.cpp` 服务端已经有较稳定的 rerank endpoint，而官方 `llama-cpp-python` 目前没有清晰稳定的高层 `rank/rerank` API。
3. CPU/CUDA 支持主要是安装/构建时能力，运行时再通过参数控制是否 offload 到 GPU。CUDA 版可以用 `n_gpu_layers=0` 跑 CPU，也可以用 `n_gpu_layers=-1` 或 `all` 跑 GPU；CPU-only 版不能临时切到 CUDA。

推荐架构：

- CLI 内部定义统一接口，例如 `Embedder.embed()` 和 `Reranker.rerank()`。
- `LlamaCppPythonEmbedder` 使用 `llama_cpp.Llama(..., embedding=True)`。
- `LlamaServerReranker` 由 CLI 启动 `llama-server` 子进程，监听 `127.0.0.1:<free_port>`，退出时清理进程。
- 如果希望实现更统一，也可以 embedding/reranker 都走 `llama-server`，代价是多一个本地 HTTP 子进程和健康检查逻辑。

## 背景

`llama.cpp` 现在不仅支持文本生成，也支持：

- GGUF embedding 模型。
- GGUF reranker/cross-encoder 模型。
- CPU、CUDA、Metal、ROCm、Vulkan、SYCL 等多种 backend。
- `llama-server` 的 OpenAI-compatible embeddings endpoint。
- `llama-server` 的 reranking endpoint。

在 Python CLI 场景下，主要有两种集成路线：

1. 直接依赖 `llama-cpp-python`，在 Python 进程中加载 GGUF。
2. 随 CLI 启动或连接一个 `llama-server`，通过 HTTP 调用。

两种路线都能支持 CPU 和 CUDA，但使用方式和工程复杂度不同。

## 方案一：`llama-cpp-python` 进程内集成

### 适用场景

适合 embedding：

- CLI 希望直接调用 Python API。
- 不想维护本地 HTTP server 生命周期。
- 每次命令或长驻 CLI 进程内部可以复用模型实例。

不太建议优先用于 reranker：

- 官方文档清晰支持 `create_embedding` 和 `embed`。
- 底层绑定有 `LLAMA_POOLING_TYPE_RANK`，但官方高层 API 未提供明确稳定的 `rank/rerank` 方法。
- 某些 fork 或模型卡展示过 `LlamaEmbedding.rank()`，但这不像官方主包的稳定 API。

### 安装 CPU 版

```bash
pip install llama-cpp-python \
  --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
```

也可以直接：

```bash
pip install llama-cpp-python
```

直接安装可能触发本机源码构建，具体取决于平台、Python 版本和 wheel 可用性。

### 安装 CUDA 版

预编译 CUDA wheel 支持 CUDA 12.1 到 12.5，对应 index 后缀为 `cu121`、`cu122`、`cu123`、`cu124`、`cu125`。

例如 CUDA 12.4：

```bash
pip install llama-cpp-python \
  --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124
```

源码构建 CUDA：

```bash
CMAKE_ARGS="-DGGML_CUDA=on" FORCE_CMAKE=1 \
  pip install --no-cache-dir --force-reinstall llama-cpp-python
```

### Embedding 示例

```python
import llama_cpp
from llama_cpp import Llama


llm = Llama(
    model_path="models/embedding-model.gguf",
    embedding=True,
    pooling_type=llama_cpp.LLAMA_POOLING_TYPE_CLS,
    n_gpu_layers=-1,  # CUDA 全 offload；CPU 用 0
    n_ctx=8192,
    n_batch=512,
)

resp = llm.create_embedding(["hello", "world"])
vectors = [item["embedding"] for item in resp["data"]]
```

运行时可以按配置切换：

```python
n_gpu_layers = -1 if device == "cuda" else 0
```

可以检查当前 build 是否支持 GPU offload：

```python
import llama_cpp

has_gpu_offload = llama_cpp.llama_supports_gpu_offload()
```

注意：`llama_supports_gpu_offload()` 为 false 时，即使传 `n_gpu_layers=-1` 也不能启用 CUDA。

### Pooling 类型

Embedding 模型需要使用模型卡推荐的 pooling 类型。常见选择：

- `LLAMA_POOLING_TYPE_CLS`
- `LLAMA_POOLING_TYPE_MEAN`
- `LLAMA_POOLING_TYPE_LAST`
- `LLAMA_POOLING_TYPE_NONE`

Reranker 模型通常用：

- `LLAMA_POOLING_TYPE_RANK`

普通生成模型通常不能直接可靠地产生 sequence-level embedding。应优先使用专用 embedding GGUF 模型。

## 方案二：`llama-server` 子进程集成

### 适用场景

适合 reranker，也适合想统一 HTTP 运行时的 embedding：

- `llama-server` 已支持 embeddings 和 reranking endpoint。
- Reranker endpoint 是官方服务端能力，不需要自己从底层 binding 拼 cross-encoder 输入和读取分类头输出。
- CLI 可以把 `llama-server` 当作可管理的本地 runtime。

代价：

- 需要管理子进程生命周期。
- 需要选择空闲端口。
- 需要等待 `/health` ready。
- 错误处理要覆盖端口占用、模型加载失败、server crash 等。

### 启动 Embedding Server

CPU：

```bash
llama-server \
  -m models/embedding-model.gguf \
  --embedding \
  --pooling cls \
  --port 8080
```

CUDA：

```bash
llama-server \
  -m models/embedding-model.gguf \
  --embedding \
  --pooling cls \
  --n-gpu-layers all \
  --port 8080
```

调用 OpenAI-compatible embeddings endpoint：

```python
import httpx

resp = httpx.post(
    "http://127.0.0.1:8080/v1/embeddings",
    json={"input": ["hello", "world"], "model": "embedding-model"},
    timeout=60,
)
resp.raise_for_status()
vectors = [item["embedding"] for item in resp.json()["data"]]
```

### 启动 Reranker Server

建议显式传入 embedding/rank pooling/reranking 参数：

```bash
llama-server \
  -m models/reranker-model.gguf \
  --embedding \
  --pooling rank \
  --reranking \
  --port 8081
```

CUDA：

```bash
llama-server \
  -m models/reranker-model.gguf \
  --embedding \
  --pooling rank \
  --reranking \
  --n-gpu-layers all \
  --port 8081
```

有些 `llama.cpp` 文档示例只写：

```bash
llama-server -m model.gguf --reranking
```

但为了避免模型默认 pooling 不符合预期，工程中建议显式写 `--embedding --pooling rank --reranking`。

### Reranker HTTP 调用示例

```python
import httpx


def rerank(base_url: str, query: str, documents: list[str]) -> list[tuple[int, float]]:
    payload = {
        "query": query,
        "documents": documents,
    }
    resp = httpx.post(f"{base_url}/v1/rerank", json=payload, timeout=60)
    resp.raise_for_status()
    results = resp.json()["results"]
    return sorted(
        [(item["index"], item["relevance_score"]) for item in results],
        key=lambda item: item[1],
        reverse=True,
    )
```

建议实现 endpoint fallback：

- `/v1/rerank`
- `/reranking`
- `/v1/reranking`

不同版本或兼容层可能使用不同路径。Lemonade 文档中暴露 `/v1/reranking`，并说明内部转发到 llama.cpp 的 `/v1/rerank`。

### 子进程管理建议

CLI 内部可以这样管理：

- 使用 `socket` 找空闲端口。
- `subprocess.Popen()` 启动 `llama-server`。
- 轮询 `/health`，直到 200 或超时。
- 命令结束时 terminate，超时后 kill。
- 日志写入临时文件或 debug 模式下转发 stderr。

伪代码：

```python
import subprocess
import time
import httpx


proc = subprocess.Popen([
    "llama-server",
    "-m", model_path,
    "--embedding",
    "--pooling", "rank",
    "--reranking",
    "--port", str(port),
])

try:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"http://127.0.0.1:{port}/health", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.5)
    else:
        raise RuntimeError("llama-server did not become ready")

    # call rerank / embedding endpoints here
finally:
    proc.terminate()
```

## CPU/CUDA 运行策略

### 关键点

- CPU/CUDA 能力取决于安装或构建的 `llama.cpp`/`llama-cpp-python`。
- CUDA build 可以通过运行时参数选择 CPU 或 CUDA。
- CPU-only build 不能在运行时临时启用 CUDA。

### `llama-cpp-python`

CPU：

```python
Llama(model_path="model.gguf", n_gpu_layers=0)
```

CUDA 全 offload：

```python
Llama(model_path="model.gguf", n_gpu_layers=-1)
```

部分 offload：

```python
Llama(model_path="model.gguf", n_gpu_layers=20)
```

多 GPU 可结合：

- `split_mode`
- `main_gpu`
- `tensor_split`

### `llama-server`

CPU：

```bash
llama-server -m model.gguf --n-gpu-layers 0
```

CUDA：

```bash
llama-server -m model.gguf --n-gpu-layers all
```

或某些版本中使用大数值：

```bash
llama-server -m model.gguf --n-gpu-layers 99
```

## 模型选择

### Embedding 模型

应选择专用 embedding GGUF 模型。示例类型：

- BGE embedding 系列 GGUF。
- E5 embedding 系列 GGUF。
- Jina embedding GGUF。
- Qwen embedding GGUF。

注意事项：

- 按模型卡设置 pooling 类型。
- 根据上下文长度设置 `n_ctx`。
- 对输出向量是否 normalize 取决于后续检索实现，例如 cosine similarity 通常希望 normalize。

### Reranker 模型

应选择专用 reranker GGUF 模型。示例：

- `gpustack/bge-reranker-v2-m3-GGUF`
- Qwen3 reranker GGUF
- Jina reranker GGUF

Reranker 是 cross-encoder：输入是 query 和 document pair，输出是相关性分数，不是向量。

典型检索流程：

1. 用 embedding 模型召回 top K，例如 top 50。
2. 用 reranker 对这 top K 文档打分。
3. 按 `relevance_score` 降序排序。
4. 取 top N 进入后续上下文或展示。

## Packaging 建议

### 不建议在 `pyproject.toml` 强绑 CUDA wheel

`pyproject.toml` 不能标准化表达用户机器的 CUDA 版本选择，也不能可靠表达 `--extra-index-url` 到不同 CUDA wheel index。

建议：

- 默认 extra 安装 CPU 版。
- 文档提供 `cpu/cu121/cu122/cu123/cu124/cu125` 安装命令。
- 或提供项目自己的安装脚本，例如 `install-runtime --backend cuda --cuda-version cu124`。

### 可选 extras

示例：

```toml
[project.optional-dependencies]
llama = ["llama-cpp-python>=0.3.22"]
server = ["httpx>=0.27"]
```

CUDA wheel 的 index 仍建议放在文档或安装脚本中，而不是假设 pip 能自动选中。

## 推荐实现取舍

### 最小可行方案

- Embedding：`llama-cpp-python`。
- Reranker：启动 `llama-server` 子进程并 HTTP 调用。
- 用户通过 CLI 参数选择：`--device cpu|cuda`。
- CUDA 场景要求用户安装 CUDA 版 runtime。

### 更统一的方案

- Embedding 和 reranker 都走 `llama-server`。
- 好处：所有推理都是 HTTP 调用，Python 侧更薄。
- 坏处：即便只做一次 embedding，也要启动 server，冷启动更重。

### 长驻服务方案

- CLI 支持 `runtime start`、`runtime stop`、`runtime status`。
- 常用命令连接已有 server。
- 适合模型较大或用户频繁执行命令的场景。

## 风险与注意事项

- 冷启动成本高：GGUF 加载可能数秒到数十秒，CLI 短命令体验可能差。
- 版本差异：rerank endpoint 路径在不同版本或兼容层可能不同，建议实现 fallback。
- Pooling 配错会导致向量或 rerank 分数不可用或质量很差。
- CUDA wheel 与本机 CUDA/driver/Python 版本要匹配。
- 模型文件体积大，建议提供本地路径配置和 Hugging Face 下载缓存策略。
- Reranker 不应对全量文档运行，只应对 embedding 召回后的候选集运行。

## 参考来源

- `llama-cpp-python` 文档：<https://llama-cpp-python.readthedocs.io/>
- `llama-cpp-python` PyPI：<https://pypi.org/project/llama-cpp-python/>
- `llama-cpp-python` API Reference：<https://llama-cpp-python.readthedocs.io/en/latest/api-reference/>
- `llama.cpp` README：<https://github.com/ggml-org/llama.cpp/blob/master/README.md>
- `llama.cpp` server README：<https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md>
- Lemonade llama.cpp-specific reranking API：<https://lemonade-server.ai/docs/api/llamacpp/>
- `gpustack/bge-reranker-v2-m3-GGUF`：<https://huggingface.co/gpustack/bge-reranker-v2-m3-GGUF>
- BGE Reranker 文档：<https://bge-model.com/bge/bge_reranker.html>
- BGE Reranking tutorial：<https://bge-model.com/tutorial/5_Reranking/5.1.html>
- Qwen3 Reranker GGUF 示例：<https://huggingface.co/JamePeng2023/Qwen3-Reranker-GGUF>
