# Local Provider API Research

## Scope

Research target: llama.cpp, vLLM, and SGLang embedding/reranking HTTP APIs, request/response shapes, and how reusable the current `requests`-based client implementation is for these backends.

Current implementation reference: `src/egrep/providers.py`.

## Executive Summary

The real implementation does not need `2 x 3 = 6` providers.

The practical split should be by API protocol shape rather than backend brand:

1. `OpenAIEmbeddingsProvider`: covers llama.cpp, vLLM, and SGLang through `/v1/embeddings`.
2. `JinaCohereRerankProvider`: covers llama.cpp, vLLM, and most hosted rerank APIs through `/rerank` or `/v1/rerank`.
3. Optional: `SGLangRerankProvider`, or more simply a response normalizer that accepts SGLang's top-level list response.

Recommended real count: **2 provider shapes plus one rerank response normalizer**. If explicit provider classes are preferred, use **3 providers**. Avoid creating 6 backend-specific providers.

## Current Client Shape

`src/egrep/providers.py` currently does:

```python
POST {base_url}/embeddings
{
  "model": model,
  "input": texts
}
```

```python
POST {base_url}/rerank
{
  "model": model,
  "query": query,
  "documents": documents,
  "top_n": top_n
}
```

The embedding parser expects OpenAI-style response data:

```json
{
  "data": [
    {"embedding": [0.1, 0.2], "index": 0}
  ]
}
```

The rerank parser in `src/egrep/retrieval.py` currently expects a dict with `results`:

```json
{
  "results": [
    {"index": 0, "relevance_score": 0.98}
  ]
}
```

It accepts either `relevance_score` or `score`, and can map by `index`, `id`, or `document.id`.

## Embedding APIs

### llama.cpp

llama.cpp's server documents an OpenAI-compatible embeddings endpoint:

```http
POST /v1/embeddings
```

Request shape:

```json
{
  "model": "model-name-or-alias",
  "input": ["hello", "world"],
  "encoding_format": "float"
}
```

Notes:

- The server must be launched for embedding usage, typically with `--embedding`/`--embeddings`.
- The model must use pooling other than `none`.
- `/embeddings` also exists but is explicitly non-OpenAI-compatible; prefer `/v1/embeddings`.

Compatibility with current client:

- Works if `base_url` is configured as `http://host:port/v1`.
- Current request omits `encoding_format`, which is optional for common use.

### vLLM

vLLM documents an OpenAI-compatible embeddings endpoint:

```http
POST /v1/embeddings
```

Request shape:

```json
{
  "model": "BAAI/bge-base-en-v1.5",
  "input": ["first text", "second text"],
  "encoding_format": "float"
}
```

Additional supported fields include `dimensions`, `user`, and vLLM-specific extras such as truncation and priority fields.

Compatibility with current client:

- Works if `base_url` is configured as `http://host:port/v1`.
- Current response parser matches OpenAI `data[].embedding`.

### SGLang

SGLang documents an OpenAI-compatible embeddings endpoint:

```http
POST /v1/embeddings
```

Request shape:

```json
{
  "model": "BAAI/bge-large-en-v1.5",
  "input": ["Artificial intelligence", "Machine learning"]
}
```

Response shape:

```json
{
  "object": "list",
  "data": [
    {
      "object": "embedding",
      "embedding": [0.0234, -0.0187],
      "index": 0
    }
  ],
  "model": "BAAI/bge-large-en-v1.5",
  "usage": {
    "prompt_tokens": 8,
    "total_tokens": 8
  }
}
```

Compatibility with current client:

- Works if `base_url` is configured as `http://host:port/v1`.
- Current response parser matches `data[].embedding`.

## Reranking APIs

### llama.cpp

llama.cpp documents reranking as similar to Jina's reranker API.

Endpoints:

```http
POST /reranking
POST /rerank
POST /v1/rerank
POST /v1/reranking
```

Request shape:

```json
{
  "model": "some-model",
  "query": "What is panda?",
  "top_n": 3,
  "documents": [
    "hi",
    "it is a bear",
    "The giant panda is a bear species endemic to China."
  ]
}
```

Notes:

- Requires a reranker model such as `BAAI/bge-reranker-v2-m3`.
- Requires launch options like `--embedding --pooling rank` and `--rerank`/`--reranking` depending on version/configuration.

Compatibility with current client:

- Request shape matches.
- Works with `base_url=http://host:port/v1` because current code posts to `{base_url}/rerank`, yielding `/v1/rerank`.
- Response is documented as Jina-like; current parser should work if the response is `{"results": [...]}` with `index` and score fields.

### vLLM

vLLM supports reranking through custom pooling/scoring APIs.

Endpoints:

```http
POST /rerank
POST /v1/rerank
POST /v2/rerank
```

Request shape:

```json
{
  "model": "BAAI/bge-reranker-v2-m3",
  "query": "What is the capital of France?",
  "documents": [
    "The capital of Brazil is Brasilia.",
    "The capital of France is Paris."
  ],
  "top_n": 2
}
```

Response shape is compatible with Jina/Cohere rerank APIs. Typical shape:

```json
{
  "results": [
    {
      "index": 1,
      "document": {"text": "The capital of France is Paris."},
      "relevance_score": 0.98
    }
  ]
}
```

