# pytest Notes for egrep Unit Tests

## Install

```bash
uv add --dev pytest pytest-httpx responses
```

## Run

```bash
uv run pytest
uv run pytest -q
uv run pytest tests/test_cli.py::test_main_prints_help -q
uv run pytest -k cli -q
```

## CLI: call `main()` directly

```python
# tests/test_cli.py
from main import main


def test_main_prints_message(capsys):
    main()

    assert capsys.readouterr().out == "Hello from egrep!\n"
```

## CLI: patch argv

```python
import sys

from main import main


def test_cli_reads_args(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["egrep", "needle", "file.txt"])

    main()

    out = capsys.readouterr().out
    assert "needle" in out
```

## CLI: subprocess smoke test

```python
import subprocess
import sys


def test_module_runs():
    result = subprocess.run(
        [sys.executable, "main.py"],
        check=True,
        text=True,
        capture_output=True,
    )

    assert result.stdout == "Hello from egrep!\n"
```

## Environment variables

```python
import os


def test_env_enabled(monkeypatch):
    monkeypatch.setenv("EGREP_COLOR", "always")

    assert os.environ["EGREP_COLOR"] == "always"


def test_env_missing(monkeypatch):
    monkeypatch.delenv("EGREP_COLOR", raising=False)

    assert "EGREP_COLOR" not in os.environ
```

## Temporary files: `tmp_path`

```python
def test_searches_file(tmp_path):
    path = tmp_path / "input.txt"
    path.write_text("alpha\nbeta\n", encoding="utf-8")

    assert path.read_text(encoding="utf-8").splitlines() == ["alpha", "beta"]
```

## Temporary cwd

```python
from pathlib import Path


def test_uses_current_directory(monkeypatch, tmp_path):
    (tmp_path / "input.txt").write_text("needle\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert Path("input.txt").read_text(encoding="utf-8") == "needle\n"
```

## Mock HTTPX with `pytest-httpx`

```python
import httpx


def fetch_text(url: str) -> str:
    return httpx.get(url).text


def test_fetch_text(httpx_mock):
    httpx_mock.add_response(url="https://example.test/a", text="ok")

    assert fetch_text("https://example.test/a") == "ok"
```

## Mock `requests` with `responses`

```python
import requests
import responses


def fetch_json(url: str) -> dict:
    return requests.get(url, timeout=5).json()


@responses.activate
def test_fetch_json():
    responses.get("https://example.test/a", json={"ok": True}, status=200)

    assert fetch_json("https://example.test/a") == {"ok": True}
```

## Mock any function with `monkeypatch`

```python
import main


def test_patch_project_function(monkeypatch):
    monkeypatch.setattr(main, "main", lambda: "patched")

    assert main.main() == "patched"
```

## Sources

- https://docs.pytest.org/en/stable/
- https://docs.pytest.org/en/stable/how-to/monkeypatch.html
- https://docs.pytest.org/en/stable/reference/fixtures.html
- https://docs.pytest.org/en/stable/how-to/capture-stdout-stderr.html
- https://docs.pytest.org/en/stable/how-to/tmp_path.html
- https://pypi.org/project/pytest-httpx/
- https://lundberg.github.io/respx/
- https://github.com/getsentry/responses
