from __future__ import annotations

import argparse

from egrep.cli import dispatch, parse_args
import pytest

from egrep.errors import IndexNotFoundError, IndexWriteError, ProviderAPIError, ProviderConfigError


def test_parse_init_defaults() -> None:
    args = parse_args(["init"])

    assert args.command == "init"
    assert args.root == "."
    assert args.collection == "default"
    assert args.include == []
    assert args.exclude == []
    assert args.max_file_size == "1MB"


def test_parse_config_global() -> None:
    args = parse_args(["config", "--global"])

    assert args.command == "config"
    assert args.global_config is True


def test_parse_query_options() -> None:
    args = parse_args(["where is config loaded", "--top-k", "5", "-v", "--no-rerank"])

    assert args.command == "query"
    assert args.query == "where is config loaded"
    assert args.top_k == 5
    assert args.verbose is True
    assert args.no_rerank is True


@pytest.mark.parametrize(
    ("error", "exit_code"),
    [
        (IndexNotFoundError("index not found"), 3),
        (ProviderConfigError("provider configuration missing"), 4),
        (ProviderAPIError("provider request failed"), 5),
        (IndexWriteError("failed to write index"), 6),
    ],
)
def test_dispatch_returns_documented_expected_exit_codes(monkeypatch, error, exit_code) -> None:
    def fail_config(args: argparse.Namespace) -> int:
        raise error

    monkeypatch.setattr("egrep.cli.run_config", fail_config)

    assert dispatch(parse_args(["config"])) == exit_code


def test_dispatch_returns_one_for_unexpected_errors(monkeypatch) -> None:
    def fail_config(args: argparse.Namespace) -> int:
        raise RuntimeError("boom")

    monkeypatch.setattr("egrep.cli.run_config", fail_config)

    assert dispatch(parse_args(["config"])) == 1
