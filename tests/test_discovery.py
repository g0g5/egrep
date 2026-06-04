from __future__ import annotations

from pathlib import Path

import pytest

from wegrep.discovery import (
    classify_workspace_file,
    discover_workspace_files,
    parse_file_size,
)


def paths(files) -> list[str]:
    return [file.relative_path for file in files]


def test_parse_file_size_units() -> None:
    assert parse_file_size("512") == 512
    assert parse_file_size("1KB") == 1024
    assert parse_file_size("1.5MB") == 1572864


def test_discover_uses_built_in_ignores_and_gitignore(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "keep.py").write_text("print('keep')\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "ignored.py").write_text("ignored\n", encoding="utf-8")
    (tmp_path / ".direnv").mkdir()
    (tmp_path / ".direnv" / "flake.nix").write_text("ignored\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg.js").write_text("ignored\n", encoding="utf-8")
    (tmp_path / "ignored.log").write_text("ignored\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("ignored.log\n", encoding="utf-8")

    files = discover_workspace_files(tmp_path)

    assert paths(files) == [".gitignore", "src/keep.py"]


def test_discover_applies_include_and_exclude_filters(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "src" / "keep.py").write_text("print('keep')\n", encoding="utf-8")
    (tmp_path / "src" / "skip.py").write_text("print('skip')\n", encoding="utf-8")
    (tmp_path / "docs" / "keep.md").write_text("# keep\n", encoding="utf-8")

    files = discover_workspace_files(
        tmp_path,
        includes=["src/**"],
        excludes=["src/skip.py"],
    )

    assert paths(files) == ["src/keep.py"]


def test_discover_skips_oversized_binary_and_non_utf8_files(tmp_path: Path) -> None:
    (tmp_path / "small.txt").write_text("small\n", encoding="utf-8")
    (tmp_path / "large.txt").write_text("too large\n", encoding="utf-8")
    (tmp_path / "binary.bin").write_bytes(b"abc\x00def")
    (tmp_path / "latin.txt").write_bytes("cafe".encode("latin-1") + b"\xff")

    files = discover_workspace_files(tmp_path, max_file_size="8B")

    assert paths(files) == ["small.txt"]


def test_discover_skips_unreadable_files(monkeypatch, tmp_path: Path) -> None:
    unreadable = tmp_path / "unreadable.txt"
    unreadable.write_text("secret\n", encoding="utf-8")

    original_read_bytes = Path.read_bytes

    def fail_read(path: Path) -> bytes:
        if path == unreadable:
            raise OSError("permission denied")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", fail_read)

    assert discover_workspace_files(tmp_path) == []


@pytest.mark.parametrize(
    ("name", "expected_type"),
    [
        ("app.py", "code"),
        ("README.md", "markdown"),
        ("notes.txt", "text"),
        ("Dockerfile", "text"),
    ],
)
def test_classify_file_types(tmp_path: Path, name: str, expected_type: str) -> None:
    path = tmp_path / name
    path.write_text("hello\n", encoding="utf-8")

    workspace_file = classify_workspace_file(
        path,
        relative_path=name,
        max_bytes=parse_file_size("1MB"),
    )

    assert workspace_file is not None
    assert workspace_file.file_type == expected_type
    assert workspace_file.text == "hello\n"
