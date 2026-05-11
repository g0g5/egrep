# ChromaDB Local Persistent Collections

Sources: [Python Collection API](https://docs.trychroma.com/reference/python/collection), [Getting Started](https://docs.trychroma.com/docs/overview/getting-started), [Chroma Clients](https://cookbook.chromadb.dev/core/clients/), [Collections Cookbook](https://cookbook.chromadb.dev/core/collections/)

## Install

```bash
pip install chromadb
```

## Persistent Local Client

```python
import chromadb

client = chromadb.PersistentClient(path=".egrep/chroma")
collection = client.get_or_create_collection(
    name="egrep_workspace",
    metadata={"purpose": "workspace-index"},
    configuration={"hnsw": {"space": "cosine"}},
)
```

## Add Documents With Explicit Embeddings

```python
records = [
    {
        "id": "src/main.py:1:80",
        "text": "def search_workspace(query): ...",
        "embedding": [0.012, -0.034, 0.056],
        "metadata": {
            "path": "src/main.py",
            "language": "python",
            "kind": "function",
            "start_line": 1,
            "end_line": 80,
            "mtime": 1778371200,
        },
    }
]

collection.upsert(
    ids=[r["id"] for r in records],
    documents=[r["text"] for r in records],
    embeddings=[r["embedding"] for r in records],
    metadatas=[r["metadata"] for r in records],
)
```

## Add Documents Using Chroma's Embedding Function

```python
collection.upsert(
    ids=["README.md:1:40", "src/index.ts:10:32"],
    documents=["Project usage and CLI examples", "export async function indexWorkspace"],
    metadatas=[
        {"path": "README.md", "language": "markdown", "kind": "docs"},
        {"path": "src/index.ts", "language": "typescript", "kind": "function"},
    ],
)
```

## Query With Explicit Query Embedding

```python
results = collection.query(
    query_embeddings=[[0.021, -0.044, 0.061]],
    n_results=8,
    where={"language": "python"},
    include=["documents", "metadatas", "distances"],
)

for id_, doc, meta, dist in zip(
    results["ids"][0],
    results["documents"][0],
    results["metadatas"][0],
    results["distances"][0],
):
    print(id_, dist, meta["path"], doc[:120])
```

## Query With Text

```python
results = collection.query(
    query_texts=["workspace indexing code"],
    n_results=5,
    where={"kind": "function"},
    include=["documents", "metadatas", "distances"],
)
```

## Metadata Filters

```python
collection.query(
    query_texts=["test runner"],
    where={"$and": [{"language": "python"}, {"kind": "test"}]},
    n_results=10,
)

collection.get(
    where={"path": "src/main.py"},
    include=["documents", "metadatas"],
)
```

## Update Changed Files

```python
collection.delete(where={"path": "src/main.py"})

collection.add(
    ids=new_ids,
    documents=new_chunks,
    embeddings=new_embeddings,
    metadatas=new_metadatas,
)
```

## Notes

```python
# add(): fails if an ID exists.
# upsert(): create-or-update; safer for incremental indexing.
# query(): returns batched columnar results: results["ids"][query_index][hit_index].
# ids are always returned; documents/metadatas/distances depend on include.
# PersistentClient stores local data under path and creates it if missing.
```
