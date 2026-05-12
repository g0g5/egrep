# SPEC

## Iteration

- Name: `local-providers-init-progress`
- Scope: provider expansion, rerank disable mode, `init` stage progress UX

## Confirmed Decisions

- `egrep init` uses per-stage progress, not one global progress bar.
- Progress output goes to `stderr` only.
- `reranking.provider == "none"` is persisted as a minimal object.
- Local runtime providers may omit `api_key`; runtime must omit the `Authorization` header when empty.
- `siliconflow` does not prompt for `base_url`; only local runtime providers do.

## Goals

1. Add provider options for local runtime backends: `llamacpp`, `vllm`, `sglang`.
2. Add `siliconflow` as both embedding and reranking provider.
3. Add reranking provider option `none` and make it equivalent to no-rerank behavior.
4. Improve `egrep init` UX with stage progress and current-document visibility.

## Non-Goals

- No new provider-specific HTTP client hierarchy.
- No global 0-100 progress model.
- No new third-party progress-bar dependency.

## External Libraries

- Reuse `requests` for provider HTTP calls.
- Reuse `questionary` for config prompts.
- Reuse `responses` for provider HTTP tests.
- Progress rendering should use stdlib only.

## Provider Model

User-facing config options:

- Embedding providers: `openrouter`, `siliconflow`, `llamacpp`, `vllm`, `sglang`
- Reranking providers: `openrouter`, `siliconflow`, `llamacpp`, `vllm`, `sglang`, `none`

Internal implementation must stay protocol-shaped, not backend-shaped:

- Embeddings: one OpenAI-compatible `/embeddings` request path
- Rerank: one `/rerank` request path plus response normalization for `dict.results` and top-level `list`

## Runtime Behavior

### Embeddings

- `openrouter`, `siliconflow`, `llamacpp`, `vllm`, and `sglang` all use:

```python
data = post_json(
    f"{base_url.rstrip('/')}/embeddings",
    api_key,
    {"model": model, "input": texts},
)
vectors = [item["embedding"] for item in data["data"]]
```

- `llamacpp`, `vllm`, and `sglang` must be configured with a `/v1` base URL.

### Reranking

- `openrouter`, `siliconflow`, `llamacpp`, `vllm`, and `sglang` all use:

```python
response = post_json_any(
    f"{base_url.rstrip('/')}/rerank",
    api_key,
    {
        "model": model,
        "query": query,
        "documents": documents,
        "top_n": top_n,
        "return_documents": False,
    },
)
```

- Response normalization must accept both shapes:

```python
def rerank_results(payload):
    if isinstance(payload, list):
        return payload
    results = payload.get("results")
    if isinstance(results, list):
        return results
    raise ProviderAPIError("provider rerank response missing results")
```

- Score parsing continues to accept both `relevance_score` and `score`.

### No Auth for Local Providers

`requests` usage must omit `Authorization` when `api_key` is empty:

```python
headers = {"Content-Type": "application/json"}
if api_key:
    headers["Authorization"] = f"Bearer {api_key}"
```

## Config UX

### Provider Registry

Add a registry in `src/egrep/config.py` that drives:

- choices shown by `egrep config`
- default base URLs
- whether `api_key` is required
- whether `model` is required
- whether `base_url` is user-editable
- runtime transport kind

Suggested fields:

```python
{
    "provider": "vllm",
    "section": "embedding",
    "default_base_url": "http://127.0.0.1:8000/v1",
    "prompt_base_url": True,
    "requires_api_key": False,
    "requires_model": True,
    "transport_kind": "openai_embeddings",
}
```

### Prompt Rules

- `openrouter`
  - do not prompt for `base_url`
  - persist fixed `https://openrouter.ai/api/v1`
  - require `api_key`
  - require `model`
  - keep current defaults:
    - embedding: `openai/text-embedding-3-small`
    - reranking: `cohere/rerank-v3.5`
- `siliconflow`
  - do not prompt for `base_url`
  - persist fixed `https://api.siliconflow.cn/v1`
  - require `api_key`
  - require `model`
  - no OpenRouter defaults; use blank/defaultless model prompt
- `llamacpp`
  - prompt for `base_url`, default `http://127.0.0.1:8080/v1`
  - `api_key` optional
  - require `model`
- `vllm`
  - prompt for `base_url`, default `http://127.0.0.1:8000/v1`
  - `api_key` optional
  - require `model`
- `sglang`
  - prompt for `base_url`, default `http://127.0.0.1:30000/v1`
  - `api_key` optional
  - require `model`
- `none`
  - valid only for reranking
  - do not prompt for `base_url`, `api_key`, or `model`

Use `questionary.prompt([...])` for conditional prompting:

```python
answers = questionary.prompt([
    {
        "type": "select",
        "name": "provider",
        "message": "Reranking provider",
        "choices": ["openrouter", "siliconflow", "llamacpp", "vllm", "sglang", "none"],
    },
    {
        "type": "text",
        "name": "base_url",
        "message": "Base URL",
        "default": lambda a: provider_specs[a["provider"]]["default_base_url"],
        "when": lambda a: provider_specs[a["provider"]]["prompt_base_url"],
    },
])
```

### Persisted Config Shape

OpenRouter example:

```json
{
  "embedding": {
    "provider": "openrouter",
    "base_url": "https://openrouter.ai/api/v1",
    "api_key": "secret",
    "model": "openai/text-embedding-3-small"
  },
  "reranking": {
    "provider": "openrouter",
    "base_url": "https://openrouter.ai/api/v1",
    "api_key": "secret",
    "model": "cohere/rerank-v3.5"
  }
}
```

