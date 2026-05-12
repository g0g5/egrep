from __future__ import annotations

import argparse
import json
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .config import resolve_provider_config
from .chunking import RetrievalChunk, chunk_workspace_files, write_docstore
from .discovery import discover_workspace_files
from .errors import EgrepError, IndexWriteError
from .providers import embed_batched


MANIFEST_VERSION = 1


@dataclass(frozen=True)
class InitProgress:
    stage: str
    current: int | None = None
    total: int | None = None
    path: str | None = None
    message: str | None = None


ProgressCallback = Callable[[InitProgress], None]


def build_index(
    root: Path,
    *,
    collection: str,
    includes: list[str],
    excludes: list[str],
    max_file_size: str,
    provider_config: dict,
    progress: ProgressCallback | None = None,
) -> dict:
    index_dir = root / ".egrep"
    _emit(progress, InitProgress("prepare", current=0, total=1, message="preparing index"))
    _prepare_rebuild(index_dir)
    _emit(progress, InitProgress("prepare", current=1, total=1, message="prepared index"))

    workspace_files = discover_workspace_files(
        root,
        includes=includes,
        excludes=excludes,
        max_file_size=max_file_size,
        progress=lambda path, current, total: _emit(
            progress,
            InitProgress(
                "discover",
                current=current,
                total=total,
                path=_relative_progress_path(root, path),
            ),
        ),
    )
    chunked = chunk_workspace_files(
        workspace_files,
        progress=lambda workspace_file, current, total: _emit(
            progress,
            InitProgress(
                "chunk",
                current=current,
                total=total,
                path=workspace_file.relative_path if workspace_file is not None else None,
            ),
        ),
    )

    retrieval_chunks = chunked.retrieval_chunks
    if retrieval_chunks:
        for index, chunk in enumerate(retrieval_chunks, start=1):
            _emit(progress, InitProgress("embed", current=index, total=len(retrieval_chunks), path=chunk.path))
    else:
        _emit(progress, InitProgress("embed", current=0, total=0))

    embeddings = embed_batched(
        provider_config["embedding"]["base_url"],
        provider_config["embedding"]["api_key"],
        provider_config["embedding"]["model"],
        [chunk.text for chunk in retrieval_chunks],
    )
    _emit(progress, InitProgress("write_chroma", current=0, total=1, message="writing chroma"))
    _write_chroma(index_dir / "chroma", collection, retrieval_chunks, embeddings)
    _emit(progress, InitProgress("write_chroma", current=1, total=1, message="wrote chroma"))

    _emit(progress, InitProgress("write_bm25", current=0, total=1, message="writing bm25"))
    _write_bm25(index_dir / "bm25", retrieval_chunks)
    _emit(progress, InitProgress("write_bm25", current=1, total=1, message="wrote bm25"))

    write_docstore(
        index_dir / "docstore.jsonl",
        chunked.display_chunks,
        progress=lambda chunk, current, total: _emit(
            progress,
            InitProgress(
                "write_docstore",
                current=current,
                total=total,
                path=chunk.path if chunk is not None else None,
            ),
        ),
    )

    manifest = {
        "version": MANIFEST_VERSION,
        "root": str(root),
        "created_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "collection": collection,
        "embedding_model": provider_config["embedding"]["model"],
        "rerank_model": provider_config["reranking"].get("model"),
        "file_count": len(workspace_files),
        "retrieval_chunk_count": len(chunked.retrieval_chunks),
        "display_chunk_count": len(chunked.display_chunks),
    }
    _emit(progress, InitProgress("write_manifest", current=0, total=1, message="writing manifest"))
    (index_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _emit(progress, InitProgress("write_manifest", current=1, total=1, message="wrote manifest"))
    return manifest


def run_init(args: argparse.Namespace, progress: ProgressCallback | None = None) -> int:
    root = Path(args.root).resolve()
    provider_config = resolve_provider_config(root)
    try:
        manifest = build_index(
            root,
            collection=args.collection,
            includes=args.include,
            excludes=args.exclude,
            max_file_size=args.max_file_size,
            provider_config=provider_config,
            progress=progress,
        )
    except EgrepError:
        raise
    except Exception as exc:
        raise IndexWriteError(f"failed to write index: {exc}") from exc

    print(
        "indexed "
        f"{manifest['file_count']} files, "
        f"{manifest['retrieval_chunk_count']} retrieval chunks, "
        f"{manifest['display_chunk_count']} display chunks"
    )
    return 0


def _prepare_rebuild(index_dir: Path) -> None:
    index_dir.mkdir(parents=True, exist_ok=True)
    for name in ("chroma", "bm25"):
        path = index_dir / name
        if path.exists():
            shutil.rmtree(path)
    for name in ("docstore.jsonl", "manifest.json"):
        path = index_dir / name
        if path.exists():
            path.unlink()


def _emit(progress: ProgressCallback | None, event: InitProgress) -> None:
    if progress is not None:
        progress(event)


def _relative_progress_path(root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _write_chroma(
    persist_dir: Path,
    collection: str,
    chunks: list[RetrievalChunk],
    embeddings: list[list[float]],
) -> None:
    import chromadb

    persist_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(persist_dir))
    chroma_collection = client.get_or_create_collection(
        name=_chroma_collection_name(collection),
        metadata={"purpose": "workspace-index"},
        configuration={"hnsw": {"space": "cosine"}},
    )
    if not chunks:
        return

    chroma_collection.upsert(
        ids=[chunk.chunk_id for chunk in chunks],
        documents=[chunk.text for chunk in chunks],
        embeddings=embeddings,
        metadatas=[_chroma_metadata(chunk.metadata) for chunk in chunks],
    )


def _write_bm25(persist_dir: Path, chunks: list[RetrievalChunk]) -> None:
    import Stemmer
    from llama_index.core.schema import TextNode
    from llama_index.retrievers.bm25 import BM25Retriever

    persist_dir.mkdir(parents=True, exist_ok=True)
    if not chunks:
        return

    nodes = [
        TextNode(
            id_=chunk.chunk_id,
            text=chunk.text,
            metadata=chunk.metadata,
        )
        for chunk in chunks
    ]
    bm25 = BM25Retriever.from_defaults(
        nodes=nodes,
        similarity_top_k=50,
        stemmer=Stemmer.Stemmer("english"),
        language="english",
    )
    bm25.persist(str(persist_dir))


def _chroma_collection_name(collection: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", collection).strip("._-") or "default"
    name = f"egrep_{name}"
    if len(name) > 63:
        name = name[:63].rstrip("._-")
    return name


def _chroma_metadata(metadata: dict[str, str | int | None]) -> dict[str, str | int]:
    return {key: ("" if value is None else value) for key, value in metadata.items()}
