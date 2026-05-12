# `responses` quick reference

Latest upstream docs/examples: `getsentry/responses` README and PyPI page.

## Mock a JSON POST

```python
import responses

from egrep.providers import OPENROUTER_BASE_URL, embed


@responses.activate
def test_embed_posts_json() -> None:
    responses.post(
        f"{OPENROUTER_BASE_URL}/embeddings",
        json={"data": [{"embedding": [0.1, 0.2]}]},
        status=200,
    )

    vectors = embed(OPENROUTER_BASE_URL, "key", "model", ["one"])

    assert vectors == [[0.1, 0.2]]
```

## Assert POST body with a matcher

```python
import responses
from responses import matchers

from egrep.providers import OPENROUTER_BASE_URL, embed


@responses.activate
def test_embed_matches_json_body() -> None:
    responses.post(
        f"{OPENROUTER_BASE_URL}/embeddings",
        json={"data": [{"embedding": [0.1, 0.2]}]},
        match=[
            matchers.json_params_matcher(
                {"model": "model", "input": ["one", "two"]}
            )
        ],
    )

    embed(OPENROUTER_BASE_URL, "key", "model", ["one", "two"])
```

## Assert headers with a matcher

```python
import responses
from responses import matchers

from egrep.providers import OPENROUTER_BASE_URL, embed


@responses.activate
def test_embed_matches_headers() -> None:
    responses.post(
        f"{OPENROUTER_BASE_URL}/embeddings",
        json={"data": [{"embedding": [0.1, 0.2]}]},
        match=[
            matchers.header_matcher(
                {
                    "Authorization": "Bearer key",
                    "Content-Type": "application/json",
                }
            )
        ],
    )

    embed(OPENROUTER_BASE_URL, "key", "model", ["one"])
```

## Assert request body and headers after the call

```python
import responses

from egrep.providers import OPENROUTER_BASE_URL, rerank


@responses.activate
def test_rerank_inspects_sent_request() -> None:
    responses.post(
        f"{OPENROUTER_BASE_URL}/rerank",
        json={"results": [{"index": 0, "relevance_score": 0.9}]},
    )

    rerank(OPENROUTER_BASE_URL, "key", "rerank-model", "query", ["doc"], 1)

    request = responses.calls[0].request
    assert request.headers["Authorization"] == "Bearer key"
    assert request.headers["Content-Type"] == "application/json"
    assert request.body == (
        b'{"model": "rerank-model", "query": "query", '
        b'"documents": ["doc"], "top_n": 1}'
    )
```

## Multiple mocked calls to the same endpoint

```python
import responses

from egrep.providers import OPENROUTER_BASE_URL, embed_batched


@responses.activate
def test_embed_batched_uses_two_responses() -> None:
    responses.post(
        f"{OPENROUTER_BASE_URL}/embeddings",
        json={"data": [{"embedding": [1.0]}]},
        status=200,
    )
    responses.post(
        f"{OPENROUTER_BASE_URL}/embeddings",
        json={"data": [{"embedding": [2.0]}]},
        status=200,
    )

    vectors = embed_batched(
        OPENROUTER_BASE_URL,
        "key",
        "model",
        [f"text-{i}" for i in range(33)],
        batch_size=32,
    )

    assert vectors == [[1.0], [2.0]]
    assert len(responses.calls) == 2
    assert responses.calls[0].request.url == f"{OPENROUTER_BASE_URL}/embeddings"
    assert responses.calls[1].request.url == f"{OPENROUTER_BASE_URL}/embeddings"
```

## Ordered responses for retries / retry-like flows

```python
import responses
from responses.registries import OrderedRegistry

import requests


@responses.activate(registry=OrderedRegistry)
def test_retry_sequence() -> None:
    url = "https://openrouter.ai/api/v1/embeddings"
    responses.post(url, status=500)
    responses.post(url, json={"data": [{"embedding": [0.1]}]}, status=200)

    first = requests.post(url)
    second = requests.post(url)

    assert first.status_code == 500
    assert second.status_code == 200
```

## Count calls

```python
import responses

import requests


@responses.activate
def test_call_count() -> None:
    url = "https://openrouter.ai/api/v1/embeddings"
    mocked = responses.post(url, json={"ok": True})

    requests.post(url)
    requests.post(url)

    assert mocked.call_count == 2
    assert responses.assert_call_count(url, 2) is True
```

## Dynamic callback when response depends on request JSON

```python
import json

import responses
import requests


@responses.activate
def test_callback() -> None:
    def callback(request):
        payload = json.loads(request.body)
        body = {"received": payload["input"]}
        return (200, {"Content-Type": "application/json"}, json.dumps(body))

    responses.add_callback(
        responses.POST,
        "https://openrouter.ai/api/v1/embeddings",
        callback=callback,
        content_type="application/json",
    )

    response = requests.post(
        "https://openrouter.ai/api/v1/embeddings",
        json={"input": ["one", "two"]},
    )

    assert response.json() == {"received": ["one", "two"]}
```

## Notes

- Prefer `matchers.json_params_matcher(...)` over exact byte-string body checks when JSON field ordering should not matter.
- Prefer `responses.calls[n].request` when you want direct post-call inspection.
- Use `OrderedRegistry` when call order matters.
- `match_querystring` is deprecated; use matchers instead.

## Sources

- https://github.com/getsentry/responses
- https://raw.githubusercontent.com/getsentry/responses/master/README.rst
- https://pypi.org/project/responses/
