from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .config import resolve_provider_config
from .chunking import DisplayChunk, read_docstore
from .errors import IndexNotFoundError, ProviderAPIError
from .indexing import _chroma_collection_name
from .output import format_human, format_verbose
from .providers import embed, rerank


BM25_TOP_K = 50
VECTOR_TOP_K = 50
CANDIDATE_TOP_K = 80


@dataclass
class Candidate:
    chunk_id: str
    text: str
    metadata: dict[str, Any]
    bm25_score: float | None = None
    vector_score: float | None = None
    hybrid_score: float = 0.0
    rerank_score: float | None = None
    confidence: float = 0.0


@dataclass(frozen=True)
class SearchResult:
    display_chunk: DisplayChunk
    candidate: Candidate


def run_query(args: argparse.Namespace) -> int:
    root = Path.cwd().resolve()
    manifest = load_manifest(root)
    provider_config = resolve_provider_config(root)
    results = search(
        root,
        args.query,
        top_k=args.top_k,
        no_rerank=args.no_rerank,
        provider_config=provider_config,
        manifest=manifest,
    )
    if getattr(args, "verbose", False):
        output = format_verbose(args.query, results)
    else:
        output = format_human(results)
    if output:
        print(output)
    return 0


def load_manifest(root: Path) -> dict[str, Any]:
    path = root / ".wegrep" / "manifest.json"
    if not path.exists():
        raise IndexNotFoundError("index not found; run `wegrep init` first")
    return json.loads(path.read_text(encoding="utf-8"))


def search(
    root: Path,
    query: str,
    *,
    top_k: int,
    no_rerank: bool,
    provider_config: dict[str, Any],
    manifest: dict[str, Any],
) -> list[SearchResult]:
    index_dir = root / ".wegrep"
    query_embedding = embed(
        provider_config["embedding"]["base_url"],
        provider_config["embedding"]["api_key"],
        provider_config["embedding"]["model"],
        [query],
    )[0]
    vector_hits = _retrieve_vector(index_dir, manifest["collection"], query_embedding)
    bm25_hits = _retrieve_bm25(index_dir, query)
    candidates = _merge_candidates(bm25_hits, vector_hits)[:CANDIDATE_TOP_K]
    docstore = read_docstore(index_dir / "docstore.jsonl")

    if candidates and not _skip_rerank(no_rerank, provider_config):
        _rerank_candidates(candidates, docstore, query, provider_config)
    else:
        for candidate in candidates:
            candidate.confidence = candidate.hybrid_score

    return _dedupe_results(candidates, docstore, top_k)


def _skip_rerank(no_rerank: bool, provider_config: dict[str, Any]) -> bool:
    return no_rerank or provider_config.get("reranking", {}).get("provider") == "none"


def _retrieve_vector(index_dir: Path, collection: str, query_embedding: list[float]) -> list[Candidate]:
    import chromadb

    client = chromadb.PersistentClient(path=str(index_dir / "chroma"))
    chroma_collection = client.get_collection(_chroma_collection_name(collection))
    data = chroma_collection.query(
        query_embeddings=[query_embedding],
        n_results=VECTOR_TOP_K,
        include=["documents", "metadatas", "distances"],
    )
    ids = data.get("ids", [[]])[0]
    documents = data.get("documents", [[]])[0]
    metadatas = data.get("metadatas", [[]])[0]
    distances = data.get("distances", [[]])[0]
    hits = []
    for chunk_id, text, metadata, distance in zip(ids, documents, metadatas, distances, strict=False):
        metadata = _metadata_with_chunk_id(metadata or {}, str(chunk_id))
        hits.append(
            Candidate(
                chunk_id=str(metadata["chunk_id"]),
                text=str(text or ""),
                metadata=metadata,
                vector_score=1.0 - float(distance),
            )
        )
    return hits


def _retrieve_bm25(index_dir: Path, query: str) -> list[Candidate]:
    from llama_index.retrievers.bm25 import BM25Retriever

    bm25 = BM25Retriever.from_persist_dir(str(index_dir / "bm25"))
    bm25.similarity_top_k = min(BM25_TOP_K, int(bm25.bm25.scores.get("num_docs") or BM25_TOP_K))
    hits = []
    for hit in bm25.retrieve(query):
        node = hit.node
        metadata = dict(node.metadata or {})
        metadata = _metadata_with_chunk_id(metadata, node.node_id)
        hits.append(
            Candidate(
                chunk_id=str(metadata["chunk_id"]),
                text=node.get_content(metadata_mode="none"),
                metadata=metadata,
                bm25_score=float(hit.score or 0.0),
            )
        )
    return hits


