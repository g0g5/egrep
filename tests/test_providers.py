from __future__ import annotations

import pytest
import responses
from responses import matchers

from egrep.config import SILICONFLOW_BASE_URL
from egrep.errors import ProviderAPIError
from egrep.providers import OPENROUTER_BASE_URL, embed, embed_batched, rerank


@responses.activate
def test_embed_posts_json_and_returns_vectors_in_order() -> None:
    responses.post(
        f"{OPENROUTER_BASE_URL}/embeddings",
        json={"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]},
        status=200,
    )

    vectors = embed(OPENROUTER_BASE_URL, "key", "model", ["one", "two"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    request = responses.calls[0].request
    assert request.headers["Authorization"] == "Bearer key"
    assert request.headers["Content-Type"] == "application/json"
    assert request.body == b'{"model": "model", "input": ["one", "two"]}'


@responses.activate
def test_rerank_posts_model_query_documents_and_top_n() -> None:
    responses.post(
        f"{OPENROUTER_BASE_URL}/rerank",
        json={"results": [{"index": 0, "relevance_score": 0.9}]},
        match=[
            matchers.json_params_matcher(
                {
                    "model": "rerank-model",
                    "query": "query",
                    "documents": ["Matched child chunk:\ntext"],
                    "top_n": 5,
                    "return_documents": False,
                }
            )
        ],
        status=200,
    )
    documents = ["Matched child chunk:\ntext"]

    result = rerank(OPENROUTER_BASE_URL, "key", "rerank-model", "query", documents, 5)

    assert result == {"results": [{"index": 0, "relevance_score": 0.9}]}


@responses.activate
def test_empty_api_key_omits_authorization_header() -> None:
    responses.post(
        "http://127.0.0.1:8000/v1/embeddings",
        json={"data": [{"embedding": [0.1, 0.2]}]},
        status=200,
    )

    embed("http://127.0.0.1:8000/v1", "", "model", ["one"])

    request = responses.calls[0].request
    assert "Authorization" not in request.headers
    assert request.headers["Content-Type"] == "application/json"


@responses.activate
def test_siliconflow_uses_openai_compatible_embedding_path() -> None:
    responses.post(
        f"{SILICONFLOW_BASE_URL}/embeddings",
        json={"data": [{"embedding": [0.1, 0.2]}]},
        match=[matchers.json_params_matcher({"model": "BAAI/bge-m3", "input": ["one"]})],
        status=200,
    )

    vectors = embed(SILICONFLOW_BASE_URL, "key", "BAAI/bge-m3", ["one"])

    assert vectors == [[0.1, 0.2]]


@responses.activate
def test_rerank_normalizes_top_level_result_list() -> None:
    responses.post(
        "http://127.0.0.1:30000/v1/rerank",
        json=[{"index": 0, "score": 0.9}],
        status=200,
    )

    result = rerank("http://127.0.0.1:30000/v1", "", "model", "query", ["doc"], 1)

    assert result == {"results": [{"index": 0, "score": 0.9}]}


@responses.activate
def test_embed_batched_uses_default_batch_size() -> None:
    texts = [f"text-{index}" for index in range(33)]
    responses.post(
        f"{OPENROUTER_BASE_URL}/embeddings",
        json={"data": [{"embedding": [float(index)]} for index in range(32)]},
        status=200,
    )
    responses.post(
        f"{OPENROUTER_BASE_URL}/embeddings",
        json={"data": [{"embedding": [32.0]}]},
        status=200,
    )

    vectors = embed_batched(OPENROUTER_BASE_URL, "key", "model", texts)

    assert vectors == [[float(index)] for index in range(33)]
    assert len(responses.calls) == 2


@responses.activate
def test_provider_http_failure_raises_exit_code_5() -> None:
    responses.post(f"{OPENROUTER_BASE_URL}/embeddings", status=500)

    with pytest.raises(ProviderAPIError) as excinfo:
        embed(OPENROUTER_BASE_URL, "key", "model", ["text"])

    assert excinfo.value.exit_code == 5


@responses.activate
def test_provider_response_failure_raises_exit_code_5() -> None:
    responses.post(
        f"{OPENROUTER_BASE_URL}/embeddings",
        json={"data": []},
        status=200,
    )

    with pytest.raises(ProviderAPIError) as excinfo:
        embed(OPENROUTER_BASE_URL, "key", "model", ["text"])

    assert excinfo.value.exit_code == 5
