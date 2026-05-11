# egrep

`egrep` is a hybrid workspace search CLI for coding agents and developers. It builds a local lexical and vector index for a project, then returns ranked source snippets for natural-language or keyword queries.

## Features

- Hybrid search with local BM25 and ChromaDB vector indexes.
- OpenRouter-compatible embedding and rerank API support.
- Code-, Markdown-, and text-aware chunking with line-numbered results.
- Workspace-local indexes stored under `.egrep/`.
- Human-readable output by default, with verbose JSON for tooling.

## Requirements

- Python 3.12 or newer
- `uv`
- An OpenRouter-compatible API key for embeddings and reranking

## Installation

From this repository:

```bash
uv sync
```

Run the CLI with:

```bash
uv run egrep --help
```

To install the command into your active environment:

```bash
uv pip install .
```

## Quick Start

1. Configure providers:

```bash
uv run egrep config
```

Use `--global` to save the provider configuration at `~/.config/egrep/provider.json` instead of the current workspace:

```bash
uv run egrep config --global
```

2. Build an index for the current workspace:

```bash
uv run egrep init
```

3. Search the indexed workspace:

```bash
uv run egrep "where is provider configuration loaded?"
```

## Usage

### Configure Providers

```bash
egrep config [--global]
```

The command prompts for embedding and reranking API keys and models. By default, workspace configuration is written to `.egrep/provider.json`; global configuration is used as a fallback.

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

## What Gets Indexed

`egrep` indexes UTF-8 text files up to the configured size limit. It recognizes common code, Markdown, and text extensions, and skips binary files.

Built-in ignores include `.git/`, `.egrep/`, virtual environments, `node_modules/`, build outputs, caches, archives, PDFs, and common image formats. Patterns from `.gitignore` are also respected. `--include` and `--exclude` use gitignore-style patterns.

## Development

```bash
uv run pytest
uv build
```
