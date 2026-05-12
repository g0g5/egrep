from __future__ import annotations

import argparse
import builtins

from egrep.cli import build_parser, dispatch, parse_args
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


def test_parse_config_ignores_grep_color_alias_option() -> None:
    args = parse_args(["--color=auto", "config"])

    assert args.command == "config"
    assert args.global_config is False


def test_parse_query_ignores_grep_color_alias_option() -> None:
    args = parse_args(["--color", "auto", "where is config loaded"])

    assert args.command == "query"
    assert args.query == "where is config loaded"


def test_help_lists_config_command() -> None:
    help_text = build_parser().format_help()

    assert "config" in help_text
    assert "configure embedding and reranking providers" in help_text


def test_config_help_lists_global_option(capsys) -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["config", "--help"])

    help_text = capsys.readouterr().out
    assert "--global" in help_text
    assert "write fallback provider configuration" in help_text


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


def test_dispatch_config_does_not_import_indexing_or_retrieval(monkeypatch) -> None:
    def ok_config(args: argparse.Namespace) -> int:
        return 0

    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name in {"egrep.indexing", "egrep.retrieval"}:
            raise AssertionError(f"unexpected import: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("egrep.cli.run_config", ok_config)
    monkeypatch.setattr(builtins, "__import__", guarded_import)

    assert dispatch(parse_args(["config"])) == 0


def test_dispatch_init_renders_progress_to_stderr_and_summary_to_stdout(monkeypatch, capsys) -> None:
    from egrep.indexing import InitProgress

    def fake_run_init(args: argparse.Namespace, progress=None) -> int:
        assert progress is not None
        progress(InitProgress("discover", current=1, total=1, path="src/app.py"))
        progress(InitProgress("write_manifest", current=1, total=1, message="wrote manifest"))
        print("indexed 1 files, 1 retrieval chunks, 1 display chunks")
        return 0

    monkeypatch.setattr("egrep.indexing.run_init", fake_run_init)

    assert dispatch(parse_args(["init"])) == 0

    captured = capsys.readouterr()
    assert captured.out == "indexed 1 files, 1 retrieval chunks, 1 display chunks\n"
    assert "discover 1/1: src/app.py" in captured.err
    assert "write manifest 1/1 wrote manifest" in captured.err
