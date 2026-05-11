from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from .config import run_config
from .errors import EgrepError
from .indexing import run_init
from .retrieval import run_query


COMMANDS = {"init", "config"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="egrep")
    sub = parser.add_subparsers(dest="command")

    init = sub.add_parser("init")
    init.add_argument("--root", default=".")
    init.add_argument("--collection", default="default")
    init.add_argument("--include", action="append", default=[])
    init.add_argument("--exclude", action="append", default=[])
    init.add_argument("--max-file-size", default="1MB")

    config = sub.add_parser("config")
    config.add_argument("--global", dest="global_config", action="store_true")

    return parser


def build_query_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="egrep")
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--no-rerank", action="store_true")
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] not in COMMANDS and args[0] not in {"-h", "--help"}:
        namespace = build_query_parser().parse_args(args)
        namespace.command = "query"
        return namespace
    return build_parser().parse_args(args)


def _run_command(args: argparse.Namespace) -> int:
    if args.command == "init":
        return run_init(args)
    if args.command == "config":
        return run_config(args)
    if args.command == "query":
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
