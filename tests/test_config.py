from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pytest

from egrep.config import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_RERANKING_MODEL,
    OPENROUTER_BASE_URL,
    PROVIDER_REGISTRY,
    SILICONFLOW_BASE_URL,
    resolve_provider_config,
    run_config,
    validate_provider_config,
)
from egrep.errors import ProviderConfigError


def provider_config(api_key: str = "key") -> dict[str, dict[str, str]]:
    return {
        "embedding": {
            "provider": "openrouter",
            "base_url": OPENROUTER_BASE_URL,
            "api_key": api_key,
            "model": DEFAULT_EMBEDDING_MODEL,
        },
        "reranking": {
            "provider": "openrouter",
            "base_url": OPENROUTER_BASE_URL,
            "api_key": api_key,
            "model": DEFAULT_RERANKING_MODEL,
        },
    }


def write_config(path: Path, config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config), encoding="utf-8")


def test_resolve_provider_config_prefers_workspace(monkeypatch, tmp_path) -> None:
    home = tmp_path / "home"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.chdir(workspace)
    write_config(home / ".config" / "egrep" / "provider.json", provider_config("global"))
    write_config(workspace / ".egrep" / "provider.json", provider_config("workspace"))

    config = resolve_provider_config()

    assert config["embedding"]["api_key"] == "workspace"
    assert config["reranking"]["api_key"] == "workspace"


def test_resolve_provider_config_uses_global_fallback(monkeypatch, tmp_path) -> None:
    home = tmp_path / "home"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.chdir(workspace)
    write_config(home / ".config" / "egrep" / "provider.json", provider_config("global"))

    config = resolve_provider_config()

    assert config["embedding"]["api_key"] == "global"


def test_missing_provider_config_raises_exit_code_4(monkeypatch, tmp_path) -> None:
    home = tmp_path / "home"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.chdir(workspace)

    with pytest.raises(ProviderConfigError) as excinfo:
        resolve_provider_config()

    assert excinfo.value.exit_code == 4


def test_incomplete_provider_config_raises_exit_code_4() -> None:
    config = provider_config()
    config["reranking"]["api_key"] = ""

    with pytest.raises(ProviderConfigError) as excinfo:
        validate_provider_config(config)

    assert excinfo.value.exit_code == 4


def test_run_config_writes_workspace_provider(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)

    def prompt(questions):
        if questions[0]["message"] == "Embedding provider":
            return {
                "provider": "openrouter",
                "api_key": "secret",
                "model": DEFAULT_EMBEDDING_MODEL,
            }
        return {
            "provider": "openrouter",
            "api_key": "secret",
            "model": DEFAULT_RERANKING_MODEL,
        }

    monkeypatch.setattr("questionary.prompt", prompt)

    assert run_config(argparse.Namespace(global_config=False)) == 0

    data = json.loads((tmp_path / ".egrep" / "provider.json").read_text())
    assert data == provider_config("secret")


def test_run_config_writes_global_provider(monkeypatch, tmp_path) -> None:
    home = tmp_path / "home"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: home)

    def prompt(questions):
        if questions[0]["message"] == "Embedding provider":
            return {
                "provider": "openrouter",
                "api_key": "secret",
                "model": DEFAULT_EMBEDDING_MODEL,
            }
        return {
            "provider": "openrouter",
            "api_key": "secret",
            "model": DEFAULT_RERANKING_MODEL,
        }

    monkeypatch.setattr("questionary.prompt", prompt)

    assert run_config(argparse.Namespace(global_config=True)) == 0

    data = json.loads((home / ".config" / "egrep" / "provider.json").read_text())
    assert data == provider_config("secret")


def test_provider_registry_includes_config_choices() -> None:
    assert list(PROVIDER_REGISTRY["embedding"]) == [
        "openrouter",
        "siliconflow",
        "llamacpp",
        "vllm",
        "sglang",
    ]
    assert list(PROVIDER_REGISTRY["reranking"]) == [
        "openrouter",
        "siliconflow",
        "llamacpp",
        "vllm",
        "sglang",
        "none",
    ]


def test_run_config_writes_siliconflow_without_base_url_prompt(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    calls = []

    def prompt(questions):
        calls.append(questions)
        assert questions[1]["when"]({"provider": "siliconflow"}) is False
        return {
            "provider": "siliconflow",
            "api_key": "secret",
            "model": "BAAI/bge-m3",
        }

    monkeypatch.setattr("questionary.prompt", prompt)

    assert run_config(argparse.Namespace(global_config=False)) == 0

    data = json.loads((tmp_path / ".egrep" / "provider.json").read_text())
    assert data == {
        "embedding": {
            "provider": "siliconflow",
            "base_url": SILICONFLOW_BASE_URL,
            "api_key": "secret",
            "model": "BAAI/bge-m3",
        },
        "reranking": {
            "provider": "siliconflow",
            "base_url": SILICONFLOW_BASE_URL,
            "api_key": "secret",
            "model": "BAAI/bge-m3",
        },
    }
    assert len(calls) == 2


def test_run_config_writes_local_provider_and_rerank_none(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)

    def prompt(questions):
        if questions[0]["message"] == "Embedding provider":
            assert questions[1]["when"]({"provider": "vllm"}) is True
            return {
                "provider": "vllm",
                "base_url": questions[1]["default"]({"provider": "vllm"}),
                "api_key": "",
                "model": "BAAI/bge-m3",
            }
        assert questions[1]["when"]({"provider": "none"}) is False
        assert questions[2]["when"]({"provider": "none"}) is False
        assert questions[3]["when"]({"provider": "none"}) is False
        return {"provider": "none"}

    monkeypatch.setattr("questionary.prompt", prompt)

    assert run_config(argparse.Namespace(global_config=False)) == 0

    data = json.loads((tmp_path / ".egrep" / "provider.json").read_text())
    assert data == {
        "embedding": {
            "provider": "vllm",
            "base_url": "http://127.0.0.1:8000/v1",
            "api_key": "",
            "model": "BAAI/bge-m3",
        },
        "reranking": {"provider": "none"},
    }


def test_local_provider_api_key_is_optional() -> None:
    config = provider_config()
    config["embedding"] = {
        "provider": "llamacpp",
        "base_url": "http://127.0.0.1:8080/v1",
        "model": "BAAI/bge-m3",
    }

    validated = validate_provider_config(config)

    assert validated["embedding"]["api_key"] == ""


def test_rerank_none_is_valid_only_for_reranking() -> None:
    config = provider_config()
    config["reranking"] = {"provider": "none"}

    assert validate_provider_config(config)["reranking"] == {"provider": "none"}

    config["embedding"] = {"provider": "none"}
    with pytest.raises(ProviderConfigError):
        validate_provider_config(config)
