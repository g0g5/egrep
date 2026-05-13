from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pathspec import GitIgnoreSpec

from .chunking import CODE_EXTENSIONS, MARKDOWN_EXTENSIONS, TEXT_EXTENSIONS


BUILT_IN_IGNORES = [
    ".*/",
    "venv/",
    "env/",
    "node_modules/",
    "dist/",
    "build/",
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    "*.so",
    "*.dylib",
    "*.dll",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.webp",
    "*.pdf",
    "*.zip",
    "*.tar",
    "*.gz",
]


@dataclass(frozen=True)
class WorkspaceFile:
    path: Path
    relative_path: str
    file_type: str
    text: str


def parse_file_size(value: str) -> int:
    normalized = value.strip().lower()
    units = (("kb", 1024), ("mb", 1024 * 1024), ("gb", 1024 * 1024 * 1024), ("b", 1))
    for suffix, multiplier in units:
        if normalized.endswith(suffix):
            number = normalized[: -len(suffix)].strip()
            break
    else:
        number = normalized
        multiplier = 1

    try:
        size = float(number)
    except ValueError as exc:
        raise ValueError(f"invalid file size: {value}") from exc
    if size < 0:
        raise ValueError(f"invalid file size: {value}")
    return int(size * multiplier)


def discover_workspace_files(
    root: Path,
    *,
    includes: list[str] | None = None,
    excludes: list[str] | None = None,
    max_file_size: str = "1MB",
    progress: Callable[[Path | None, int, int], None] | None = None,
) -> list[WorkspaceFile]:
    resolved_root = root.resolve()
    max_bytes = parse_file_size(max_file_size)
    ignore_spec = _ignore_spec(resolved_root, excludes or [])
    include_spec = GitIgnoreSpec.from_lines(includes or []) if includes else None
    files: list[WorkspaceFile] = []
    candidate_paths = sorted(path for path in resolved_root.rglob("*") if path.is_file())

    if not candidate_paths and progress is not None:
        progress(None, 0, 0)
    for index, path in enumerate(candidate_paths, start=1):
        if progress is not None:
            progress(path, index, len(candidate_paths))
        relative_path = path.relative_to(resolved_root).as_posix()
        if ignore_spec.match_file(relative_path):
            continue
        if include_spec is not None and not include_spec.match_file(relative_path):
            continue
        workspace_file = classify_workspace_file(
            path,
            relative_path=relative_path,
            max_bytes=max_bytes,
        )
        if workspace_file is not None:
            files.append(workspace_file)

    return files


def classify_workspace_file(
    path: Path,
    *,
    relative_path: str | None = None,
    max_bytes: int,
) -> WorkspaceFile | None:
    try:
        if path.stat().st_size > max_bytes:
            return None
        data = path.read_bytes()
    except OSError:
        return None

    if b"\x00" in data:
        return None

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None

    suffix = path.suffix.lower()
    if suffix in CODE_EXTENSIONS:
        file_type = "code"
    elif suffix in MARKDOWN_EXTENSIONS:
        file_type = "markdown"
    elif suffix in TEXT_EXTENSIONS or suffix not in CODE_EXTENSIONS | MARKDOWN_EXTENSIONS:
        file_type = "text"
    else:
        return None

    return WorkspaceFile(
        path=path,
        relative_path=relative_path or path.name,
        file_type=file_type,
        text=text,
    )


def _ignore_spec(root: Path, excludes: list[str]) -> GitIgnoreSpec:
    lines = list(BUILT_IN_IGNORES)
    gitignore = root / ".gitignore"
    if gitignore.exists():
        try:
            lines.extend(gitignore.read_text(encoding="utf-8", errors="ignore").splitlines())
        except OSError:
            pass
    lines.extend(excludes)
    return GitIgnoreSpec.from_lines(lines)
