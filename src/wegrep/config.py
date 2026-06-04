from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ProviderConfigError


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-3-small"
DEFAULT_RERANKING_MODEL = "cohere/rerank-v3.5"


@dataclass(frozen=True)
class ProviderSpec:
    provider: str
    section: str
    default_base_url: str | None
    prompt_base_url: bool
    requires_api_key: bool
    prompt_api_key: bool
    requires_model: bool
    default_model: str | None
    transport_kind: str


PROVIDER_REGISTRY: dict[str, dict[str, ProviderSpec]] = {
    "embedding": {
        "openrouter": ProviderSpec(
            provider="openrouter",
            section="embedding",
            default_base_url=OPENROUTER_BASE_URL,
            prompt_base_url=False,
            requires_api_key=True,
            prompt_api_key=True,
            requires_model=True,
            default_model=DEFAULT_EMBEDDING_MODEL,
            transport_kind="openai_embeddings",
        ),
        "siliconflow": ProviderSpec(
            provider="siliconflow",
            section="embedding",
            default_base_url=SILICONFLOW_BASE_URL,
            prompt_base_url=False,
            requires_api_key=True,
            prompt_api_key=True,
            requires_model=True,
            default_model=None,
            transport_kind="openai_embeddings",
        ),
        "llamacpp": ProviderSpec(
            provider="llamacpp",
            section="embedding",
            default_base_url="http://127.0.0.1:8080/v1",
            prompt_base_url=True,
            requires_api_key=False,
            prompt_api_key=True,
            requires_model=True,
            default_model=None,
            transport_kind="openai_embeddings",
        ),
        "vllm": ProviderSpec(
            provider="vllm",
            section="embedding",
            default_base_url="http://127.0.0.1:8000/v1",
            prompt_base_url=True,
            requires_api_key=False,
            prompt_api_key=True,
            requires_model=True,
            default_model=None,
            transport_kind="openai_embeddings",
        ),
        "sglang": ProviderSpec(
            provider="sglang",
            section="embedding",
            default_base_url="http://127.0.0.1:30000/v1",
            prompt_base_url=True,
            requires_api_key=False,
            prompt_api_key=True,
            requires_model=True,
            default_model=None,
            transport_kind="openai_embeddings",
        ),
    },
    "reranking": {
        "openrouter": ProviderSpec(
            provider="openrouter",
            section="reranking",
            default_base_url=OPENROUTER_BASE_URL,
            prompt_base_url=False,
            requires_api_key=True,
            prompt_api_key=True,
            requires_model=True,
            default_model=DEFAULT_RERANKING_MODEL,
            transport_kind="rerank",
        ),
        "siliconflow": ProviderSpec(
            provider="siliconflow",
            section="reranking",
            default_base_url=SILICONFLOW_BASE_URL,
            prompt_base_url=False,
            requires_api_key=True,
            prompt_api_key=True,
            requires_model=True,
            default_model=None,
            transport_kind="rerank",
        ),
        "llamacpp": ProviderSpec(
            provider="llamacpp",
            section="reranking",
            default_base_url="http://127.0.0.1:8080/v1",
            prompt_base_url=True,
            requires_api_key=False,
            prompt_api_key=True,
            requires_model=True,
            default_model=None,
            transport_kind="rerank",
        ),
        "vllm": ProviderSpec(
            provider="vllm",
            section="reranking",
            default_base_url="http://127.0.0.1:8000/v1",
            prompt_base_url=True,
            requires_api_key=False,
            prompt_api_key=True,
            requires_model=True,
            default_model=None,
            transport_kind="rerank",
        ),
        "sglang": ProviderSpec(
            provider="sglang",
            section="reranking",
            default_base_url="http://127.0.0.1:30000/v1",
            prompt_base_url=True,
            requires_api_key=False,
            prompt_api_key=True,
            requires_model=True,
            default_model=None,
            transport_kind="rerank",
        ),
        "none": ProviderSpec(
            provider="none",
            section="reranking",
            default_base_url=None,
            prompt_base_url=False,
            requires_api_key=False,
            prompt_api_key=False,
            requires_model=False,
            default_model=None,
            transport_kind="none",
        ),
    },
}


def workspace_provider_path(root: Path | None = None) -> Path:
    return (Path.cwd() if root is None else root) / ".wegrep" / "provider.json"


def global_provider_path() -> Path:
    return Path.home() / ".config" / "wegrep" / "provider.json"


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
        provider = section.get("provider")
        if not isinstance(provider, str) or not provider:
            raise ProviderConfigError(
                f"provider configuration missing {section_name} fields: provider"
            )
        spec = PROVIDER_REGISTRY[section_name].get(provider)
        if spec is None:
            raise ProviderConfigError(
                f"unsupported {section_name} provider: {provider}"
            )
        if provider == "none":
            continue

        if spec.default_base_url and not spec.prompt_base_url:
            section["base_url"] = spec.default_base_url
        if not spec.requires_api_key:
            section.setdefault("api_key", "")

        missing = []
        if spec.prompt_base_url and not section.get("base_url"):
            missing.append("base_url")
        if spec.requires_api_key and not section.get("api_key"):
            missing.append("api_key")
        if spec.requires_model and not section.get("model"):
            missing.append("model")
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
        "provider configuration missing; run `wegrep config` or `wegrep config --global`"
    )


def _section_spec(section: str, provider: str) -> ProviderSpec:
    return PROVIDER_REGISTRY[section][provider]


def _prompt_section(questionary, section: str) -> dict[str, Any]:
    message_prefix = "Embedding" if section == "embedding" else "Reranking"

    answers = questionary.prompt(
        [
            {
                "type": "select",
                "name": "provider",
                "message": f"{message_prefix} provider",
                "choices": list(PROVIDER_REGISTRY[section]),
            },
            {
                "type": "text",
                "name": "base_url",
                "message": "Base URL",
                "default": lambda answer: _section_spec(
                    section, answer["provider"]
                ).default_base_url,
                "when": lambda answer: _section_spec(
                    section, answer["provider"]
                ).prompt_base_url,
            },
            {
                "type": "password",
                "name": "api_key",
                "message": f"{message_prefix} API key",
                "when": lambda answer: _section_spec(
                    section, answer["provider"]
                ).prompt_api_key,
            },
            {
                "type": "text",
                "name": "model",
                "message": f"{message_prefix} model",
                "default": lambda answer: _section_spec(
                    section, answer["provider"]
                ).default_model
                or "",
                "when": lambda answer: _section_spec(
                    section, answer["provider"]
                ).requires_model,
            },
        ]
    )
    if not isinstance(answers, dict):
        raise ProviderConfigError("provider configuration cancelled or incomplete")

    provider = answers.get("provider")
    if not isinstance(provider, str) or not provider:
        raise ProviderConfigError("provider configuration cancelled or incomplete")
    spec = _section_spec(section, provider)
    if provider == "none":
        return {"provider": "none"}

    base_url = answers.get("base_url") or spec.default_base_url
    api_key = answers.get("api_key", "")
    model = answers.get("model")
    if spec.requires_api_key and not api_key:
        raise ProviderConfigError("provider configuration cancelled or incomplete")
    if spec.requires_model and not model:
        raise ProviderConfigError("provider configuration cancelled or incomplete")

    return {
        "provider": provider,
        "base_url": base_url,
        "api_key": str(api_key),
        "model": str(model),
    }


def _prompt_provider_config() -> dict[str, Any]:
    import questionary

    return {
        "embedding": _prompt_section(questionary, "embedding"),
        "reranking": _prompt_section(questionary, "reranking"),
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
