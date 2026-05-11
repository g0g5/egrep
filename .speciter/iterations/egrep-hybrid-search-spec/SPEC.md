# SPEC: egrep Hybrid Workspace Search

## Iteration

- Name: `egrep-hybrid-search-spec`
- Goal: specify the MVP for a Python CLI named `egrep` that indexes visible workspace files and returns high-confidence code/document snippets for coding agents.
- Scope: SPEC plus enough implementation guidance and acceptance criteria for the next build iteration.

## Product Behavior

`egrep` is a local workspace search CLI for coding agents.

- `egrep init` rebuilds the local index for the current workspace by default.
- `egrep "query"` performs BM25 + vector recall, reranks candidates, and returns snippets.
- `egrep config` configures workspace-local network providers for embedding and reranking by default; `egrep config --global` configures the fallback global providers.
- Local runtime/model management libraries such as `llama-cpp-python`, `transformers`, and `vllm` are out of scope.

## Commands

### `egrep init`

Rebuild the workspace index under `.egrep/`.

```bash
egrep init
egrep init --root .
egrep init --collection default
egrep init --include "**/*.py"
egrep init --exclude "dist/**"
egrep init --max-file-size 1MB
```

Required behavior:

- Fails with exit code `4` if resolved provider configuration is missing or incomplete.
- Uses current directory as default root.
- Rebuilds existing `.egrep/` index by default.
- Reads `.gitignore` plus built-in ignores.
- Skips binary/unreadable files.
- Classifies files as `code`, `markdown`, or `text`.
- Chunks by file type.
- Embeds retrieval chunks.
- Persists vector index, BM25 index, docstore/display chunks, and manifest.

### `egrep "query"`

Search the existing index.

```bash
egrep "where is config loaded"
egrep "where is config loaded" --top-k 10
egrep "where is config loaded" -v
egrep "where is config loaded" --no-rerank
```

Required behavior:

- Fails with a clear message if `.egrep/manifest.json` is missing.
- Fails with exit code `4` if resolved provider configuration is missing or incomplete.
- Performs BM25 recall and vector recall.
- Merges candidates by retrieval chunk id.
- Reranks using both child hit text and parent display text.
- Deduplicates final results by display chunk id.
- Returns minimal human-readable text with path, line range, confidence, and content by default.
- Returns detailed JSON only with `-v/--verbose`.

### `egrep config`

```bash
egrep config
egrep config --global
```

Required behavior:

- Uses `questionary` for an interactive TUI.
- Prompts separately configure the embedding provider and reranking provider. MVP supports only `OpenRouter.ai` for each provider role.
- Each provider prompt group sets provider, API key, and model.
- Defaults embedding model to `openai/text-embedding-3-small`.
- Defaults reranking model to `cohere/rerank-v3.5`.
- Embedding model must be served by the configured embedding provider.
- Reranking model must be served by the configured reranking provider.
- Persists provider configuration to workspace `.egrep/provider.json` by default.
- `egrep config --global` persists provider configuration to `~/.config/egrep/provider.json`.

## CLI Technology

- Use Python stdlib `argparse`.
- Project management: `uv`.
- Tests: `pytest`.
- Default output format: human-readable text.
- Verbose output format: detailed JSON enabled by `-v/--verbose`.

Minimal parser shape:

```python
import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="egrep")
    sub = parser.add_subparsers(dest="command")

    init = sub.add_parser("init")
    init.add_argument("--root", default=".")
    init.add_argument("--collection", default="default")
    init.add_argument("--include", action="append", default=[])
    init.add_argument("--exclude", action="append", default=[])
    init.add_argument("--max-file-size", default="1MB")

    config = sub.add_parser("config")
    config.add_argument("--global", dest="global_config", action="store_true")

    parser.add_argument("query", nargs="?")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--no-rerank", action="store_true")
    return parser
```

## Dependencies

Required runtime dependencies:

