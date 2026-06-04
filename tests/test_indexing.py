from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from wegrep.config import DEFAULT_EMBEDDING_MODEL, DEFAULT_RERANKING_MODEL, OPENROUTER_BASE_URL
from wegrep.errors import IndexWriteError
from wegrep.indexing import InitProgress, build_index, run_init


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


def fake_embeddings(
    base_url: str,
    api_key: str,
    model: str,
    texts: list[str],
) -> list[list[float]]:
    return [[1.0, float(index)] for index, _text in enumerate(texts)]


def test_build_index_writes_expected_layout_and_manifest(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
    (tmp_path / ".wegrep").mkdir()
    provider_path = tmp_path / ".wegrep" / "provider.json"
    provider_path.write_text(json.dumps(provider_config()), encoding="utf-8")
    monkeypatch.setattr("wegrep.indexing.embed_batched", fake_embeddings)

    manifest = build_index(
        tmp_path,
        collection="default",
        includes=[],
        excludes=[],
        max_file_size="1MB",
        provider_config=provider_config(),
    )

    assert provider_path.exists()
    assert (tmp_path / ".wegrep" / "manifest.json").exists()
    assert (tmp_path / ".wegrep" / "chroma").is_dir()
    assert (tmp_path / ".wegrep" / "bm25").is_dir()
    assert (tmp_path / ".wegrep" / "docstore.jsonl").exists()
    assert manifest["version"] == 1
    assert manifest["root"] == str(tmp_path)
    assert manifest["collection"] == "default"
    assert manifest["embedding_model"] == DEFAULT_EMBEDDING_MODEL
    assert manifest["rerank_model"] == DEFAULT_RERANKING_MODEL
    assert manifest["file_count"] == 1
    assert manifest["retrieval_chunk_count"] >= 1
    assert manifest["display_chunk_count"] >= 1


def test_build_index_allows_reranking_provider_none(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
    config = provider_config()
    config["reranking"] = {"provider": "none"}
    monkeypatch.setattr("wegrep.indexing.embed_batched", fake_embeddings)

    manifest = build_index(
        tmp_path,
        collection="default",
        includes=[],
        excludes=[],
        max_file_size="1MB",
        provider_config=config,
    )

    persisted = json.loads((tmp_path / ".wegrep" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["rerank_model"] is None
    assert persisted["rerank_model"] is None


def test_build_index_emits_progress_events(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
    monkeypatch.setattr("wegrep.indexing.embed_batched", fake_embeddings)
    events: list[InitProgress] = []

    build_index(
        tmp_path,
        collection="default",
        includes=[],
        excludes=[],
        max_file_size="1MB",
        provider_config=provider_config(),
        progress=events.append,
    )

    stages = {event.stage for event in events}
    assert {
        "prepare",
        "discover",
        "chunk",
        "embed",
        "write_chroma",
        "write_bm25",
        "write_docstore",
        "write_manifest",
    } <= stages
    assert any(event.stage == "discover" and event.path == "src/app.py" and event.total == 1 for event in events)
    assert any(event.stage == "chunk" and event.path == "src/app.py" and event.total == 1 for event in events)
    assert any(event.stage == "embed" and event.path == "src/app.py" for event in events)
    assert any(event.stage == "write_docstore" and event.total is not None and event.total >= 1 for event in events)


def test_run_init_resolves_root_and_maps_write_failures(monkeypatch, tmp_path: Path) -> None:
    def fail_build(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("wegrep.indexing.resolve_provider_config", lambda root: provider_config())
    monkeypatch.setattr("wegrep.indexing.build_index", fail_build)

    args = argparse.Namespace(
        root=str(tmp_path),
        collection="default",
        include=[],
        exclude=[],
        max_file_size="1MB",
    )

    with pytest.raises(IndexWriteError) as excinfo:
        run_init(args)

    assert excinfo.value.exit_code == 6


def test_run_init_uses_current_directory_by_default(monkeypatch, tmp_path: Path) -> None:
    seen: dict[str, Path] = {}

    def fake_build(root: Path, **kwargs) -> dict:
        seen["root"] = root
        return {"file_count": 0, "retrieval_chunk_count": 0, "display_chunk_count": 0}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("wegrep.indexing.resolve_provider_config", lambda root: provider_config())
    monkeypatch.setattr("wegrep.indexing.build_index", fake_build)

    exit_code = run_init(
        argparse.Namespace(
            root=".",
            collection="default",
            include=[],
            exclude=[],
            max_file_size="1MB",
        )
    )

    assert exit_code == 0
    assert seen["root"] == tmp_path.resolve()
