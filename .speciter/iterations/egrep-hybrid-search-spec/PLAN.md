# Implementation Plan: egrep Hybrid Workspace Search

## Phase 1: Project Structure and CLI Entry Point

1. Define the `uv` project metadata and add the required runtime and dev dependencies from the spec.
2. Create the Python package layout for CLI, configuration, providers, indexing, chunking, retrieval, output formatting, and tests.
3. Implement the `argparse` parser for `egrep init`, `egrep config`, and query mode with `--top-k`, `-v/--verbose`, and `--no-rerank`.
4. Add a thin command dispatcher that maps expected failures to the documented exit codes and leaves invalid CLI usage to `argparse`.

Completion log, 2026-05-11 14:01:17 MSK: Completed Phase 1 by adding the `uv` project metadata, required runtime/dev dependencies, console script entry point, `src/egrep` package skeleton, argparse-based CLI parsing for `init`, `config`, and query mode, command dispatch with documented expected-error exit-code handling, and initial CLI tests. Verified with `uv run pytest`.

## Phase 2: Provider Configuration

1. Implement workspace and global provider config paths: `.egrep/provider.json` and `~/.config/egrep/provider.json`.
2. Implement config resolution so workspace config takes precedence and global config is used only when workspace config is missing.
3. Validate that both embedding and reranking sections contain provider, base URL, API key, and model; return exit code `4` when missing or incomplete.
4. Implement `egrep config` and `egrep config --global` using `questionary`, with separate prompt groups for embedding and reranking.
5. Persist only OpenRouter provider settings using the fixed OpenRouter base URL and the specified default model names.

Completion log, 2026-05-11 14:03:26 MSK: Completed Phase 2 by adding workspace and global provider config path handling, workspace-first/global-fallback config resolution, required embedding/reranking section validation with `ProviderConfigError` exit code `4`, interactive `questionary` prompts for separate embedding and reranking OpenRouter settings, provider config persistence for `.egrep/provider.json` and `~/.config/egrep/provider.json`, and config validation hooks for `egrep init` and query mode. Added provider config tests for resolution precedence, global fallback, missing/incomplete config failures, and workspace/global config writing. Verified with `uv run pytest`.

## Phase 3: Provider HTTP Client

1. Implement a small `requests` wrapper with explicit connect/read timeout and clear provider errors.
2. Implement embedding calls against `/embeddings`, returning vectors in provider response order.
3. Implement reranking calls against `/rerank`, passing model, query, documents, and `top_n`.
4. Batch retrieval chunk embeddings with a default batch size of `32`.
5. Map provider HTTP and response failures to exit code `5`.

Completion log, 2026-05-11 14:04:53 MSK: Completed Phase 3 by adding a `requests` JSON POST wrapper with explicit connect/read timeout and clear `ProviderAPIError` failures, OpenRouter-compatible embedding calls that preserve provider response order, reranking calls that pass model, query, documents, and `top_n`, default batched embedding support with batch size `32`, and provider HTTP/invalid response failures that map to exit code `5`. Added mocked `responses` tests for embedding, reranking, batching, HTTP failure, and response-shape failure. Verified with `uv run pytest`.

## Phase 4: Workspace Discovery and File Classification

1. Implement visible file discovery from the resolved root using `.gitignore` plus the built-in ignore list.
2. Apply CLI include and exclude filters consistently with gitignore-style matching.
3. Parse `--max-file-size` values and skip files that exceed the configured size.
4. Skip binary and unreadable files without aborting the index build.
5. Classify files as `code`, `markdown`, or `text` based on the spec extension lists, allowing unknown extensions only when UTF-8 decodable and under the size limit.

Completion log, 2026-05-11 14:06:24 MSK: Completed Phase 4 by adding workspace file discovery from a resolved root with built-in ignores, `.gitignore` support, gitignore-style CLI include/exclude filtering, `--max-file-size` parsing with byte/KB/MB/GB units, non-aborting skips for oversized, binary, unreadable, and non-UTF-8 files, and file classification for code, markdown, and text including UTF-8 unknown extensions as text. Added discovery tests for ignore handling, include/exclude filters, size limits, binary/non-UTF-8/unreadable skips, and classification. Verified with `uv run pytest`.