```toml
dependencies = [
  "chromadb",
  "llama-index",
  "llama-index-vector-stores-chroma",
  "llama-index-retrievers-bm25",
  "PyStemmer",
  "requests",
  "pathspec",
  "questionary",
]
```

Required dev dependencies:

```toml
[dependency-groups]
dev = [
  "pytest",
  "responses",
  "python-dotenv",
]
```

Do not add local model runtime dependencies in this iteration.

## Workspace Discovery

Built-in ignores:

```text
.git/
.egrep/
.speciter/
.venv/
venv/
env/
node_modules/
dist/
build/
__pycache__/
*.pyc
*.pyo
*.so
*.dylib
*.dll
*.png
*.jpg
*.jpeg
*.gif
*.webp
*.pdf
*.zip
*.tar
*.gz
```

Use `pathspec.GitIgnoreSpec` for `.gitignore` semantics.

```python
from pathlib import Path
from pathspec import GitIgnoreSpec


def visible_files(root: Path, extra_ignores: list[str]) -> list[Path]:
    lines = [".git/", ".egrep/", ".speciter/", "node_modules/", "__pycache__/"]
    gitignore = root / ".gitignore"
    if gitignore.exists():
        lines.extend(gitignore.read_text(encoding="utf-8", errors="ignore").splitlines())
    lines.extend(extra_ignores)
    spec = GitIgnoreSpec.from_lines(lines)

    files = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if not spec.match_file(rel):
            files.append(path)
    return files
```

## File Types

`code` extensions:

```text
.py .js .ts .tsx .jsx .go .rs .java .c .cpp .h .hpp .sh .toml .yaml .yml .json
```

`markdown` extensions:

```text
.md .mdx .rst
```

`text` extensions:

```text
.txt .log .ini .cfg
```

Files with unknown extensions may be indexed as `text` only if they are UTF-8 decodable and below `--max-file-size`.

## Chunk Model

There are two logical chunk roles:

- `retrieval_chunk`: embedded and searched.
- `display_chunk`: returned to the user.

Metadata required on every retrieval chunk:

```json
{
  "chunk_id": "stable retrieval chunk id",
  "display_chunk_id": "stable parent-or-self display chunk id",
  "parent_chunk_id": "parent id or null",
  "chunk_role": "parent|child|standalone",
  "type": "code|markdown|text",
  "path": "relative/path.py",
  "start_line": 10,
  "end_line": 40,
  "display_start_line": 8,
  "display_end_line": 90,
  "content_hash": "sha256",
  "file_hash": "sha256"
}
```

Persist display chunks in `.egrep/docstore.jsonl` or an equivalent simple local store keyed by `display_chunk_id`.

### Code Chunking

Use LlamaIndex `CodeSplitter`.

- Function/class/method chunks are preferred display chunks.
- If a function/class/method exceeds max length, split it into overlapped retrieval child chunks.
- If any child chunk is matched, return the full parent function/class/method display chunk.

```python
from llama_index.core import Document
from llama_index.core.node_parser import CodeSplitter


doc = Document(text=source_text, metadata={"path": "src/search.py", "type": "code"})
nodes = CodeSplitter(
    language="python",
    chunk_lines=120,
    chunk_lines_overlap=20,
    max_chars=4000,
).get_nodes_from_documents([doc])
```

### Markdown Chunking

Use LlamaIndex `MarkdownNodeParser`.

- Treat Markdown as structured text similar to code.
- Section chunks are display chunks.
- Overlong sections are split into overlapped retrieval child chunks.
- If any child chunk is matched, return the full parent section display chunk.

```python
from llama_index.core import Document
from llama_index.core.node_parser import MarkdownNodeParser


doc = Document(text=markdown_text, metadata={"path": "README.md", "type": "markdown"})
nodes = MarkdownNodeParser().get_nodes_from_documents([doc])
```

### Text Chunking