def _merge_candidates(bm25_hits: list[Candidate], vector_hits: list[Candidate]) -> list[Candidate]:
    bm25_norm = _normalized_scores({hit.chunk_id: hit.bm25_score for hit in bm25_hits})
    vector_norm = _normalized_scores({hit.chunk_id: hit.vector_score for hit in vector_hits})
    merged: dict[str, Candidate] = {}
    for hit in [*bm25_hits, *vector_hits]:
        candidate = merged.get(hit.chunk_id)
        if candidate is None:
            candidate = Candidate(chunk_id=hit.chunk_id, text=hit.text, metadata=hit.metadata)
            merged[hit.chunk_id] = candidate
        if hit.bm25_score is not None:
            candidate.bm25_score = hit.bm25_score
        if hit.vector_score is not None:
            candidate.vector_score = hit.vector_score
        if not candidate.text and hit.text:
            candidate.text = hit.text
        if not candidate.metadata and hit.metadata:
            candidate.metadata = hit.metadata

    for candidate in merged.values():
        candidate.hybrid_score = 0.5 * bm25_norm.get(candidate.chunk_id, 0.0) + 0.5 * vector_norm.get(
            candidate.chunk_id, 0.0
        )
    return sorted(merged.values(), key=lambda candidate: candidate.hybrid_score, reverse=True)


def _rerank_candidates(
    candidates: list[Candidate],
    docstore: dict[str, DisplayChunk],
    query: str,
    provider_config: dict[str, Any],
) -> None:
    documents = [_rerank_document(candidate, docstore) for candidate in candidates]
    response = rerank(
        provider_config["reranking"]["base_url"],
        provider_config["reranking"]["api_key"],
        provider_config["reranking"]["model"],
        query,
        documents,
        len(documents),
    )
    raw_scores = _parse_rerank_scores(response, candidates)
    normalized = _normalized_scores(raw_scores)
    for candidate in candidates:
        candidate.rerank_score = raw_scores.get(candidate.chunk_id)
        candidate.confidence = normalized.get(candidate.chunk_id, 0.0)


def _rerank_document(candidate: Candidate, docstore: dict[str, DisplayChunk]) -> str:
    display_text = docstore[candidate.metadata["display_chunk_id"]].text
    return f"Matched child chunk:\n{candidate.text}\n\nParent display chunk:\n{display_text}"


def _parse_rerank_scores(response: dict[str, Any], candidates: list[Candidate]) -> dict[str, float]:
    results = response.get("results")
    if not isinstance(results, list):
        raise ProviderAPIError("provider rerank response missing results")

    scores: dict[str, float] = {}
    for item in results:
        if not isinstance(item, dict):
            continue
        score = item.get("relevance_score", item.get("score"))
        if score is None:
            continue
        if "index" in item:
            chunk_id = candidates[int(item["index"])].chunk_id
        elif "id" in item:
            chunk_id = str(item["id"])
        elif isinstance(item.get("document"), dict) and "id" in item["document"]:
            chunk_id = str(item["document"]["id"])
        else:
            continue
        scores[chunk_id] = float(score)
    if not scores:
        raise ProviderAPIError("provider rerank response missing scores")
    return scores


def _dedupe_results(
    candidates: list[Candidate],
    docstore: dict[str, DisplayChunk],
    top_k: int,
) -> list[SearchResult]:
    ordered = sorted(candidates, key=lambda candidate: candidate.confidence, reverse=True)
    results: list[SearchResult] = []
    seen: set[str] = set()
    for candidate in ordered:
        display_chunk_id = candidate.metadata["display_chunk_id"]
        if display_chunk_id in seen or display_chunk_id not in docstore:
            continue
        seen.add(display_chunk_id)
        results.append(SearchResult(display_chunk=docstore[display_chunk_id], candidate=candidate))
        if len(results) >= top_k:
            break
    return results


def _normalized_scores(scores: Mapping[str, float | None]) -> dict[str, float]:
    numeric = {key: float(value) for key, value in scores.items() if value is not None}
    if not numeric:
        return {}
    low = min(numeric.values())
    high = max(numeric.values())
    if high == low:
        return {key: 1.0 for key in numeric}
    return {key: (value - low) / (high - low) for key, value in numeric.items()}


def _metadata_with_chunk_id(metadata: dict[str, Any], fallback: str) -> dict[str, Any]:
    metadata = dict(metadata)
    metadata["chunk_id"] = metadata.get("chunk_id") or fallback
    if metadata.get("parent_chunk_id") == "":
        metadata["parent_chunk_id"] = None
    return metadata
