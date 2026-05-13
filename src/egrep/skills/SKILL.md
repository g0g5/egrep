---
name: egrep
description: >
  Hybrid workspace code search using egrep. Use this whenever you need to find
  code, locate definitions, search for patterns, or answer semantic questions
  about a codebase that has an egrep index. egrep combines BM25 keyword search
  with vector semantic search and optional neural reranking for precise
  retrieval.
---

# egrep Query

`egrep` is a hybrid workspace search CLI. The default command is **query** —
pass a search string positionally, no subcommand needed.

## Prerequisites

Before running a query, two things must exist in the current directory:

- `.egrep/manifest.json` — the index manifest (created by `egrep init`)
- Provider config — either `.egrep/provider.json` (workspace) or
  `~/.config/egrep/provider.json` (global), created by `egrep config`

If the index is missing, the tool will error with "index not found; run
`egrep init` first" and exit code 3. If the provider config is missing, it
errors with exit code 4. Do not attempt to fix these — tell the user to run
`egrep init` or `egrep config` as appropriate.

## Usage

```
egrep "your search query" [--top-k N] [--no-rerank] [-v | --verbose]
```

- **query** (positional, required): the search string.
- **--top-k N**: number of results to return (default: 10).
- **--no-rerank**: skip the neural reranking step; results use the hybrid
  BM25+vector score directly. Useful for speed or when the rerank provider is
  unavailable.
- **-v / --verbose**: output results as indented JSON instead of the default
  human-readable format.

## Output Formats

### Default (human-readable)

```
1. src/file.py:10-25 confidence=0.92
def my_function():
    ...

2. src/other.py:42-55 confidence=0.81
class MyClass:
    ...
```

Each result shows rank, `path:start-end`, a confidence score (0–1), and the
chunk text.

### Verbose (`-v`)

JSON with the query string and an array of results, each containing:

- `path`, `start_line`, `end_line`, `content` — the display chunk location and text
- `confidence` — final score (rerank-normalised if reranking, otherwise hybrid)
- `scores` — breakdown: `bm25_score`, `vector_score`, `hybrid_score`,
  `rerank_score`
- `matched_chunks` — the specific child chunk(s) that matched, with their own
  line ranges and scores

## When to Use egrep

Use egrep when you need to understand where something lives or how it works in
a codebase:

- "Where is authentication handled?"
- "Find the function that parses command-line arguments"
- "How does error handling work in this project?"
- "Search for all files related to database connections"
- "What code handles the login flow?"

egrep is particularly effective for questions that combine keywords with
conceptual intent, since the hybrid approach covers both exact matches and
semantic similarity.

## When NOT to Use egrep

- To find exact string literals or grep-like pattern matches — use `rg` or
  `grep` instead. egrep searches on chunked text and metadata, not raw file
  bytes.
- When the index hasn't been built yet.
- For tasks better served by reading specific known files directly.

## Error Handling

| Exit code | Cause |
|-----------|-------|
| 3 | Index not found (`.egrep/manifest.json` missing) |
| 4 | Provider config missing or invalid |
| 5 | Provider API error (network, auth, bad response) |
| 1 | Unexpected error |

If egrep returns a non-zero exit code, inspect the stderr message and act
accordingly. Do not retry the same failing query without changing something.
