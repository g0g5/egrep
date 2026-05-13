from __future__ import annotations

import argparse
import json
from pathlib import Path

from .errors import IndexNotFoundError


def run_list(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    manifest_path = root / ".egrep" / "manifest.json"
    if not manifest_path.exists():
        raise IndexNotFoundError("index not found; run `egrep init` first")

    docstore_path = root / ".egrep" / "docstore.jsonl"
    paths: set[str] = set()
    if docstore_path.exists():
        with docstore_path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                chunk = json.loads(line)
                paths.add(chunk["path"])

    tree = _build_tree(sorted(paths))
    _print_tree(tree)
    print(f"\n{len(paths)} files indexed")
    return 0


def _build_tree(paths: list[str]) -> dict:
    root: dict = {}
    for path in paths:
        parts = path.split("/")
        node = root
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node.setdefault("__files__", []).append(parts[-1])
    return root


def _print_tree(tree: dict, prefix: str = "") -> None:
    entries = sorted(tree.items(), key=lambda x: (not isinstance(x[1], list), x[0]))
    for index, (name, subtree) in enumerate(entries):
        is_last = index == len(entries) - 1
        connector = "└── " if is_last else "├── "
        if isinstance(subtree, list):
            for file_index, filename in enumerate(sorted(subtree)):
                file_last = file_index == len(subtree) - 1
                file_connector = "└── " if is_last and file_last else "├── "
                indent = prefix + ("    " if is_last else "│   ")
                print(f"{prefix}{file_connector}{filename}")
        else:
            print(f"{prefix}{connector}{name}/")
            indent = prefix + ("    " if is_last else "│   ")
            _print_tree(subtree, indent)
