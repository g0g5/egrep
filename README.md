# egrep

`egrep` is a hybrid workspace search CLI for coding agents and developers. It builds a local lexical and vector index for a project, then returns ranked source snippets for natural-language or keyword queries.

## Features

- Hybrid search with local BM25 and ChromaDB vector indexes.
- OpenAI-compatible embedding and rerank API support for OpenRouter, SiliconFlow, and local runtimes.
- Optional reranking, including a persisted `none` provider and per-query `--no-rerank`.
- Per-stage `egrep init` progress on `stderr`, with the current document shown while indexing.
- Code-, Markdown-, and text-aware chunking with line-numbered results.
- Workspace-local indexes stored under `.egrep/`.
- Human-readable output by default, with verbose JSON for tooling.

## Requirements

- Python 3.12 or newer
- `uv`
- A configured embedding provider. Hosted providers require an API key; local runtimes can use a blank API key.

## Installation

Recommended:

```bash
uv tool install egrep --from git+https://github.com/g0g5/egrep
```

Alternatively:

```bash
pip install egrep --from git+https://github.com/g0g5/egrep
```

After installation, the global `egrep` command should be available:

```bash
egrep --help
```

## Usage

Configure a global provider:

```bash
egrep config --global
```

In a workspace, optionally configure a workspace-specific provider:

```bash
egrep config
```

Build an index for the current workspace:

```bash
egrep init --root . --max-file-size 2MB
```

Search the indexed workspace:

```bash
egrep "where is provider configuration loaded?"
```

### Configure Providers

```bash
egrep config [--global]
```

The command prompts for embedding and reranking providers, API keys, models, and local runtime base URLs. By default, workspace configuration is written to `.egrep/provider.json`; global configuration is used as a fallback.

Embedding providers:

- `openrouter`
- `siliconflow`
- `llamacpp`
- `vllm`
- `sglang`

Reranking providers:

- `openrouter`
- `siliconflow`
- `llamacpp`
- `vllm`
- `sglang`
- `none`

Provider behavior:

- OpenRouter uses the fixed base URL `https://openrouter.ai/api/v1` and default models shown below.
- SiliconFlow uses the fixed base URL `https://api.siliconflow.cn/v1` and prompts for models.
- Local runtimes prompt for editable `/v1` base URLs: `llamacpp` defaults to `http://127.0.0.1:8080/v1`, `vllm` to `http://127.0.0.1:8000/v1`, and `sglang` to `http://127.0.0.1:30000/v1`.
- Local runtime API keys are optional. When blank, provider requests omit the `Authorization` header.
- Reranking provider `none` is persisted as `{ "provider": "none" }` and disables reranking for searches by default.

Default models:

- Embeddings: `openai/text-embedding-3-small`
- Reranking: `cohere/rerank-v3.5`

### Build or Rebuild an Index

```bash
egrep init [--root PATH] [--collection NAME] [--include PATTERN] [--exclude PATTERN] [--max-file-size SIZE]
```

Examples:

```bash
egrep init --root . --max-file-size 2MB
egrep init --include "src/**" --include "tests/**"
egrep init --exclude "docs/archive/**"
```

Index artifacts are written under `.egrep/`. Re-running `egrep init` rebuilds the index.

Progress and status output is written to `stderr`; the final `indexed X files, ...` summary remains on `stdout`. Progress is reported per stage for prepare, discovery, chunking, embedding, Chroma writes, BM25 writes, docstore writes, and manifest writes. Discovery, chunking, and embedding progress includes the current document path.

### Search

```bash
egrep "QUERY" [--top-k N] [--no-rerank] [-v|--verbose]
```

Examples:

```bash
egrep "how are files ignored?"
egrep "rerank response parsing" --top-k 5
egrep "index manifest" --no-rerank
egrep "provider request failed" --verbose
```

Default output shows ranked snippets with file paths, line ranges, and confidence scores. Verbose output prints JSON with BM25, vector, hybrid, and rerank scores.

Use `--no-rerank` to skip reranking for a single query. If the configured reranking provider is `none`, searches use the same no-rerank behavior automatically and confidence is based on the hybrid score.

## What Gets Indexed

`egrep` indexes UTF-8 text files up to the configured size limit. It recognizes common code, Markdown, and text extensions, and skips binary files.

Built-in ignores include `.git/`, `.egrep/`, virtual environments, `node_modules/`, build outputs, caches, archives, PDFs, and common image formats. Patterns from `.gitignore` are also respected. `--include` and `--exclude` use gitignore-style patterns.

## Development

```bash
uv run pytest
uv build
```