SiliconFlow example:

```json
{
  "embedding": {
    "provider": "siliconflow",
    "base_url": "https://api.siliconflow.cn/v1",
    "api_key": "secret",
    "model": "BAAI/bge-m3"
  },
  "reranking": {
    "provider": "siliconflow",
    "base_url": "https://api.siliconflow.cn/v1",
    "api_key": "secret",
    "model": "BAAI/bge-reranker-v2-m3"
  }
}
```

Local runtime + no-rerank example:

```json
{
  "embedding": {
    "provider": "vllm",
    "base_url": "http://127.0.0.1:8000/v1",
    "api_key": "",
    "model": "BAAI/bge-m3"
  },
  "reranking": {
    "provider": "none"
  }
}
```

### Validation Rules

- Validation becomes section- and provider-aware.
- `none` is accepted only under `reranking`.
- `base_url` is required only when the chosen provider is local runtime.
- `api_key` is optional only for local runtime providers.
- `model` is required for every provider except `none`.

## Query Semantics

`search()` must skip rerank when either condition is true:

- CLI `--no-rerank`
- config `provider_config["reranking"]["provider"] == "none"`

Behavior when rerank is skipped:

- do not call `rerank()`
- set `candidate.confidence = candidate.hybrid_score`
- leave `candidate.rerank_score` as `None`

CLI flag priority:

- `--no-rerank` always wins even if a rerank provider is configured.

## Indexing / Manifest

- Index building continues to require only embedding provider settings.
- `reranking.provider == "none"` must not block `egrep init`.
- Manifest must allow `rerank_model: null` when reranking provider is `none`.

## Init Progress UX

### Output Rules

- Progress/status goes to `stderr` only.
- Final `indexed X files, ...` summary remains on `stdout`.
- Show the current document path during discovery, chunking, and embedding.

### Stage Model

Recommended stages:

1. `prepare`
2. `discover`
3. `chunk`
4. `embed`
5. `write_chroma`
6. `write_bm25`
7. `write_docstore`
8. `write_manifest`

Each stage has its own progress line. Determinate totals:

- `discover`: candidate file paths under `root` before filtering/classification
- `chunk`: accepted workspace files
- `embed`: retrieval chunks
- `write_docstore`: display chunks

One-shot stages may render as a stage banner plus completion tick.

### Reporter Interface

Add a lightweight event model in `src/egrep/indexing.py`:

```python
@dataclass(frozen=True)
class InitProgress:
    stage: str
    current: int | None = None
    total: int | None = None
    path: str | None = None
    message: str | None = None
```

`build_index(..., progress=None)` emits events.

Thread optional progress callbacks into:

- `discover_workspace_files(..., progress=None)`
- `chunk_workspace_files(..., progress=None)`

Embedding progress should be orchestrated in `build_index()` so the reporter can emit the current retrieval chunk path.

### Rendering Expectations

- Avoid line spam; update the current stage line in place when practical.
- Include the current path as a truncated relative path when needed.
- Keep messages short enough for standard terminals.

## Files Expected To Change

- `src/egrep/config.py`
- `src/egrep/providers.py`
- `src/egrep/retrieval.py`
- `src/egrep/indexing.py`
- `src/egrep/discovery.py`
- `src/egrep/chunking.py`
- `src/egrep/cli.py`
- `README.md`
- `tests/test_config.py`
- `tests/test_providers.py`
- `tests/test_retrieval.py`
- `tests/test_indexing.py`
- `tests/test_cli.py`

## Test Plan

### Config

- provider choices include `siliconflow`, `llamacpp`, `vllm`, `sglang`, and rerank `none`
- `siliconflow` does not prompt for `base_url`
- local providers do prompt for `base_url` with provider-specific defaults
- local providers allow blank `api_key`
- `none` writes `{ "provider": "none" }`
- `none` is rejected for embedding

### Providers

- empty local `api_key` omits the `Authorization` header
- SiliconFlow requests use fixed `/v1` base URL and current request shapes
- rerank accepts `{"results": [...]}` and top-level `[{"index": ..., "score": ...}]`

Use `responses` matchers where field ordering should not matter:

```python
responses.post(
    url,
    json={"data": [{"embedding": [0.1, 0.2]}]},
    match=[matchers.json_params_matcher({"model": "model", "input": ["one"]})],
)
```

### Retrieval

- `reranking.provider == "none"` skips `rerank()`
- `--no-rerank` still skips `rerank()` when a rerank provider exists
- no-rerank path sets `confidence == hybrid_score`
- SGLang top-level list response produces rerank scores correctly

### Indexing UX

- progress events are emitted for all stages
- `run_init()` writes progress to `stderr`
- final index summary remains on `stdout`
- manifest writes `rerank_model: null` when rerank provider is `none`

## Acceptance Criteria

1. `egrep config` can configure `openrouter`, `siliconflow`, `llamacpp`, `vllm`, `sglang`, and rerank `none`.
2. SiliconFlow works without prompting for `base_url`.
3. Local runtime providers work with editable `base_url` defaults and no auth header when the key is blank.
4. `reranking.provider == "none"` behaves the same as current no-rerank flow.
5. `sglang` rerank works with top-level list responses.
6. `egrep init` shows per-stage progress and current document on `stderr`.
7. Existing tests are updated and new cases cover provider config, rerank disablement, and progress reporting.
