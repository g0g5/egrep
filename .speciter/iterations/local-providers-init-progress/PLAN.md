# Implementation Plan

## Phase 1: Provider Registry And Config UX

1. Add a provider registry in `src/egrep/config.py` for embedding and reranking providers, including provider choices, fixed/default base URLs, prompt behavior, required fields, and transport kind.
2. Update config prompts to derive provider choices and conditional fields from the registry.
3. Preserve OpenRouter defaults and fixed base URL behavior.
4. Add SiliconFlow with fixed `https://api.siliconflow.cn/v1`, required API key, and required model prompts without model defaults.
5. Add local runtime providers `llamacpp`, `vllm`, and `sglang` with editable `/v1` base URL defaults, optional API key, and required model prompts.
6. Add reranking provider `none` so it persists only `{ "provider": "none" }` and skips base URL, API key, and model prompts.
7. Update provider-aware validation so `none` is valid only for reranking, local providers may omit API keys, and all non-`none` providers require a model.

Completed 2026-05-12 12:55:41 MSK: Added the config provider registry, registry-driven prompts, fixed OpenRouter/SiliconFlow base URL handling, local provider editable `/v1` defaults with optional API keys, reranking `none` persistence, and provider-aware validation. Updated config tests for provider choices, SiliconFlow prompt behavior, local provider defaults, optional local API keys, and reranking `none`; verified with `uv run pytest tests/test_config.py` and `uv run pytest`.

## Phase 2: Provider HTTP Behavior

1. Update `src/egrep/providers.py` so embedding providers share the OpenAI-compatible `/embeddings` request path.
2. Update request header construction to omit `Authorization` whenever `api_key` is empty.
3. Update reranking requests to use the shared `/rerank` request path for OpenRouter, SiliconFlow, and local runtime providers.
4. Normalize rerank responses from both `{"results": [...]}` payloads and top-level result lists.
5. Keep rerank score parsing compatible with both `relevance_score` and `score` fields.

Completed 2026-05-12 12:59:19 MSK: Updated provider HTTP calls to omit `Authorization` when `api_key` is blank, added a shared JSON POST helper that accepts dict or list responses, kept embeddings on the OpenAI-compatible `/embeddings` path, added `return_documents: false` to shared `/rerank` requests, and normalized rerank responses from both `{"results": [...]}` and top-level list payloads while preserving downstream `{"results": [...]}` shape. Added provider tests for blank local API keys, SiliconFlow embedding URL/request shape, rerank request payloads, and top-level list rerank responses; verified with `uv run pytest tests/test_providers.py` and `uv run pytest`.

## Phase 3: Rerank Disable Semantics

1. Update retrieval logic in `src/egrep/retrieval.py` so reranking is skipped when `--no-rerank` is set or config has `reranking.provider == "none"`.
2. Ensure skipped rerank results set `confidence` from `hybrid_score` and leave `rerank_score` as `None`.
3. Preserve CLI flag priority so `--no-rerank` wins even when a rerank provider is configured.
4. Update indexing and manifest handling so `reranking.provider == "none"` does not block init and writes `rerank_model: null`.

Completed 2026-05-12 13:01:52 MSK: Added config-based rerank skipping for `reranking.provider == "none"` while preserving `--no-rerank` priority, kept skipped candidates on `hybrid_score` confidence with `rerank_score` unset, and changed manifest writing to allow `rerank_model: null` when reranking is disabled. Added retrieval tests for config-based and CLI-based rerank skipping plus indexing coverage for reranking `none`; verified with `uv run pytest tests/test_retrieval.py`, `uv run pytest tests/test_indexing.py`, and `uv run pytest`.

## Phase 4: Init Progress Events

1. Add the `InitProgress` dataclass and optional `progress` callback support in `src/egrep/indexing.py`.
2. Emit progress events for `prepare`, `discover`, `chunk`, `embed`, `write_chroma`, `write_bm25`, `write_docstore`, and `write_manifest`.
3. Thread optional progress callbacks into discovery and chunking code so current document paths can be reported.
4. Compute determinate totals for discovery candidates, accepted workspace files, retrieval chunks, and display chunks.
5. Emit embedding progress from `build_index()` using retrieval chunk paths.

Completed 2026-05-12 13:06:28 MSK: Added the `InitProgress` dataclass and optional `build_index(..., progress=...)` callback support, emitted events for prepare, discover, chunk, embed, write_chroma, write_bm25, write_docstore, and write_manifest stages, threaded lightweight progress callbacks through discovery, chunking, and docstore writing, and reported current document paths with determinate totals for discovery candidates, accepted files, retrieval chunks, and display chunks. Added indexing coverage for emitted progress stages and paths; verified with `uv run pytest tests/test_indexing.py tests/test_discovery.py tests/test_chunking.py` and `uv run pytest`.

## Phase 5: Progress Rendering In CLI

1. Add stdlib-only progress rendering in `src/egrep/cli.py` for `egrep init`.
2. Write all progress and status output to `stderr` only.
3. Render each stage as a concise progress line, updating in place where practical.
4. Show truncated relative paths for current documents during discovery, chunking, and embedding.
5. Keep the final `indexed X files, ...` summary on `stdout`.

Completed 2026-05-12 13:09:13 MSK: Added a stdlib-only `egrep init` progress renderer in `src/egrep/cli.py` that writes concise per-stage updates to `stderr`, updates the current line in place, truncates current document paths to terminal width, and finalizes the progress line before exit or errors. Threaded the renderer into `run_init(..., progress=...)` while preserving the final indexed summary on `stdout`. Added CLI coverage for `stderr` progress and `stdout` summary separation; verified with `uv run pytest tests/test_cli.py tests/test_indexing.py`.

## Phase 6: Documentation And Tests

1. Update `README.md` to document SiliconFlow, local runtime providers, optional local API keys, rerank `none`, and init progress behavior.
2. Update config tests for provider choices, conditional prompts, local provider defaults, optional API keys, and rerank `none` validation/persistence.
3. Update provider tests for missing auth headers with blank API keys, SiliconFlow request URLs, shared request shapes, and rerank response normalization.
4. Update retrieval tests for config-based no-rerank behavior, CLI no-rerank priority, confidence assignment, and SGLang top-level rerank list responses.
5. Update indexing and CLI tests for progress event emission, `stderr` progress output, `stdout` final summary, and manifest `rerank_model: null` behavior.
6. Run the full test suite with `uv run pytest` and address regressions.

Completed 2026-05-12 13:11:22 MSK: Updated `README.md` to document SiliconFlow, local runtime providers and their `/v1` defaults, optional local API keys with omitted auth headers, reranking provider `none`, per-query `--no-rerank`, and `egrep init` progress behavior with `stderr` progress and `stdout` summary separation. Confirmed phase coverage in config, provider, retrieval, indexing, and CLI tests; verified with `uv run pytest` passing 63 tests.