Use overlapped chunking only.

- Text chunks are standalone retrieval and display chunks.
- Matching a text chunk returns that same chunk.
- Default target: 120 lines or approximately 800 tokens.
- Default overlap: 20 lines or approximately 100 tokens.

## Provider Configuration

Provider configuration is workspace-local by default, with an optional global fallback.

- `egrep config` writes `.egrep/provider.json` under the current workspace.
- `egrep config --global` writes `~/.config/egrep/provider.json`.
- `egrep init` and `egrep "query"` first read workspace `.egrep/provider.json`.
- If workspace `.egrep/provider.json` is missing, `egrep init` and `egrep "query"` use `~/.config/egrep/provider.json`.
- If the resolved provider configuration is missing or incomplete, `egrep init` and `egrep "query"` fail with exit code `4`.
- MVP supports only `OpenRouter.ai` for both embedding and reranking provider roles.
- OpenRouter base URL is fixed to `https://openrouter.ai/api/v1`.
- Embedding and reranking provider settings are configured separately.
- Embedding model must be available from the configured embedding provider.
- Reranking model must be available from the configured reranking provider.
- Do not read provider configuration from environment variables.

`.egrep/provider.json` or `~/.config/egrep/provider.json`:

```json
{
  "embedding": {
    "provider": "openrouter",
    "base_url": "https://openrouter.ai/api/v1",
    "api_key": "...",
    "model": "openai/text-embedding-3-small"
  },
  "reranking": {
    "provider": "openrouter",
    "base_url": "https://openrouter.ai/api/v1",
    "api_key": "...",
    "model": "cohere/rerank-v3.5"
  }
}
```

Config TUI shape:

```python
import questionary


embedding_provider = questionary.select(
    "Embedding provider",
    choices=["OpenRouter.ai"],
).ask()
embedding_api_key = questionary.password("Embedding API key").ask()
embedding_model = questionary.text(
    "Embedding model",
    default="openai/text-embedding-3-small",
).ask()
reranking_provider = questionary.select(
    "Reranking provider",
    choices=["OpenRouter.ai"],
).ask()
reranking_api_key = questionary.password("Reranking API key").ask()
reranking_model = questionary.text(
    "Reranking model",
    default="cohere/rerank-v3.5",
).ask()
```

Use `requests` with explicit timeout and clear provider errors.

```python
import requests

TIMEOUT = (5, 60)


class ProviderHTTPError(RuntimeError):
    pass


def post_json(url: str, api_key: str, body: dict) -> dict:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        response = requests.post(url, headers=headers, json=body, timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as exc:
        raise ProviderHTTPError(f"provider request failed: {exc}") from exc


def embed(base_url: str, api_key: str, model: str, texts: list[str]) -> list[list[float]]:
    data = post_json(
        f"{base_url.rstrip('/')}/embeddings",
        api_key,
        {"model": model, "input": texts},
    )
    return [item["embedding"] for item in data["data"]]
```

Batch embeddings. Default batch size: `32` retrieval chunks.

## Vector Store

Use persistent ChromaDB at `.egrep/chroma`.

```python
import chromadb


client = chromadb.PersistentClient(path=".egrep/chroma")
collection = client.get_or_create_collection(
    name="egrep_default",
    metadata={"purpose": "workspace-index"},
    configuration={"hnsw": {"space": "cosine"}},
)

collection.upsert(
    ids=[record["id"] for record in records],
    documents=[record["text"] for record in records],
    embeddings=[record["embedding"] for record in records],
    metadatas=[record["metadata"] for record in records],
)
```

LlamaIndex Chroma integration may be used where it simplifies retrieval:

```python
from llama_index.vector_stores.chroma import ChromaVectorStore


vector_store = ChromaVectorStore.from_params(
    collection_name="egrep_default",
    persist_dir=".egrep/chroma",
    collection_kwargs={"configuration": {"hnsw": {"space": "cosine"}}},
)
```

