# llama-index-vector-stores-chroma

Latest useful package: `llama-index-vector-stores-chroma`.

Install:

```bash
uv add llama-index-vector-stores-chroma chromadb
```

Persistent collection:

```python
import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore

PERSIST_DIR = ".egrep/chroma"
COLLECTION = "egrep_vector_index"

chroma_client = chromadb.PersistentClient(path=PERSIST_DIR)
chroma_collection = chroma_client.get_or_create_collection(
    COLLECTION,
    configuration={"hnsw": {"space": "cosine"}},
)
vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
```

Equivalent LlamaIndex constructor:

```python
from llama_index.vector_stores.chroma import ChromaVectorStore

vector_store = ChromaVectorStore.from_params(
    collection_name="egrep_vector_index",
    persist_dir=".egrep/chroma",
    collection_kwargs={"configuration": {"hnsw": {"space": "cosine"}}},
)
```

Add LlamaIndex nodes with metadata:

```python
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.schema import TextNode

nodes = [
    TextNode(
        id_="src/search.py:10:24",
        text="def grep(pattern, path): ...",
        metadata={
            "repo": "egrep",
            "path": "src/search.py",
            "lang": "python",
            "symbol": "grep",
            "kind": "function",
        },
    )
]

storage_context = StorageContext.from_defaults(vector_store=vector_store)
index = VectorStoreIndex(nodes, storage_context=storage_context)
```

Open existing persistent index:

```python
from llama_index.core import VectorStoreIndex
from llama_index.core import StorageContext

storage_context = StorageContext.from_defaults(vector_store=vector_store)
index = VectorStoreIndex.from_vector_store(
    vector_store,
    storage_context=storage_context,
)
```

Query with LlamaIndex metadata filters:

```python
from llama_index.core.vector_stores import (
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
)

filters = MetadataFilters(filters=[
    MetadataFilter(key="repo", operator=FilterOperator.EQ, value="egrep"),
    MetadataFilter(key="path", operator=FilterOperator.EQ, value="src/search.py"),
    MetadataFilter(key="kind", operator=FilterOperator.EQ, value="function"),
])

retriever = index.as_retriever(similarity_top_k=8, filters=filters)
matches = retriever.retrieve("regex search implementation")
```

Query with Chroma-native `where`:

```python
from llama_index.core.vector_stores import VectorStoreQuery

query = VectorStoreQuery(
    query_embedding=embed_model.get_text_embedding("regex search implementation"),
    similarity_top_k=8,
)

result = vector_store.query(
    query,
    where={"$and": [
        {"repo": {"$eq": "egrep"}},
        {"lang": {"$eq": "python"}},
    ]},
)
```

MMR retrieval:

```python
query_engine = index.as_query_engine(
    similarity_top_k=8,
    vector_store_query_mode="mmr",
    vector_store_kwargs={"mmr_threshold": 0.5},
)
response = query_engine.query("where is indexing updated?")
```

Fetch or delete by metadata:

```python
filters = MetadataFilters(filters=[
    MetadataFilter(key="path", operator=FilterOperator.EQ, value="src/search.py"),
])

nodes = vector_store.get_nodes(node_ids=None, filters=filters)
vector_store.delete_nodes(node_ids=None, filters=filters)
```

Chroma direct operations:

```python
chroma_collection.count()
chroma_collection.peek(limit=5)
chroma_collection.delete(where={"path": "src/search.py"})
```

Notes:

- `ChromaVectorStore` stores embeddings, text, and flat metadata in a Chroma collection.
- `PersistentClient(path=...)` keeps the collection on disk.
- Collection HNSW distance metric must be chosen when the collection is created.
- LlamaIndex converts `MetadataFilters` into Chroma `where` filters.
- Do not pass both `query.filters` and `where` to `vector_store.query()`.

Sources:

- [LlamaIndex Chroma API Reference](https://docs.llamaindex.ai/en/stable/api_reference/storage/vector_store/chroma/)
- [LlamaIndex Chroma metadata filter example](https://docs.llamaindex.ai/en/v0.10.22/examples/vector_stores/chroma_metadata_filter/)
- [Chroma Cookbook: Collections](https://cookbook.chromadb.dev/core/collections/)
- [Chroma Docs](https://docs.trychroma.com/)
