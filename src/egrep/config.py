from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .errors import ProviderConfigError


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-3-small"
DEFAULT_RERANKING_MODEL = "cohere/rerank-v3.5"
REQUIRED_PROVIDER_FIELDS = ("provider", "base_url", "api_key", "model")


def workspace_provider_path(root: Path | None = None) -> Path:
    return (Path.cwd() if root is None else root) / ".egrep" / "provider.json"


def global_provider_path() -> Path:
    return Path.home() / ".config" / "egrep" / "provider.json"


def provider_config_path(global_config: bool, root: Path | None = None) -> Path:
    if global_config:
        return global_provider_path()
    return workspace_provider_path(root)


def _read_provider_config(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProviderConfigError(f"invalid provider configuration: {path}") from exc
    if not isinstance(data, dict):
        raise ProviderConfigError(f"invalid provider configuration: {path}")
    return data


def validate_provider_config(config: dict[str, Any]) -> dict[str, Any]:
    for section_name in ("embedding", "reranking"):
        section = config.get(section_name)
        if not isinstance(section, dict):
            raise ProviderConfigError(
                f"provider configuration missing {section_name} settings"
            )
        missing = [field for field in REQUIRED_PROVIDER_FIELDS if not section.get(field)]
        if missing:
            raise ProviderConfigError(
                f"provider configuration missing {section_name} fields: "
                + ", ".join(missing)
            )
    return config


def resolve_provider_config(root: Path | None = None) -> dict[str, Any]:
    workspace_path = workspace_provider_path(root)
    if workspace_path.exists():
        return validate_provider_config(_read_provider_config(workspace_path))

    fallback_path = global_provider_path()
    if fallback_path.exists():
        return validate_provider_config(_read_provider_config(fallback_path))

    raise ProviderConfigError(
        "provider configuration missing; run `egrep config` or `egrep config --global`"
    )


def _ask_required(prompt) -> str:
    value = prompt.ask()
    if not value:
        raise ProviderConfigError("provider configuration cancelled or incomplete")
    return str(value)


def _prompt_provider_config() -> dict[str, Any]:
    import questionary

    _ask_required(
        questionary.select("Embedding provider", choices=["OpenRouter.ai"])
    )
    embedding_api_key = _ask_required(questionary.password("Embedding API key"))
    embedding_model = _ask_required(
        questionary.text("Embedding model", default=DEFAULT_EMBEDDING_MODEL)
    )

    _ask_required(
        questionary.select("Reranking provider", choices=["OpenRouter.ai"])
    )
    reranking_api_key = _ask_required(questionary.password("Reranking API key"))
    reranking_model = _ask_required(
        questionary.text("Reranking model", default=DEFAULT_RERANKING_MODEL)
    )

    return {
        "embedding": {
            "provider": "openrouter",
            "base_url": OPENROUTER_BASE_URL,
            "api_key": embedding_api_key,
            "model": embedding_model,
        },
        "reranking": {
            "provider": "openrouter",
            "base_url": OPENROUTER_BASE_URL,
            "api_key": reranking_api_key,
            "model": reranking_model,
        },
    }


def write_provider_config(path: Path, config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def run_config(args: argparse.Namespace) -> int:
    config = validate_provider_config(_prompt_provider_config())
    path = provider_config_path(args.global_config)
    write_provider_config(path, config)
    print(f"provider configuration written to {path}")
    return 0
