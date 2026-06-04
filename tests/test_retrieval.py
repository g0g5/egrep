from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from wegrep.chunking import DisplayChunk, write_docstore
from wegrep.config import DEFAULT_EMBEDDING_MODEL, DEFAULT_RERANKING_MODEL, OPENROUTER_BASE_URL
from wegrep.errors import IndexNotFoundError
from wegrep.retrieval import Candidate, SearchResult, _retrieve_bm25, load_manifest, run_query, search


def provider_config() -> dict[str, dict[str, str]]:
    return {
        "embedding": {
            "provider": "openrouter",
            "base_url": OPENROUTER_BASE_URL,
            "api_key": "key",
            "model": DEFAULT_EMBEDDING_MODEL,
        },
        "reranking": {
            "provider": "openrouter",
            "base_url": OPENROUTER_BASE_URL,
            "api_key": "key",
            "model": DEFAULT_RERANKING_MODEL,
        },
    }


def display_chunk(display_chunk_id: str, text: str) -> DisplayChunk:
    return DisplayChunk(
        display_chunk_id=display_chunk_id,
        type="text",
        path="notes.txt",
        start_line=1,
        end_line=3,
        content_hash="content",
        file_hash="file",
        text=text,
    )


def candidate(chunk_id: str, display_chunk_id: str, text: str, score: float | None = None) -> Candidate:
    return Candidate(
        chunk_id=chunk_id,
        text=text,
        metadata={
            "chunk_id": chunk_id,
            "display_chunk_id": display_chunk_id,
            "start_line": 1,
            "end_line": 3,
        },
        vector_score=score,
    )