## BM25

Use LlamaIndex BM25 retriever and persist it under `.egrep/bm25`.

```python
import Stemmer
from llama_index.retrievers.bm25 import BM25Retriever


bm25 = BM25Retriever.from_defaults(
    nodes=retrieval_nodes,
    similarity_top_k=50,
    stemmer=Stemmer.Stemmer("english"),
    language="english",
)
bm25.persist(".egrep/bm25")

bm25 = BM25Retriever.from_persist_dir(".egrep/bm25")
```

## Retrieval Pipeline

Default parameters:

```text
bm25_top_k = 50
vector_top_k = 50
candidate_top_k = 80
final_top_k = 10
```

Algorithm:

1. Embed query.
2. Query Chroma with query embedding for `vector_top_k` retrieval chunks.
3. Query BM25 for `bm25_top_k` retrieval chunks.
4. Normalize BM25 and vector scores independently to `[0, 1]`.
5. Merge by `chunk_id`.
6. Compute `hybrid_score = 0.5 * normalized_bm25 + 0.5 * normalized_vector`.
7. Keep top `candidate_top_k` by `hybrid_score`.
8. Build rerank documents containing both child hit and parent display text.
9. Rerank unless `--no-rerank` is set.
10. Map each candidate to `display_chunk_id`.
11. Deduplicate by `display_chunk_id`; keep the best-scoring child hit.
12. Return top `final_top_k` display chunks.

Rerank document shape:

```json
{
  "id": "retrieval-chunk-id",
  "text": "Matched child chunk:\n...\n\nParent display chunk:\n..."
}
```

## Reranking

Use the configured reranking provider.

```python
def rerank(base_url: str, api_key: str, model: str, query: str, documents: list[dict], top_n: int):
    return post_json(
        f"{base_url.rstrip('/')}/rerank",
        api_key,
        {
            "model": model,
            "query": query,
            "documents": documents,
            "top_n": top_n,
        },
    )
```

Reranker failure policy:

- Default: fail the command with provider error.
- `--no-rerank`: skip reranking and sort by `hybrid_score`.
- A future `--fallback-no-rerank` flag may be added later; do not implement unless requested.

## Output

Default output is minimal human-readable text. It is the only non-verbose output mode.

```text
1. src/example.py:12-96 confidence=0.91
<display chunk content>

2. README.md:20-45 confidence=0.84
<display chunk content>
```

`-v/--verbose` returns detailed JSON. There is no separate `--json` mode.

```json
{
  "query": "where is config loaded",
  "results": [
    {
      "path": "src/example.py",
      "start_line": 12,
      "end_line": 96,
      "confidence": 0.91,
      "scores": {
        "bm25_score": 8.42,
        "vector_score": 0.77,
        "hybrid_score": 0.81,
        "rerank_score": 0.91
      },
      "matched_chunks": [
        {
          "chunk_id": "child-1",
          "start_line": 40,
          "end_line": 58,
          "bm25_score": 8.42,
          "vector_score": 0.77,
          "hybrid_score": 0.81,
          "rerank_score": 0.91
        }
      ],
      "content": "..."
    }
  ]
}
```

Confidence rules:

- With reranker: `confidence = normalized rerank_score`.
- Without reranker: `confidence = hybrid_score`.
- If multiple children map to one display chunk, use the highest confidence child.

## Index Layout

```text
.egrep/
  provider.json  # optional; created by `egrep config`
  chroma/
  bm25/
  docstore.jsonl
  manifest.json
```

`manifest.json`:

```json
{
  "version": 1,
  "root": "/absolute/workspace/path",
  "created_at": "2026-05-10T00:00:00Z",
  "collection": "default",
  "embedding_model": "openai/text-embedding-3-small",
  "rerank_model": "cohere/rerank-v3.5",
  "file_count": 120,
  "retrieval_chunk_count": 1234,
  "display_chunk_count": 456
}
```

