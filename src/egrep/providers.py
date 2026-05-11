from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import requests

from .errors import ProviderAPIError

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
TIMEOUT = (5, 60)
DEFAULT_EMBED_BATCH_SIZE = 32


def post_json(url: str, api_key: str, body: dict[str, Any]) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        response = requests.post(url, headers=headers, json=body, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as exc:
        raise ProviderAPIError(f"provider request failed: {exc}") from exc
    except ValueError as exc:
        raise ProviderAPIError("provider returned invalid JSON") from exc

    if not isinstance(data, dict):
        raise ProviderAPIError("provider returned invalid JSON shape")
    return data


def embed(
    base_url: str,
    api_key: str,
    model: str,
    texts: list[str],
) -> list[list[float]]:
    data = post_json(
        f"{base_url.rstrip('/')}/embeddings",
        api_key,
        {"model": model, "input": texts},
    )
    try:
        embeddings = [item["embedding"] for item in data["data"]]
    except (KeyError, TypeError) as exc:
        raise ProviderAPIError("provider embedding response missing data") from exc

    if len(embeddings) != len(texts):
        raise ProviderAPIError("provider embedding response count mismatch")
    return embeddings


def _batches(values: list[str], batch_size: int) -> Iterable[list[str]]:
    for start in range(0, len(values), batch_size):
        yield values[start : start + batch_size]


def embed_batched(
    base_url: str,
    api_key: str,
    model: str,
    texts: list[str],
    batch_size: int = DEFAULT_EMBED_BATCH_SIZE,
) -> list[list[float]]:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    embeddings: list[list[float]] = []
    for batch in _batches(texts, batch_size):
        embeddings.extend(embed(base_url, api_key, model, batch))
    return embeddings


def rerank(
    base_url: str,
    api_key: str,
    model: str,
    query: str,
    documents: list[dict[str, Any]],
    top_n: int,
) -> dict[str, Any]:
    return post_json(
        f"{base_url.rstrip('/')}/rerank",
        api_key,
        {
            "model": model,
            "query": query,
            "documents": documents,
            "top_n": top_n,
        },
    )
