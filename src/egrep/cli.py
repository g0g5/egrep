from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from .config import run_config
from .errors import EgrepError


COMMANDS = {"init", "config"}
IGNORED_COMPAT_OPTIONS = {"--color", "--colour"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="egrep",
        description="Hybrid workspace search CLI for coding agents",
    )
    sub = parser.add_subparsers(dest="command", metavar="command")

    init = sub.add_parser(
        "init",
        help="build or rebuild a workspace index",
        description="Build or rebuild a workspace index.",
    )
    init.add_argument("--root", default=".")
    init.add_argument("--collection", default="default")
    init.add_argument("--include", action="append", default=[])
    init.add_argument("--exclude", action="append", default=[])
    init.add_argument("--max-file-size", default="1MB")

    config = sub.add_parser(
        "config",
        help="configure embedding and reranking providers",
        description="Configure embedding and reranking providers.",
    )
    config.add_argument(
        "--global",
        dest="global_config",
        action="store_true",
        help="write fallback provider configuration under ~/.config/egrep",
    )

    return parser


def build_query_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="egrep")
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--no-rerank", action="store_true")
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    args = _strip_compat_options(list(sys.argv[1:] if argv is None else argv))
    if args and args[0] not in COMMANDS and args[0] not in {"-h", "--help"}:
        namespace = build_query_parser().parse_args(args)
        namespace.command = "query"
        return namespace
    return build_parser().parse_args(args)


def _strip_compat_options(args: list[str]) -> list[str]:
    normalized: list[str] = []
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg in IGNORED_COMPAT_OPTIONS:
            skip_next = True
            continue
        if any(arg.startswith(f"{option}=") for option in IGNORED_COMPAT_OPTIONS):
            continue
        normalized.append(arg)
    return normalized


def _run_command(args: argparse.Namespace) -> int:
    if args.command == "init":
        from .indexing import run_init

        return run_init(args)
    if args.command == "config":
        return run_config(args)
    if args.command == "query":
        from .retrieval import run_query

        return run_query(args)

    build_parser().print_help(sys.stderr)
    return 2


def dispatch(args: argparse.Namespace) -> int:
    try:
        return _run_command(args)
    except EgrepError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code
    except Exception as exc:
        print(f"unexpected error: {exc}", file=sys.stderr)
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    return dispatch(parse_args(argv))
