from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .retrieval import SearchResult


def format_human(results: list[SearchResult]) -> str:
    sections = []
    for rank, result in enumerate(results, start=1):
        chunk = result.display_chunk
        sections.append(
            "\n".join(
                [
                    f"{rank}. {chunk.path}:{chunk.start_line}-{chunk.end_line} "
                    f"confidence={result.candidate.confidence:.2f}",
                    chunk.text.rstrip(),
                ]
            )
        )
    return "\n\n".join(sections)


def format_verbose(query: str, results: list[SearchResult]) -> str:
    payload: dict[str, Any] = {
        "query": query,
        "results": [_verbose_result(result) for result in results],
    }
    return json.dumps(payload, indent=2)


def _verbose_result(result: SearchResult) -> dict[str, Any]:
    chunk = result.display_chunk
    candidate = result.candidate
    return {
        "path": chunk.path,
        "start_line": chunk.start_line,
        "end_line": chunk.end_line,
        "confidence": candidate.confidence,
        "scores": {
            "bm25_score": candidate.bm25_score,
            "vector_score": candidate.vector_score,
            "hybrid_score": candidate.hybrid_score,
            "rerank_score": candidate.rerank_score,
        },
        "matched_chunks": [
            {
                "chunk_id": candidate.chunk_id,
                "start_line": candidate.metadata.get("start_line"),
                "end_line": candidate.metadata.get("end_line"),
                "bm25_score": candidate.bm25_score,
                "vector_score": candidate.vector_score,
                "hybrid_score": candidate.hybrid_score,
                "rerank_score": candidate.rerank_score,
            }
        ],
        "content": chunk.text,
    }
