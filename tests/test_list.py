from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from wegrep.errors import IndexNotFoundError
from wegrep.list import _build_tree, _print_tree, run_list


def test_run_list_missing_index(tmp_path: Path) -> None:
    args = argparse.Namespace(root=str(tmp_path))
    with pytest.raises(IndexNotFoundError) as excinfo:
        run_list(args)
    assert excinfo.value.exit_code == 3


def test_run_list_empty_index(tmp_path: Path) -> None:
    (tmp_path / ".wegrep").mkdir()
    (tmp_path / ".wegrep" / "manifest.json").write_text(
        json.dumps({"version": 1, "file_count": 0, "root": str(tmp_path)}), encoding="utf-8"
    )
    args = argparse.Namespace(root=str(tmp_path))
    exit_code = run_list(args)
    assert exit_code == 0


def test_run_list_with_files(tmp_path: Path, capsys) -> None:
    (tmp_path / ".wegrep").mkdir()
    (tmp_path / ".wegrep" / "manifest.json").write_text(
        json.dumps({"version": 1, "file_count": 2, "root": str(tmp_path)}), encoding="utf-8"
    )
    docstore = tmp_path / ".wegrep" / "docstore.jsonl"
    with docstore.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"display_chunk_id": "dc-1", "type": "code", "path": "src/app.py", "start_line": 1, "end_line": 5, "content_hash": "abc", "file_hash": "def", "text": "code"}) + "\n")
        f.write(json.dumps({"display_chunk_id": "dc-2", "type": "code", "path": "src/utils/helpers.py", "start_line": 1, "end_line": 10, "content_hash": "ghi", "file_hash": "jkl", "text": "more code"}) + "\n")

    args = argparse.Namespace(root=str(tmp_path))
    exit_code = run_list(args)
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "src/" in captured.out
    assert "app.py" in captured.out
    assert "helpers.py" in captured.out
    assert "utils/" in captured.out
    assert "2 files indexed" in captured.out


def test_build_tree_flat() -> None:
    tree = _build_tree(["app.py", "README.md"])
    assert tree == {"__files__": ["app.py", "README.md"]}


def test_build_tree_nested() -> None:
    tree = _build_tree(["src/app.py", "src/utils/helpers.py", "README.md"])
    assert tree == {
        "__files__": ["README.md"],
        "src": {
            "__files__": ["app.py"],
            "utils": {
                "__files__": ["helpers.py"],
            },
        },
    }


def test_build_tree_empty() -> None:
    assert _build_tree([]) == {}


def test_print_tree_output(capsys) -> None:
    tree = {
        "__files__": ["README.md", "pyproject.toml"],
        "src": {
            "__files__": ["cli.py"],
        },
    }
    _print_tree(tree)
    captured = capsys.readouterr()
    output = captured.out
    assert "README.md" in output
    assert "pyproject.toml" in output
    assert "src/" in output
    assert "cli.py" in output