## Configuration

- Provider configuration comes from workspace `.egrep/provider.json` when it exists.
- If workspace `.egrep/provider.json` is missing, provider configuration falls back to `~/.config/egrep/provider.json`.
- Provider configuration is created and updated by `egrep config` in workspace `.egrep/provider.json` by default.
- Global provider configuration is created and updated by `egrep config --global` in `~/.config/egrep/provider.json`.
- `egrep init` and `egrep "query"` fail with exit code `4` when resolved provider configuration is missing or incomplete.
- Command behavior still comes from CLI arguments, such as `--top-k` and `--no-rerank`.
- Built-in defaults apply only to non-secret values prompted by `egrep config`, such as default model names.

## Exit Codes

```text
0 success
1 unexpected error
2 invalid CLI usage
3 index not found
4 provider configuration missing
5 provider API error
6 filesystem/index write error
```

## Tests

Use `pytest` with `tmp_path`, `monkeypatch`, and `responses` for `requests` mocks.

Use `python-dotenv` only as a development/test dependency. Tests that intentionally hit the real OpenRouter API may load `OPENROUTER_API_KEY` from the project root `.env`; they must be skipped when the variable is unavailable. Unit tests must not require real network calls.

```python
def test_uses_current_directory(monkeypatch, tmp_path):
    (tmp_path / "input.txt").write_text("needle\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert (tmp_path / "input.txt").exists()
```

```python
import responses


@responses.activate
def test_embedding_provider_posts_json():
    responses.post(
        "https://openrouter.ai/api/v1/embeddings",
        json={"data": [{"embedding": [0.1, 0.2]}]},
        status=200,
    )
    vectors = embed("https://openrouter.ai/api/v1", "key", "model", ["hello"])
    assert vectors == [[0.1, 0.2]]
```

Acceptance tests:

- `egrep config` writes `.egrep/provider.json` with separate embedding and reranking provider settings.
- `egrep config --global` writes `~/.config/egrep/provider.json` with separate embedding and reranking provider settings.
- `egrep init` and `egrep "query"` use workspace `.egrep/provider.json` when present.
- `egrep init` and `egrep "query"` fall back to `~/.config/egrep/provider.json` when workspace `.egrep/provider.json` is missing.
- `egrep init` creates `.egrep/manifest.json`, `.egrep/chroma/`, `.egrep/bm25/`, and docstore.
- `.git`, `.egrep`, `.speciter`, `node_modules`, binary files, and ignored files are skipped.
- Code files use LlamaIndex code chunking.
- Markdown files use section chunking.
- Text files use overlapped chunking.
- Overlong code and markdown display chunks create child retrieval chunks.
- Matching a code child returns the parent function/class display chunk.
- Matching a markdown child returns the parent section display chunk.
- Multiple child hits under the same display chunk appear once in final results.
- Default output is minimal text and includes only path, line range, confidence, and content.
- `-v/--verbose` output parses with `json.loads()` and includes BM25, vector, hybrid, rerank, and matched child details.
- Query without index exits with code `3`.
- Missing or incomplete resolved provider config exits with code `4` for both `egrep init` and `egrep "query"`.
- Provider HTTP failure exits with code `5`.

## MVP Done Criteria

- `uv run egrep init` indexes a small fixture workspace.
- `uv run egrep "query"` returns ranked snippets with file paths and confidence.
- `uv run egrep "query" -v` returns the verbose JSON schema.
- Unit tests do not require real network calls.
- No local model runtime dependencies are introduced.
- `uv run pytest` passes.

## Research Reports

- `.speciter/docs/chromadb.md`
- `.speciter/docs/llama-index.md`
- `.speciter/docs/llama-index-vector-stores-chroma.md`
- `.speciter/docs/requests.md`
- `.speciter/docs/pathspec.md`
- `.speciter/docs/pytest.md`