def write_manifest(root: Path) -> dict[str, object]:
    manifest = {"version": 1, "root": str(root), "collection": "default"}
    index_dir = root / ".wegrep"
    index_dir.mkdir()
    (index_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


def test_load_manifest_missing_index_exits_three(tmp_path: Path) -> None:
    with pytest.raises(IndexNotFoundError) as excinfo:
        load_manifest(tmp_path)

    assert excinfo.value.exit_code == 3
    assert "wegrep init" in str(excinfo.value)


def test_search_merges_scores_and_deduplicates_without_rerank(monkeypatch, tmp_path: Path) -> None:
    manifest = write_manifest(tmp_path)
    write_docstore(
        tmp_path / ".wegrep" / "docstore.jsonl",
        [display_chunk("display-a", "parent a"), display_chunk("display-b", "parent b")],
    )
    bm25_hit = candidate("chunk-a", "display-a", "bm25 child")
    bm25_hit.bm25_score = 10.0
    vector_a = candidate("chunk-a", "display-a", "vector child", 0.2)
    vector_b = candidate("chunk-b", "display-b", "vector child b", 0.9)
    monkeypatch.setattr("wegrep.retrieval.embed", lambda *args: [[0.1, 0.2]])
    monkeypatch.setattr("wegrep.retrieval._retrieve_bm25", lambda *args: [bm25_hit])
    monkeypatch.setattr("wegrep.retrieval._retrieve_vector", lambda *args: [vector_a, vector_b])

    results = search(
        tmp_path,
        "needle",
        top_k=10,
        no_rerank=True,
        provider_config=provider_config(),
        manifest=manifest,
    )

    assert [result.display_chunk.display_chunk_id for result in results] == ["display-a", "display-b"]
    assert results[0].candidate.chunk_id == "chunk-a"
    assert results[0].candidate.bm25_score == 10.0
    assert results[0].candidate.vector_score == 0.2
    assert results[0].candidate.hybrid_score == 0.5
    assert results[0].candidate.confidence == results[0].candidate.hybrid_score
    assert results[0].candidate.rerank_score is None


def test_search_skips_rerank_when_provider_is_none(monkeypatch, tmp_path: Path) -> None:
    manifest = write_manifest(tmp_path)
    write_docstore(
        tmp_path / ".wegrep" / "docstore.jsonl",
        [display_chunk("display-a", "parent a")],
    )
    config = provider_config()
    config["reranking"] = {"provider": "none"}
    monkeypatch.setattr("wegrep.retrieval.embed", lambda *args: [[0.1, 0.2]])
    monkeypatch.setattr("wegrep.retrieval._retrieve_bm25", lambda *args: [])
    monkeypatch.setattr(
        "wegrep.retrieval._retrieve_vector",
        lambda *args: [candidate("chunk-a", "display-a", "child a", 0.9)],
    )
    monkeypatch.setattr("wegrep.retrieval.rerank", lambda *args: pytest.fail("rerank called"))

    results = search(
        tmp_path,
        "needle",
        top_k=10,
        no_rerank=False,
        provider_config=config,
        manifest=manifest,
    )

    assert results[0].candidate.confidence == results[0].candidate.hybrid_score
    assert results[0].candidate.rerank_score is None


def test_search_no_rerank_flag_wins_with_configured_provider(monkeypatch, tmp_path: Path) -> None:
    manifest = write_manifest(tmp_path)
    write_docstore(
        tmp_path / ".wegrep" / "docstore.jsonl",
        [display_chunk("display-a", "parent a")],
    )
    monkeypatch.setattr("wegrep.retrieval.embed", lambda *args: [[0.1, 0.2]])
    monkeypatch.setattr("wegrep.retrieval._retrieve_bm25", lambda *args: [])
    monkeypatch.setattr(
        "wegrep.retrieval._retrieve_vector",
        lambda *args: [candidate("chunk-a", "display-a", "child a", 0.9)],
    )
    monkeypatch.setattr("wegrep.retrieval.rerank", lambda *args: pytest.fail("rerank called"))

    results = search(
        tmp_path,
        "needle",
        top_k=10,
        no_rerank=True,
        provider_config=provider_config(),
        manifest=manifest,
    )

    assert results[0].candidate.confidence == results[0].candidate.hybrid_score
    assert results[0].candidate.rerank_score is None


def test_search_reranks_with_child_and_parent_text(monkeypatch, tmp_path: Path) -> None:
    manifest = write_manifest(tmp_path)
    write_docstore(
        tmp_path / ".wegrep" / "docstore.jsonl",
        [display_chunk("display-a", "parent a"), display_chunk("display-b", "parent b")],
    )
    monkeypatch.setattr("wegrep.retrieval.embed", lambda *args: [[0.1, 0.2]])
    monkeypatch.setattr("wegrep.retrieval._retrieve_bm25", lambda *args: [])
    monkeypatch.setattr(
        "wegrep.retrieval._retrieve_vector",
        lambda *args: [candidate("chunk-a", "display-a", "child a", 0.1), candidate("chunk-b", "display-b", "child b", 0.9)],
    )
    rerank_documents = []

    def fake_rerank(base_url, api_key, model, query, documents, top_n):
        rerank_documents.extend(documents)
        return {
            "results": [
                {"index": 0, "relevance_score": 0.8},
                {"index": 1, "relevance_score": 0.2},
            ]
        }

    monkeypatch.setattr("wegrep.retrieval.rerank", fake_rerank)

    results = search(
        tmp_path,
        "needle",
        top_k=1,
        no_rerank=False,
        provider_config=provider_config(),
        manifest=manifest,
    )

    assert results[0].display_chunk.display_chunk_id == "display-b"
    assert results[0].candidate.confidence == 1.0
    assert "Matched child chunk:\nchild b" in rerank_documents[0]
    assert "Parent display chunk:\nparent b" in rerank_documents[0]


def test_retrieve_bm25_loads_persisted_retriever_without_bm25s_kwargs(
    monkeypatch, tmp_path: Path
) -> None:
    from llama_index.retrievers.bm25 import BM25Retriever

    class FakeBM25:
        scores = {"num_docs": 1}

    class FakeRetriever:
        bm25 = FakeBM25()
        similarity_top_k = None

        def retrieve(self, query):
            assert query == "needle"
            return []

    def fake_from_persist_dir(path):
        assert path == str(tmp_path / ".wegrep" / "bm25")
        return FakeRetriever()

    monkeypatch.setattr(BM25Retriever, "from_persist_dir", fake_from_persist_dir)

    assert _retrieve_bm25(tmp_path / ".wegrep", "needle") == []


def test_run_query_requires_manifest_before_provider_config(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("wegrep.retrieval.resolve_provider_config", lambda root: pytest.fail("provider resolved"))

    with pytest.raises(IndexNotFoundError):
        run_query(argparse.Namespace(query="needle", top_k=10, no_rerank=True))


def test_run_query_default_output_is_human_readable(monkeypatch, tmp_path: Path, capsys) -> None:
    manifest = write_manifest(tmp_path)
    result = SearchResult(display_chunk=display_chunk("display-a", "parent text\n"), candidate=candidate("chunk-a", "display-a", "child"))
    result.candidate.confidence = 0.913
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("wegrep.retrieval.resolve_provider_config", lambda root: provider_config())
    monkeypatch.setattr("wegrep.retrieval.search", lambda *args, **kwargs: [result])

    exit_code = run_query(argparse.Namespace(query="needle", top_k=10, no_rerank=True, verbose=False))

    assert exit_code == 0
    output = capsys.readouterr().out
    assert output == "1. notes.txt:1-3 confidence=0.91\nparent text\n"
    with pytest.raises(json.JSONDecodeError):
        json.loads(output)


def test_run_query_verbose_output_is_json(monkeypatch, tmp_path: Path, capsys) -> None:
    result = SearchResult(display_chunk=display_chunk("display-a", "parent text"), candidate=candidate("chunk-a", "display-a", "child"))
    result.candidate.bm25_score = 8.42
    result.candidate.vector_score = 0.77
    result.candidate.hybrid_score = 0.81
    result.candidate.rerank_score = 0.91
    result.candidate.confidence = 1.0
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("wegrep.retrieval.resolve_provider_config", lambda root: provider_config())
    monkeypatch.setattr("wegrep.retrieval.search", lambda *args, **kwargs: [result])
    write_manifest(tmp_path)

    exit_code = run_query(argparse.Namespace(query="needle", top_k=10, no_rerank=False, verbose=True))

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["query"] == "needle"
    assert payload["results"][0]["path"] == "notes.txt"
    assert payload["results"][0]["scores"] == {
        "bm25_score": 8.42,
        "vector_score": 0.77,
        "hybrid_score": 0.81,
        "rerank_score": 0.91,
    }
    assert payload["results"][0]["matched_chunks"] == [
        {
            "chunk_id": "chunk-a",
            "start_line": 1,
            "end_line": 3,
            "bm25_score": 8.42,
            "vector_score": 0.77,
            "hybrid_score": 0.81,
            "rerank_score": 0.91,
        }
    ]
    assert payload["results"][0]["content"] == "parent text"
