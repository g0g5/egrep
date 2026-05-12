# Iteration Complete

Iteration `1` (`local-providers-init-progress`) is complete.

## Implemented

- Added registry-driven provider configuration for OpenRouter, SiliconFlow, llama.cpp, vLLM, SGLang, and reranking `none`.
- Updated provider HTTP behavior for OpenAI-compatible embeddings/rerank endpoints, optional local API keys, and list-or-object rerank responses.
- Added config-based rerank disabling semantics and manifest support for `rerank_model: null`.
- Added `egrep init` per-stage progress events and stderr-only CLI progress rendering with stdout summary preserved.
- Updated README, AGENTS guidance, speciter docs, and tests for the new provider and progress behavior.

## Verification

- `uv run pytest` passed with 63 tests during implementation.
- Targeted suites were run for config, providers, retrieval, indexing, discovery, chunking, and CLI coverage.