## Phase 5: Chunking and Docstore

1. Implement stable IDs and required metadata for every retrieval chunk.
2. Use LlamaIndex `CodeSplitter` for code files and create function/class/method-oriented display chunks where available.
3. Use LlamaIndex `MarkdownNodeParser` for markdown files and treat sections as display chunks.
4. Split overlong code and markdown display chunks into overlapped child retrieval chunks that point back to the parent display chunk.
5. Implement overlapped standalone chunking for text files using the default line/token targets.
6. Track path, retrieval line range, display line range, content hash, and file hash for all chunks.
7. Persist display chunks in `.egrep/docstore.jsonl` keyed by `display_chunk_id`.

Completion log, 2026-05-11 14:09:38 MSK: Completed Phase 5 by adding stable retrieval/display chunk models, required retrieval metadata, content and file hashing, LlamaIndex-backed code and markdown display chunk extraction with safe fallbacks, the tree-sitter parser package needed by LlamaIndex `CodeSplitter`, overlong code/markdown parent-to-child overlapped retrieval chunking, standalone overlapped text chunking, and JSONL docstore persistence keyed by `display_chunk_id`. Added chunking tests for text overlap, stable metadata, markdown section display chunks, overlong parent/child relationships, and docstore round-tripping. Verified with `uv run pytest`.

## Phase 6: Index Build

1. Implement `egrep init` root resolution, collection naming, and rebuild behavior for the selected workspace index.
2. Ensure `.egrep/` is created without deleting workspace provider configuration.
3. Persist retrieval chunks to ChromaDB under `.egrep/chroma` using cosine HNSW configuration.
4. Build and persist the LlamaIndex BM25 retriever under `.egrep/bm25` with English stemming.
5. Write `.egrep/manifest.json` with version, root, collection, provider models, and file/chunk counts.
6. Map filesystem and index write failures to exit code `6`.

Completion log, 2026-05-11 14:11:25 MSK: Completed Phase 6 by implementing `egrep init` root resolution, collection naming, rebuild behavior that preserves `.egrep/provider.json`, workspace discovery and chunking orchestration, batched embedding of retrieval chunks, persistent ChromaDB writes under `.egrep/chroma` with cosine HNSW configuration, LlamaIndex BM25 persistence under `.egrep/bm25` with English stemming, docstore persistence, manifest writing with version/root/collection/provider model/count metadata, and filesystem/index write failure mapping to `IndexWriteError` exit code `6`. Added indexing tests for expected `.egrep/` layout and manifest creation, provider config preservation, and init write-failure exit-code mapping. Verified with `uv run pytest`.

## Phase 7: Search Pipeline

1. Implement query mode to require `.egrep/manifest.json`, returning exit code `3` with a clear message when missing.
2. Resolve and validate provider configuration before searching.
3. Embed the query and retrieve candidates from Chroma using `vector_top_k = 50`.
4. Load the persisted BM25 retriever and retrieve candidates using `bm25_top_k = 50`.
5. Normalize BM25 and vector scores independently, merge candidates by retrieval `chunk_id`, and compute the equal-weight hybrid score.
6. Keep the top `candidate_top_k = 80` candidates by hybrid score.
7. Build rerank documents that include both the matched child text and parent display text.
8. Rerank candidates unless `--no-rerank` is set; when skipped, sort by hybrid score.
9. Map candidates to display chunks, deduplicate by `display_chunk_id`, and retain the best-scoring child hit for each display chunk.
10. Return the requested `--top-k` display chunks with confidence based on normalized rerank score or hybrid score.

Completion log, 2026-05-11 14:14:43 MSK: Completed Phase 7 by implementing query mode manifest checks with `IndexNotFoundError` exit code `3`, provider config resolution before search, query embedding, Chroma vector retrieval with `vector_top_k = 50`, persisted BM25 retrieval with `bm25_top_k = 50`, independent score normalization, retrieval chunk merging with equal-weight hybrid scoring, `candidate_top_k = 80` pruning, rerank document construction with matched child and parent display text, optional reranking with normalized rerank confidence, `--no-rerank` hybrid-score ordering, display chunk mapping, deduplication by `display_chunk_id`, and top-k result return/printing. Added retrieval tests for missing index behavior, BM25/vector merging, no-rerank scoring, rerank document shape, rerank confidence, and display deduplication. Verified with `uv run pytest`.

