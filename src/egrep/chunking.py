from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .discovery import WorkspaceFile


CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".sh",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
}

MARKDOWN_EXTENSIONS = {".md", ".mdx", ".rst"}
TEXT_EXTENSIONS = {".txt", ".log", ".ini", ".cfg"}

CODE_LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".sh": "bash",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
}

DISPLAY_MAX_LINES = 120
DISPLAY_MAX_CHARS = 4000
TEXT_CHUNK_LINES = 120
TEXT_CHUNK_OVERLAP = 20


@dataclass(frozen=True)
class DisplayChunk:
    display_chunk_id: str
    type: str
    path: str
    start_line: int
    end_line: int
    content_hash: str
    file_hash: str
    text: str


@dataclass(frozen=True)
class RetrievalChunk:
    chunk_id: str
    display_chunk_id: str
    parent_chunk_id: str | None
    chunk_role: str
    type: str
    path: str
    start_line: int
    end_line: int
    display_start_line: int
    display_end_line: int
    content_hash: str
    file_hash: str
    text: str

    @property
    def metadata(self) -> dict[str, str | int | None]:
        return {
            "chunk_id": self.chunk_id,
            "display_chunk_id": self.display_chunk_id,
            "parent_chunk_id": self.parent_chunk_id,
            "chunk_role": self.chunk_role,
            "type": self.type,
            "path": self.path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "display_start_line": self.display_start_line,
            "display_end_line": self.display_end_line,
            "content_hash": self.content_hash,
            "file_hash": self.file_hash,
        }


@dataclass(frozen=True)
class ChunkedFile:
    retrieval_chunks: list[RetrievalChunk]
    display_chunks: list[DisplayChunk]


def chunk_workspace_file(workspace_file: WorkspaceFile) -> ChunkedFile:
    if workspace_file.file_type == "code":
        spans = _code_display_spans(workspace_file)
    elif workspace_file.file_type == "markdown":
        spans = _markdown_display_spans(workspace_file)
    else:
        spans = _text_display_spans(workspace_file.text)

    return _build_chunks(workspace_file, spans)


def chunk_workspace_files(
    files: list[WorkspaceFile],
    progress: Callable[[WorkspaceFile | None, int, int], None] | None = None,
) -> ChunkedFile:
    retrieval_chunks: list[RetrievalChunk] = []
    display_chunks: list[DisplayChunk] = []
    if not files and progress is not None:
        progress(None, 0, 0)
    for index, workspace_file in enumerate(files, start=1):
        if progress is not None:
            progress(workspace_file, index, len(files))
        chunked = chunk_workspace_file(workspace_file)
        retrieval_chunks.extend(chunked.retrieval_chunks)
        display_chunks.extend(chunked.display_chunks)
    return ChunkedFile(retrieval_chunks=retrieval_chunks, display_chunks=display_chunks)


