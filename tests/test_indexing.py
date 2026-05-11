from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from egrep.config import DEFAULT_EMBEDDING_MODEL, DEFAULT_RERANKING_MODEL, OPENROUTER_BASE_URL
from egrep.errors import IndexWriteError
from egrep.indexing import build_index, run_init


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
    (tmp_path / ".egrep").mkdir()
    provider_path = tmp_path / ".egrep" / "provider.json"
    provider_path.write_text(json.dumps(provider_config()), encoding="utf-8")
    monkeypatch.setattr("egrep.indexing.embed_batched", fake_embeddings)

    manifest = build_index(
        tmp_path,
        collection="default",
        includes=[],
        excludes=[],
        max_file_size="1MB",
        provider_config=provider_config(),
    )

    assert provider_path.exists()
    assert (tmp_path / ".egrep" / "manifest.json").exists()
    assert (tmp_path / ".egrep" / "chroma").is_dir()
    assert (tmp_path / ".egrep" / "bm25").is_dir()
    assert (tmp_path / ".egrep" / "docstore.jsonl").exists()
    assert manifest["version"] == 1
    assert manifest["root"] == str(tmp_path)
    assert manifest["collection"] == "default"
    assert manifest["embedding_model"] == DEFAULT_EMBEDDING_MODEL
    assert manifest["rerank_model"] == DEFAULT_RERANKING_MODEL
    assert manifest["file_count"] == 1
    assert manifest["retrieval_chunk_count"] >= 1
    assert manifest["display_chunk_count"] >= 1


def test_run_init_resolves_root_and_maps_write_failures(monkeypatch, tmp_path: Path) -> None:
    def fail_build(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("egrep.indexing.resolve_provider_config", lambda root: provider_config())
    monkeypatch.setattr("egrep.indexing.build_index", fail_build)

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
    monkeypatch.setattr("egrep.indexing.resolve_provider_config", lambda root: provider_config())
    monkeypatch.setattr("egrep.indexing.build_index", fake_build)

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
