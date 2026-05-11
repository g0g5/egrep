# LlamaIndex Notes For egrep Code Search

Latest docs use `llama_index.core` for core types, `llama-index-retrievers-bm25` for BM25, and retriever fusion for hybrid retrieval.

## Install

```bash
pip install llama-index llama-index-retrievers-bm25 PyStemmer
```

## Code Chunking

```python
from llama_index.core import Document
from llama_index.core.node_parser import CodeSplitter

doc = Document(
    text=source_text,
    metadata={"path": "src/search.rs", "language": "rust"},
)

nodes = CodeSplitter(
    language="rust",
    chunk_lines=80,
    chunk_lines_overlap=20,
    max_chars=4000,
).get_nodes_from_documents([doc])
```

## Markdown Section Chunking

```python
from llama_index.core import Document
from llama_index.core.node_parser import MarkdownNodeParser

doc = Document(text=markdown_text, metadata={"path": "README.md"})
nodes = MarkdownNodeParser().get_nodes_from_documents([doc])
```

## Metadata On Nodes

```python
from llama_index.core.schema import TextNode

node = TextNode(
    text=chunk,
    metadata={
        "repo": "egrep",
        "path": "src/search.rs",
        "language": "rust",
        "symbol": "search_files",
        "start_line": 42,
        "end_line": 118,
        "git_sha": "abc123",
    },
    excluded_embed_metadata_keys=["git_sha"],
    excluded_llm_metadata_keys=["git_sha"],
)
```

## Vector Index + Metadata Filters

```python
from llama_index.core import VectorStoreIndex
from llama_index.core.vector_stores import MetadataFilter, MetadataFilters

index = VectorStoreIndex(nodes)

retriever = index.as_retriever(
    similarity_top_k=20,
    filters=MetadataFilters(filters=[
        MetadataFilter(key="language", value="rust"),
        MetadataFilter(key="repo", value="egrep"),
    ]),
)

hits = retriever.retrieve("ripgrep ignore glob walker")
```

## BM25 Retrieval

```python
import Stemmer
from llama_index.retrievers.bm25 import BM25Retriever

bm25 = BM25Retriever.from_defaults(
    nodes=nodes,
    similarity_top_k=20,
    stemmer=Stemmer.Stemmer("english"),
    language="english",
)

hits = bm25.retrieve("fn search_files ignore_patterns")
bm25.persist(".cache/egrep-bm25")
bm25 = BM25Retriever.from_persist_dir(".cache/egrep-bm25")
```

## BM25 With Docstore

```python
import Stemmer
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.retrievers.bm25 import BM25Retriever

docstore = SimpleDocumentStore()
docstore.add_documents(nodes)

bm25 = BM25Retriever.from_defaults(
    docstore=docstore,
    similarity_top_k=20,
    stemmer=Stemmer.Stemmer("english"),
    language="english",
)
```

## Hybrid Retrieval: Vector + BM25 Fusion

```python
from llama_index.core import VectorStoreIndex
from llama_index.core.retrievers import QueryFusionRetriever
from llama_index.retrievers.bm25 import BM25Retriever

index = VectorStoreIndex(nodes)
vector = index.as_retriever(similarity_top_k=20)
bm25 = BM25Retriever.from_defaults(nodes=nodes, similarity_top_k=20)

hybrid = QueryFusionRetriever(
    [vector, bm25],
    similarity_top_k=20,
    num_queries=1,
    mode="reciprocal_rerank",
    use_async=True,
)

hits = hybrid.retrieve("where are regex matches ranked")
```

## Parent-Child Retrieval / Auto-Merging

```python
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.node_parser import HierarchicalNodeParser, get_leaf_nodes
from llama_index.core.retrievers import AutoMergingRetriever
from llama_index.core.storage.docstore import SimpleDocumentStore

all_nodes = HierarchicalNodeParser.from_defaults(
    chunk_sizes=[4096, 1024, 256]
).get_nodes_from_documents(documents)

leaf_nodes = get_leaf_nodes(all_nodes)
docstore = SimpleDocumentStore()
docstore.add_documents(all_nodes)

storage = StorageContext.from_defaults(docstore=docstore)
index = VectorStoreIndex(leaf_nodes, storage_context=storage)
base = index.as_retriever(similarity_top_k=12)
retriever = AutoMergingRetriever(base, storage, verbose=False)

hits = retriever.retrieve("how are child match chunks merged to file context")
```

## Suggested egrep Pipeline

```python
from pathlib import Path
from llama_index.core import Document, VectorStoreIndex
from llama_index.core.node_parser import CodeSplitter, MarkdownNodeParser
from llama_index.core.retrievers import QueryFusionRetriever
from llama_index.retrievers.bm25 import BM25Retriever

def parse_file(path: Path):
    text = path.read_text(errors="ignore")
    meta = {"repo": "egrep", "path": str(path), "ext": path.suffix}
    doc = Document(text=text, metadata=meta)
    if path.suffix == ".md":
        return MarkdownNodeParser().get_nodes_from_documents([doc])
    return CodeSplitter(language="rust", chunk_lines=80).get_nodes_from_documents([doc])

nodes = [node for path in paths for node in parse_file(path)]

vector = VectorStoreIndex(nodes).as_retriever(similarity_top_k=30)
bm25 = BM25Retriever.from_defaults(nodes=nodes, similarity_top_k=30)
search = QueryFusionRetriever([vector, bm25], mode="reciprocal_rerank", num_queries=1)

results = search.retrieve("symbol exact terms plus semantic intent")
```

## Sources

- [Node Parser Modules](https://docs.llamaindex.ai/en/stable/module_guides/loading/node_parsers/modules/)
- [BM25 Retriever](https://docs.llamaindex.ai/en/stable/examples/retrievers/bm25_retriever/)
- [AutoMergingRetriever API](https://docs.llamaindex.ai/en/stable/api_reference/retrievers/auto_merging/)
- [AutoMergingRetriever Pack](https://docs.llamaindex.ai/en/stable/api_reference/packs/auto_merging_retriever/)
- [QueryFusionRetriever API](https://docs.llamaindex.ai/en/v0.10.23/api_reference/retrievers/query_fusion/)
