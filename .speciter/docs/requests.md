# Requests for egrep Providers

Use `requests` with explicit `timeout`, `headers`, `json=...`, `raise_for_status()`, and `requests.exceptions.RequestException` handling.

```python
import requests

TIMEOUT = (5, 60)  # connect seconds, read seconds


class ProviderHTTPError(RuntimeError):
    pass


def post_json(url, api_key, body, extra_headers=None):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        **(extra_headers or {}),
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        r = requests.post(url, headers=headers, json=body, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.JSONDecodeError as exc:
        raise ProviderHTTPError("provider returned non-JSON response") from exc
    except requests.exceptions.HTTPError as exc:
        response = exc.response
        detail = None
        try:
            detail = response.json()
        except requests.exceptions.JSONDecodeError:
            detail = response.text[:500]
        raise ProviderHTTPError(f"HTTP {response.status_code}: {detail}") from exc
    except requests.exceptions.Timeout as exc:
        raise ProviderHTTPError("provider request timed out") from exc
    except requests.exceptions.RequestException as exc:
        raise ProviderHTTPError(f"provider request failed: {exc}") from exc
```

## OpenAI-Compatible Embeddings

```python
def embed(base_url, api_key, model, texts):
    data = post_json(
        f"{base_url.rstrip('/')}/v1/embeddings",
        api_key,
        {"model": model, "input": texts},
    )
    return [item["embedding"] for item in data["data"]]


vectors = embed(
    "https://api.openai.com",
    api_key="sk-...",
    model="text-embedding-3-small",
    texts=["egrep provider docs", "requests timeout handling"],
)
```

## OpenAI-Compatible Rerank

```python
def rerank(base_url, api_key, model, query, documents, top_n=10):
    return post_json(
        f"{base_url.rstrip('/')}/v1/rerank",
        api_key,
        {
            "model": model,
            "query": query,
            "documents": documents,
            "top_n": top_n,
            "return_documents": True,
        },
    )["data"]


hits = rerank(
    "https://provider.example.com",
    api_key="...",
    model="bge-reranker-v2-m3",
    query="requests JSON timeout error handling",
    documents=[
        {"id": "1", "text": "Use json= to send JSON bodies."},
        {"id": "2", "text": "Use timeout to avoid indefinite hangs."},
    ],
    top_n=2,
)
```

## Provider-Specific Headers

```python
# Bearer-token OpenAI-compatible providers
headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

# Pinecone rerank
headers = {
    "Api-Key": api_key,
    "X-Pinecone-Api-Version": "2026-04",
    "Content-Type": "application/json",
    "Accept": "application/json",
}
```

## Pinecone-Style Rerank

```python
def pinecone_rerank(api_key, model, query, documents, top_n=10):
    return post_json(
        "https://api.pinecone.io/rerank",
        api_key=None,
        extra_headers={
            "Api-Key": api_key,
            "X-Pinecone-Api-Version": "2026-04",
        },
        body={
            "model": model,
            "query": query,
            "documents": documents,
            "top_n": top_n,
            "return_documents": True,
        },
    )["data"]
```

## Notes

- `timeout` is socket inactivity timeout, not total wall-clock request time.
- Without `timeout`, `requests` can hang indefinitely.
- `r.json()` success does not mean HTTP success; call `raise_for_status()` first.
- `json=body` serializes JSON and sets the JSON content type.
- All `requests` explicit exceptions inherit from `requests.exceptions.RequestException`.

## Sources

- [Requests Quickstart](https://docs.python-requests.org/en/latest/user/quickstart/)
- [Requests API Reference](https://docs.python-requests.org/en/api/)
- [Requests PyPI](https://pypi.org/project/requests/)
- [OpenAI Embeddings API Reference](https://platform.openai.com/docs/api-reference/embeddings?lang=curl)
- [OpenAI API Authentication](https://platform.openai.com/docs/api-reference/introduction/tokenization)
- [Pinecone 2026-04 Rerank API](https://docs.pinecone.io/reference/api/2026-04/inference/rerank)
- [Heroku `/v1/rerank` API](https://devcenter.heroku.com/articles/heroku-inference-api-v1-rerank)
- [ZeroEntropy Rerank API](https://docs.zeroentropy.dev/api-reference/models/rerank)
- [GPUStack Rerank API](https://docs.gpustack.ai/2.0/user-guide/rerank-api/)
