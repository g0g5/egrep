## Project Overview
`egrep` is a Python 3.12 CLI for hybrid workspace search, using local ChromaDB/BM25 indexes with OpenAI-compatible embedding and rerank providers.

## Structure Map
```text
egrep/
|- pyproject.toml              # Project metadata, dependencies, console script, pytest config, and Hatchling build setup
|- uv.lock                     # Locked dependency graph for uv
|- README.md                   # User-facing feature, install, usage, and development docs
|- main.py                     # Root launcher delegating to the egrep CLI
|- src/                        # Runtime package source
|  \- egrep/                   # Main CLI package
|     |- __main__.py           # `python -m egrep` entrypoint
|     |- cli.py                # Argparse command parsing, dispatch, and init progress rendering
|     |- errors.py             # Shared expected error types and exit codes
|     |- config.py             # Provider registry, prompting, validation, and workspace/global config resolution
|     |- providers.py          # OpenAI-compatible embedding and rerank HTTP clients
|     |- discovery.py          # Workspace traversal, ignore/include/exclude handling, and file classification
|     |- chunking.py           # Code/Markdown/text chunking, retrieval/display chunk models, and docstore IO
|     |- indexing.py           # Index build orchestration for vector, BM25, docstore, and manifest artifacts
|     |- retrieval.py          # Query embedding, hybrid retrieval, reranking, dedupe, and result assembly
|     \- output.py             # Human-readable and verbose JSON output formatting
|- tests/                      # Pytest suite mirroring package modules
|  |- test_cli.py              # CLI parsing and dispatch coverage
|  |- test_config.py           # Provider config path, registry, validation, and prompting coverage
|  |- test_providers.py        # Mocked provider API coverage
|  |- test_discovery.py        # Workspace discovery and filtering coverage
|  |- test_chunking.py         # Chunk splitting and docstore coverage
|  |- test_indexing.py         # Index layout, manifest, rebuild, and progress coverage
|  \- test_retrieval.py        # Search, rerank, no-rerank, and deduplication coverage
\- analysis_*.md               # Research notes; not part of runtime behavior
```

## Development Guide
- Build: `uv build`
- Test and verify changes: `uv run pytest`
- Typecheck: no dedicated typecheck command is configured