vLLM also has a lower-level Score API:

```http
POST /score
```

With request shape:

```json
{
  "model": "BAAI/bge-reranker-v2-m3",
  "queries": "What is the capital of France?",
  "documents": [
    "The capital of Brazil is Brasilia.",
    "The capital of France is Paris."
  ]
}
```

The Score API returns `data[].score`, but the Rerank API is a better fit for this project because it matches the current `query + documents + top_n` design.

Compatibility with current client:

- Request shape matches `/v1/rerank`.
- Response shape matches current parser if it returns `results` with `index` and `relevance_score` or `score`.

### SGLang

SGLang supports reranking for cross-encoder models and decoder-only yes/no rerank models.

Endpoint:

```http
POST /v1/rerank
```

SGLang Model Gateway also lists:

```http
POST /v1/rerank
POST /rerank
```

Cross-encoder request shape:

```json
{
  "model": "BAAI/bge-reranker-v2-m3",
  "query": "what is panda?",
  "documents": [
    "hi",
    "The giant panda is a bear species endemic to China."
  ],
  "top_n": 1,
  "return_documents": true
}
```

Decoder-only Qwen3 reranker request shape:

```json
{
  "model": "Qwen3-Reranker-0.6B",
  "query": "法国首都是哪里？",
  "documents": [
    "法国的首都是巴黎。",
    "德国的首都是柏林。",
    "香蕉是黄色的水果。"
  ],
  "instruct": "Given a web search query, retrieve relevant passages that answer the query.",
  "top_n": 2,
  "return_documents": true
}
```

Response shape:

```json
[
  {"score": 0.99, "document": "法国的首都是巴黎。", "index": 0},
  {"score": 0.01, "document": "德国的首都是柏林。", "index": 1}
]
```

With `return_documents: false`:

```json
[
  {"score": 0.99, "index": 0},
  {"score": 0.01, "index": 1}
]
```

Compatibility with current client:

- Request shape mostly matches. Current client does not send `return_documents`, but SGLang defaults are sufficient for text-only use.
- Current `post_json` rejects top-level list responses, so SGLang rerank currently does **not** work.
- Current `_parse_rerank_scores()` also expects `response.get("results")`, so it needs a small compatibility path for top-level list.

## Reuse Assessment

### Embedding

All three backends can use a single OpenAI-compatible embedding implementation.

Required configuration convention:

```toml
[embedding]
base_url = "http://localhost:8000/v1"
model = "..."
```

Then the current code posts to:

```text
http://localhost:8000/v1/embeddings
```

This is correct for llama.cpp, vLLM, and SGLang.

### Reranking

llama.cpp and vLLM can reuse the current rerank request shape directly.

Required configuration convention:

```toml
[reranking]
base_url = "http://localhost:8000/v1"
model = "..."
```

Then the current code posts to:

```text
http://localhost:8000/v1/rerank
```

This is valid for llama.cpp and vLLM, and likely valid for SGLang. The only blocker is SGLang's response shape.

## Recommended Minimal Code Changes

Do not introduce backend-specific clients for each server. Instead:

1. Keep a generic OpenAI embeddings function.
2. Keep a generic Jina/Cohere-style rerank request function.
3. Allow `post_json` or `rerank()` to accept top-level JSON arrays for rerank responses.
4. Normalize rerank response shapes before parsing:

```python
def _rerank_results(response):
    if isinstance(response, list):
        return response
    results = response.get("results")
    if isinstance(results, list):
        return results
    raise ProviderAPIError("provider rerank response missing results")
```

5. Continue accepting both `relevance_score` and `score`.
6. Optionally add `return_documents: False` for rerank providers where this is accepted, because the project only needs `index` and score.

## Provider Count Decision

Minimum viable provider count:

- 1 embedding provider: OpenAI-compatible `/v1/embeddings`.
- 1 reranking provider: Jina/Cohere-style `/v1/rerank`, with response normalization for dict/list forms.

Practical provider count:

- 2 provider shapes total.

If explicit naming improves configuration UX:

- `openai_embeddings`
- `jina_rerank`
- optional alias presets: `llamacpp`, `vllm`, `sglang` that only prefill endpoint paths and defaults.

Avoid:

- `llamacpp_embedding`, `llamacpp_rerank`, `vllm_embedding`, `vllm_rerank`, `sglang_embedding`, `sglang_rerank` as separate logic providers. This would duplicate nearly identical request code and make maintenance worse.

## Sources

- llama.cpp server README: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- vLLM OpenAI-Compatible Server: https://docs.vllm.ai/serving/openai_compatible_server.html
- vLLM Embedding Usages: https://docs.vllm.ai/en/latest/models/pooling_models/embed.html
- vLLM Scoring Usages: https://docs.vllm.ai/en/latest/models/pooling_models/scoring.html
- SGLang Embeddings API: https://sgl-project-sglang-93.mintlify.app/api/http/embeddings
- SGLang Native APIs: https://sglang.org/zh/basic_usage/native_api
- SGLang Rerank Models: https://sgl-project.github.io/supported_models/retrieval_ranking/rerank_models.html
- SGLang Model Gateway: https://docs.sglang.io/advanced_features/sgl_model_gateway.html
