## Project Overview
`egrep` is a Python 3.12 CLI for hybrid workspace search, using local ChromaDB/BM25 indexes with OpenRouter-compatible embedding and rerank APIs.

## Structure Map
```text
egrep/
|- pyproject.toml              # Project metadata, dependencies, console script, pytest config, and Hatchling build setup
|- uv.lock                     # Locked dependency graph for uv
|- main.py                     # Root launcher delegating to the egrep CLI
|- src/                        # Runtime package source
|  \- egrep/                   # Main CLI package
|     |- __main__.py           # `python -m egrep` entrypoint
|     |- cli.py                # Command parsing and dispatch for init, config, and query flows
|     |- errors.py             # Shared expected error types and exit codes
|     |- config.py             # Workspace/global provider config loading, prompting, validation, and resolution
|     |- providers.py          # OpenRouter-style embedding and rerank HTTP clients
|     |- discovery.py          # Workspace traversal, ignore/include/exclude handling, and file classification
|     |- chunking.py           # Retrieval/display chunk models, splitters, and docstore IO
|     |- indexing.py           # Index build orchestration for vector, BM25, docstore, and manifest artifacts
|     |- retrieval.py          # Query embedding, hybrid retrieval, reranking, dedupe, and result assembly
|     \- output.py             # Human-readable and verbose JSON output formatting
|- tests/                      # Pytest suite mirroring package modules
|  |- test_cli.py              # CLI parsing and dispatch coverage
|  |- test_config.py           # Config path and validation coverage
|  |- test_providers.py        # Mocked provider API coverage
|  |- test_discovery.py        # Workspace discovery and filtering coverage
|  |- test_chunking.py         # Chunk splitting and docstore coverage
|  |- test_indexing.py         # Index layout, manifest, and rebuild coverage
|  \- test_retrieval.py        # Search, rerank, and deduplication coverage
\- analysis_*.md               # Research notes; not part of runtime behavior
```

## Development Guide
- Build: `uv build`
- Test and verify changes: `uv run pytest`
- Typecheck: no dedicated typecheck command is configured
