# LlamaIndex 对 OpenRouter Embedding 与 Reranker 支持情况调研

调研日期：2026-05-10

## 结论

截至当前公开资料，LlamaIndex 对 OpenRouter 的支持主要集中在 **LLM provider**，并不完整覆盖 OpenRouter 的 embedding 与 reranker 能力。

| 能力 | LlamaIndex 现状 | 可行性 |
| --- | --- | --- |
| OpenRouter 作为 LLM provider | 原生支持，包为 `llama-index-llms-openrouter`，类为 `OpenRouter` | 官方支持 |
| OpenRouter embedding 模型 | 未发现专门的 `OpenRouterEmbedding` 或 `llama-index-embeddings-openrouter` 包 | 可通过 `OpenAILikeEmbedding` 间接调用 |
| OpenRouter reranker 模型 | 未发现专门的 `OpenRouterRerank` 或 `llama-index-postprocessor-openrouter` 包 | 需要自定义 postprocessor，或用 `LLMRerank` 变通 |

简要判断：

- Embedding：支持间接接入，不是 LlamaIndex 原生 OpenRouter embedding provider。
- Reranker：未看到 LlamaIndex 原生支持 OpenRouter `/rerank` endpoint，需要自定义封装。

## OpenRouter 侧能力

OpenRouter 当前已经提供 embedding 与 rerank API：

- Embeddings endpoint：`POST https://openrouter.ai/api/v1/embeddings`
- Rerank endpoint：`POST https://openrouter.ai/api/v1/rerank`

OpenRouter 也提供对应模型集合页面：

- Embedding 模型示例：`openai/text-embedding-3-small`、`openai/text-embedding-3-large`、`qwen/qwen3-embedding-8b`、`qwen/qwen3-embedding-4b`、`baai/bge-m3`、`google/gemini-embedding-001`、`perplexity/pplx-embed-v1-0.6b` 等。
- Rerank 模型示例：`cohere/rerank-4-pro`、`cohere/rerank-4-fast`、`cohere/rerank-v3.5`。

## LlamaIndex 侧能力

### LLM

LlamaIndex 官方已有 OpenRouter LLM 集成：

```bash
pip install llama-index-llms-openrouter
```

示例：

```python
from llama_index.llms.openrouter import OpenRouter

llm = OpenRouter(
    api_key="<OPENROUTER_API_KEY>",
    model="mistralai/mixtral-8x7b-instruct",
    max_tokens=256,
    context_window=4096,
)
```

该集成基于 `OpenAILike`，用于 chat/completion 场景。PyPI 显示 `llama-index-llms-openrouter` 最新版本为 `0.5.0`，发布时间为 2026-03-12。

### Embedding

未发现 LlamaIndex 官方专门的 OpenRouter embedding 集成包，例如：

- `llama-index-embeddings-openrouter`
- `OpenRouterEmbedding`

但 LlamaIndex 有 `OpenAILikeEmbedding`，支持配置 `api_base`，可以指向 OpenRouter 的 OpenAI-compatible embeddings endpoint。

可行示例：

```python
from llama_index.embeddings.openai_like import OpenAILikeEmbedding

embed_model = OpenAILikeEmbedding(
    model_name="openai/text-embedding-3-small",
    api_base="https://openrouter.ai/api/v1",
    api_key="<OPENROUTER_API_KEY>",
)
```

如果需要传 OpenRouter provider routing 参数，可能需要通过 OpenAI SDK 的 `extra_body` 机制传入，具体取决于当前 LlamaIndex 与 OpenAI SDK 版本，建议实测：

```python
from llama_index.embeddings.openai_like import OpenAILikeEmbedding

embed_model = OpenAILikeEmbedding(
    model_name="qwen/qwen3-embedding-8b",
    api_base="https://openrouter.ai/api/v1",
    api_key="<OPENROUTER_API_KEY>",
    additional_kwargs={
        "extra_body": {
            "provider": {
                "allow_fallbacks": True,
            }
        }
    },
)
```