## Phase 8: Output Formatting

1. Implement default human-readable output with only rank, path, line range, confidence, and content.
2. Implement verbose JSON output only for `-v/--verbose`.
3. Include query, result metadata, BM25 score, vector score, hybrid score, rerank score, matched child details, and content in verbose output.
4. Ensure default output does not emit JSON and verbose output parses with `json.loads()`.

Completion log, 2026-05-11 14:16:02 MSK: Completed Phase 8 by adding centralized human-readable and verbose JSON output formatters, wiring query mode to select verbose JSON only for `-v/--verbose`, including query metadata, result path/line/confidence fields, BM25/vector/hybrid/rerank scores, matched child details, and content in verbose output, and preserving minimal non-JSON default output with rank, path, line range, confidence, and content only. Added output tests that assert default output is not JSON and verbose output parses with `json.loads()`. Verified with `uv run pytest`.

## Phase 9: Test Coverage

1. Add unit tests for CLI parsing and command dispatch exit code behavior.
2. Add tests for workspace/global provider config writing, resolution precedence, and incomplete config failures.
3. Add mocked `responses` tests for embedding, reranking, batching, and provider HTTP failures.
4. Add discovery tests for current-directory defaults, built-in ignores, `.gitignore`, extra include/exclude filters, binary files, unreadable files, and max file size.
5. Add chunking tests for code, markdown, text, overlong parent-to-child relationships, stable metadata, and docstore persistence.
6. Add indexing tests that assert manifest, Chroma directory, BM25 directory, and docstore are created.
7. Add retrieval tests for BM25/vector merge, score normalization, rerank document shape, deduplication by display chunk, `--no-rerank`, and output schemas.
8. Keep all unit tests network-free and skip any optional real-provider tests unless `OPENROUTER_API_KEY` is available.
9. Run `uv run pytest` and fix failures without introducing local model runtime dependencies.

Completion log, 2026-05-11 14:17:29 MSK: Completed Phase 9 by reviewing the test suite against the coverage checklist, adding focused tests for documented dispatch exit-code behavior including unexpected errors, current-directory default root resolution for `egrep init`, code function/class display chunking, and overlong markdown parent-to-child retrieval chunking. Confirmed existing tests cover provider config writing/resolution/failures, mocked provider HTTP behavior, discovery filters and skips, indexing layout, retrieval merge/rerank/deduplication/no-rerank behavior, and output schemas. Verified all tests are network-free and pass with `uv run pytest`.

## Phase 10: Acceptance Verification

1. Verify `uv run egrep init` indexes a small fixture workspace and writes the expected `.egrep/` layout.
2. Verify `uv run egrep "query"` returns ranked human-readable snippets with paths, line ranges, and confidence.
3. Verify `uv run egrep "query" -v` returns the specified verbose JSON shape.
4. Verify missing index, missing provider config, provider API failure, and filesystem/index write failures map to the documented exit codes.
5. Confirm the dependency set excludes local model runtime packages such as `llama-cpp-python`, `transformers`, and `vllm`.

Completion log, 2026-05-11 14:20:33 MSK: Completed Phase 10 by running full test verification with `uv run pytest`, performing CLI-level acceptance against an isolated fixture workspace using a local mocked provider, confirming `uv run egrep init` writes `.egrep/manifest.json`, `.egrep/chroma/`, `.egrep/bm25/`, and `.egrep/docstore.jsonl`, confirming default query output returns ranked human-readable snippets with paths, line ranges, and confidence, confirming `-v/--verbose` returns parseable JSON with the specified result fields, verifying documented exit codes for missing index (`3`), missing provider config (`4`) for init and query, provider API failure (`5`), and filesystem/index write failure (`6`), and confirming `pyproject.toml` excludes local model runtime packages `llama-cpp-python`, `transformers`, and `vllm`. During acceptance verification, fixed persisted BM25 loading compatibility by avoiding unsupported `bm25s` load kwargs and added a regression test. Verified with `uv run pytest`.
