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
    resolve_provider_config,
    run_config,
    validate_provider_config,
)
from egrep.errors import ProviderConfigError


class Prompt:
    def __init__(self, value: str) -> None:
        self.value = value

    def ask(self) -> str:
        return self.value


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
    monkeypatch.setattr("questionary.select", lambda *args, **kwargs: Prompt("OpenRouter.ai"))
    monkeypatch.setattr("questionary.password", lambda *args, **kwargs: Prompt("secret"))
    monkeypatch.setattr(
        "questionary.text", lambda *args, **kwargs: Prompt(kwargs["default"])
    )

    assert run_config(argparse.Namespace(global_config=False)) == 0

    data = json.loads((tmp_path / ".egrep" / "provider.json").read_text())
    assert data == provider_config("secret")


def test_run_config_writes_global_provider(monkeypatch, tmp_path) -> None:
    home = tmp_path / "home"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setattr("questionary.select", lambda *args, **kwargs: Prompt("OpenRouter.ai"))
    monkeypatch.setattr("questionary.password", lambda *args, **kwargs: Prompt("secret"))
    monkeypatch.setattr(
        "questionary.text", lambda *args, **kwargs: Prompt(kwargs["default"])
    )

    assert run_config(argparse.Namespace(global_config=True)) == 0

    data = json.loads((home / ".config" / "egrep" / "provider.json").read_text())
    assert data == provider_config("secret")