注意：OpenRouter embeddings API 文档支持 `provider`、`dimensions`、`encoding_format`、`input_type` 等参数；LlamaIndex 的 `OpenAILikeEmbedding` 是否能完整透传这些参数，需要以实际版本行为为准。

### Reranker

未发现 LlamaIndex 官方专门的 OpenRouter rerank 集成，例如：

- `llama-index-postprocessor-openrouter`
- `OpenRouterRerank`

LlamaIndex 目前有多种 rerank postprocessor，例如：

- `CohereRerank`
- `JinaAIRerank`
- `NvidiaRerank`
- `SiliconflowRerank`
- `LLMRerank`
- `OpenVINORerank`
- `SentenceTransformerRerank`

其中 `LLMRerank` 可以配合 OpenRouter LLM 做生成式重排，但这不是调用 OpenRouter 的 `/api/v1/rerank` reranker endpoint。

OpenRouter `/rerank` 的请求形态大致为：

```python
import requests

url = "https://openrouter.ai/api/v1/rerank"

payload = {
    "documents": [
        "Paris is the capital of France.",
        "Berlin is the capital of Germany.",
    ],
    "model": "cohere/rerank-v3.5",
    "query": "What is the capital of France?",
    "top_n": 3,
}

headers = {
    "Authorization": "Bearer <OPENROUTER_API_KEY>",
    "Content-Type": "application/json",
}

response = requests.post(url, json=payload, headers=headers)
print(response.json())
```

如果要在 LlamaIndex 查询链路中使用 OpenRouter reranker，建议实现一个自定义 `BaseNodePostprocessor`，内部调用 `https://openrouter.ai/api/v1/rerank`，再根据返回的 `index` 与 `relevance_score` 重排 `NodeWithScore`。

## 推荐接入策略

1. 如果只需要 LLM：直接使用 `llama-index-llms-openrouter`。
2. 如果需要 embedding：优先用 `OpenAILikeEmbedding` 指向 `https://openrouter.ai/api/v1`，并选用 OpenRouter embedding 模型。
3. 如果需要 OpenRouter reranker：实现自定义 node postprocessor 调 OpenRouter `/rerank`；不要误以为 `CohereRerank` 会自动走 OpenRouter。
4. 如果只是想快速提升检索结果，可临时使用 LlamaIndex 的 `LLMRerank` 配合 OpenRouter LLM，但成本、延迟和排序稳定性通常不如专门 rerank endpoint。

## 来源

- [LlamaIndex with OpenRouter](https://openrouter.ai/works-with-openrouter/llamaindex)
- [LlamaIndex OpenRouter LLM API Reference](https://docs.llamaindex.ai/en/stable/api_reference/llms/openrouter/)
- [llama-index-llms-openrouter PyPI](https://pypi.org/project/llama-index-llms-openrouter/)
- [LlamaIndex OpenAI-like Embedding API Reference](https://docs.llamaindex.ai/en/stable/api_reference/embeddings/openai_like/)
- [LlamaIndex OpenAI Embedding API Reference](https://docs.llamaindex.ai/en/stable/api_reference/embeddings/openai/)
- [LlamaIndex Cohere Rerank API Reference](https://docs.llamaindex.ai/en/stable/api_reference/postprocessor/cohere_rerank/)
- [OpenRouter Embeddings API](https://openrouter.ai/docs/api/api-reference/embeddings/create-embeddings)
- [OpenRouter Rerank API](https://openrouter.ai/docs/api/api-reference/rerank/create-rerank)
- [OpenRouter Embedding Models](https://openrouter.ai/collections/embedding-models)
- [OpenRouter Rerank Models](https://openrouter.ai/collections/rerank-models)
- [GitHub issue: Support for Choosing OpenRouter Provider in LlamaIndex](https://github.com/run-llama/llama_index/issues/17751)