def write_docstore(
    path: Path,
    display_chunks: list[DisplayChunk],
    progress: Callable[[DisplayChunk | None, int, int], None] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        if not display_chunks and progress is not None:
            progress(None, 0, 0)
        for index, chunk in enumerate(display_chunks, start=1):
            if progress is not None:
                progress(chunk, index, len(display_chunks))
            file.write(json.dumps(asdict(chunk), sort_keys=True) + "\n")


def read_docstore(path: Path) -> dict[str, DisplayChunk]:
    chunks: dict[str, DisplayChunk] = {}
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            chunk = DisplayChunk(**json.loads(line))
            chunks[chunk.display_chunk_id] = chunk
    return chunks


def _build_chunks(workspace_file: WorkspaceFile, spans: list[tuple[int, int]]) -> ChunkedFile:
    file_hash = _sha256(workspace_file.text)
    retrieval_chunks: list[RetrievalChunk] = []
    display_chunks: list[DisplayChunk] = []

    for start_line, end_line in spans:
        text = _slice_lines(workspace_file.text, start_line, end_line)
        display_chunk_id = _stable_id("display", workspace_file.relative_path, start_line, end_line, text)
        display_chunk = DisplayChunk(
            display_chunk_id=display_chunk_id,
            type=workspace_file.file_type,
            path=workspace_file.relative_path,
            start_line=start_line,
            end_line=end_line,
            content_hash=_sha256(text),
            file_hash=file_hash,
            text=text,
        )
        display_chunks.append(display_chunk)

        if workspace_file.file_type in {"code", "markdown"} and _is_overlong(text):
            child_spans = _overlapped_line_spans(start_line, end_line, TEXT_CHUNK_LINES, TEXT_CHUNK_OVERLAP)
            for child_start, child_end in child_spans:
                child_text = _slice_lines(workspace_file.text, child_start, child_end)
                retrieval_chunks.append(
                    _retrieval_chunk(
                        workspace_file,
                        display_chunk,
                        child_text,
                        child_start,
                        child_end,
                        chunk_role="child",
                        parent_chunk_id=display_chunk_id,
                    )
                )
        else:
            retrieval_chunks.append(
                _retrieval_chunk(
                    workspace_file,
                    display_chunk,
                    text,
                    start_line,
                    end_line,
                    chunk_role="standalone",
                    parent_chunk_id=None,
                )
            )

    return ChunkedFile(retrieval_chunks=retrieval_chunks, display_chunks=display_chunks)


def _retrieval_chunk(
    workspace_file: WorkspaceFile,
    display_chunk: DisplayChunk,
    text: str,
    start_line: int,
    end_line: int,
    *,
    chunk_role: str,
    parent_chunk_id: str | None,
) -> RetrievalChunk:
    return RetrievalChunk(
        chunk_id=_stable_id("retrieval", workspace_file.relative_path, start_line, end_line, text),
        display_chunk_id=display_chunk.display_chunk_id,
        parent_chunk_id=parent_chunk_id,
        chunk_role=chunk_role,
        type=workspace_file.file_type,
        path=workspace_file.relative_path,
        start_line=start_line,
        end_line=end_line,
        display_start_line=display_chunk.start_line,
        display_end_line=display_chunk.end_line,
        content_hash=_sha256(text),
        file_hash=display_chunk.file_hash,
        text=text,
    )


def _code_display_spans(workspace_file: WorkspaceFile) -> list[tuple[int, int]]:
    suffix = workspace_file.path.suffix.lower()
    language = CODE_LANGUAGE_BY_EXTENSION.get(suffix)
    if language is None:
        return [(1, _line_count(workspace_file.text))]

    try:
        from llama_index.core import Document
        from llama_index.core.node_parser import CodeSplitter

        nodes = CodeSplitter(
            language=language,
            chunk_lines=DISPLAY_MAX_LINES,
            chunk_lines_overlap=TEXT_CHUNK_OVERLAP,
            max_chars=DISPLAY_MAX_CHARS,
        ).get_nodes_from_documents([Document(text=workspace_file.text)])
    except Exception:
        return _fallback_code_spans(workspace_file.text)

    return _node_spans(workspace_file.text, [(node.start_char_idx, node.end_char_idx) for node in nodes])


def _markdown_display_spans(workspace_file: WorkspaceFile) -> list[tuple[int, int]]:
    try:
        from llama_index.core import Document
        from llama_index.core.node_parser import MarkdownNodeParser

        nodes = MarkdownNodeParser().get_nodes_from_documents([Document(text=workspace_file.text)])
    except Exception:
        return _fallback_markdown_spans(workspace_file.text)

    return _node_spans(workspace_file.text, [(node.start_char_idx, node.end_char_idx) for node in nodes])


def _text_display_spans(text: str) -> list[tuple[int, int]]:
    return _overlapped_line_spans(1, _line_count(text), TEXT_CHUNK_LINES, TEXT_CHUNK_OVERLAP)


def _fallback_code_spans(text: str) -> list[tuple[int, int]]:
    lines = text.splitlines() or [""]
    starts = [
        index
        for index, line in enumerate(lines, start=1)
        if line.startswith(("def ", "class ", "async def "))
    ]
    if not starts:
        return [(1, len(lines))]
    spans: list[tuple[int, int]] = []
    if starts[0] > 1:
        spans.append((1, starts[0] - 1))
    for index, start in enumerate(starts):
        end = starts[index + 1] - 1 if index + 1 < len(starts) else len(lines)
        spans.append((start, end))
    return spans


def _fallback_markdown_spans(text: str) -> list[tuple[int, int]]:
    lines = text.splitlines() or [""]
    starts = [index for index, line in enumerate(lines, start=1) if line.startswith("#")]
    if not starts:
        return [(1, len(lines))]
    spans: list[tuple[int, int]] = []
    if starts[0] > 1:
        spans.append((1, starts[0] - 1))
    for index, start in enumerate(starts):
        end = starts[index + 1] - 1 if index + 1 < len(starts) else len(lines)
        spans.append((start, end))
    return spans


def _node_spans(text: str, char_spans: list[tuple[int | None, int | None]]) -> list[tuple[int, int]]:
    spans = []
    for start_char, end_char in char_spans:
        if start_char is None or end_char is None:
            continue
        spans.append((_line_for_char(text, start_char), _line_for_char(text, max(start_char, end_char - 1))))
    return _dedupe_spans(spans) or [(1, _line_count(text))]


def _dedupe_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    deduped: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for start, end in spans:
        normalized = (max(1, start), max(start, end))
        if normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return deduped


def _overlapped_line_spans(start_line: int, end_line: int, target_lines: int, overlap: int) -> list[tuple[int, int]]:
    if end_line <= start_line + target_lines - 1:
        return [(start_line, end_line)]
    spans = []
    current = start_line
    step = max(1, target_lines - overlap)
    while current <= end_line:
        chunk_end = min(end_line, current + target_lines - 1)
        spans.append((current, chunk_end))
        if chunk_end == end_line:
            break
        current += step
    return spans


def _slice_lines(text: str, start_line: int, end_line: int) -> str:
    lines = text.splitlines(keepends=True) or [""]
    return "".join(lines[start_line - 1 : end_line])


def _line_count(text: str) -> int:
    return max(1, len(text.splitlines()))


def _line_for_char(text: str, char_index: int) -> int:
    return text.count("\n", 0, char_index) + 1


def _is_overlong(text: str) -> bool:
    return len(text) > DISPLAY_MAX_CHARS or len(text.splitlines()) > DISPLAY_MAX_LINES


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stable_id(prefix: str, path: str, start_line: int, end_line: int, text: str) -> str:
    digest = _sha256("\0".join([path, str(start_line), str(end_line), _sha256(text)]))[:24]
    return f"{prefix}-{digest}"
