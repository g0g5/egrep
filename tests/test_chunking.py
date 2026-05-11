from __future__ import annotations

from pathlib import Path

from egrep.chunking import chunk_workspace_file, read_docstore, write_docstore
from egrep.discovery import WorkspaceFile


def workspace_file(tmp_path: Path, name: str, file_type: str, text: str) -> WorkspaceFile:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return WorkspaceFile(path=path, relative_path=name, file_type=file_type, text=text)


def test_text_files_use_overlapped_standalone_chunks(tmp_path: Path) -> None:
    text = "".join(f"line {line}\n" for line in range(1, 151))

    chunked = chunk_workspace_file(workspace_file(tmp_path, "notes.txt", "text", text))

    assert [(chunk.start_line, chunk.end_line) for chunk in chunked.retrieval_chunks] == [
        (1, 120),
        (101, 150),
    ]
    assert [chunk.chunk_role for chunk in chunked.retrieval_chunks] == ["standalone", "standalone"]
    assert len(chunked.display_chunks) == 2
    assert chunked.retrieval_chunks[0].metadata["display_start_line"] == 1
    assert chunked.retrieval_chunks[0].metadata["display_end_line"] == 120


def test_code_chunks_include_required_stable_metadata(tmp_path: Path) -> None:
    text = "def foo():\n    return 1\n\nclass Bar:\n    pass\n"
    file = workspace_file(tmp_path, "src/app.py", "code", text)

    first = chunk_workspace_file(file)
    second = chunk_workspace_file(file)

    assert [chunk.chunk_id for chunk in first.retrieval_chunks] == [
        chunk.chunk_id for chunk in second.retrieval_chunks
    ]
    metadata = first.retrieval_chunks[0].metadata
    assert set(metadata) == {
        "chunk_id",
        "display_chunk_id",
        "parent_chunk_id",
        "chunk_role",
        "type",
        "path",
        "start_line",
        "end_line",
        "display_start_line",
        "display_end_line",
        "content_hash",
        "file_hash",
    }
    assert metadata["path"] == "src/app.py"
    assert metadata["type"] == "code"
    assert metadata["content_hash"]
    assert metadata["file_hash"]


def test_code_functions_and_classes_are_display_chunks(tmp_path: Path) -> None:
    text = "def foo():\n    return 1\n\nclass Bar:\n    pass\n"

    chunked = chunk_workspace_file(workspace_file(tmp_path, "src/app.py", "code", text))

    assert [chunk.text for chunk in chunked.display_chunks] == [
        "def foo():\n    return 1\n\n",
        "class Bar:\n    pass\n",
    ]


def test_markdown_sections_are_display_chunks(tmp_path: Path) -> None:
    text = "# One\nfirst\n\n## Two\nsecond\n"

    chunked = chunk_workspace_file(workspace_file(tmp_path, "README.md", "markdown", text))

    assert len(chunked.display_chunks) == 2
    assert chunked.display_chunks[0].text.startswith("# One")
    assert chunked.display_chunks[1].text.startswith("## Two")


def test_overlong_code_display_chunk_creates_children(tmp_path: Path) -> None:
    text = "def large():\n" + "".join(f"    value_{line} = {line}\n" for line in range(1, 151))

    chunked = chunk_workspace_file(workspace_file(tmp_path, "large.py", "code", text))

    assert len(chunked.display_chunks) == 1
    assert len(chunked.retrieval_chunks) == 2
    assert {chunk.chunk_role for chunk in chunked.retrieval_chunks} == {"child"}
    assert {chunk.parent_chunk_id for chunk in chunked.retrieval_chunks} == {
        chunked.display_chunks[0].display_chunk_id
    }
    assert {chunk.display_chunk_id for chunk in chunked.retrieval_chunks} == {
        chunked.display_chunks[0].display_chunk_id
    }
    assert chunked.retrieval_chunks[0].display_end_line == 151


def test_overlong_markdown_display_chunk_creates_children(tmp_path: Path) -> None:
    text = "# Large\n" + "".join(f"line {line}\n" for line in range(1, 151))

    chunked = chunk_workspace_file(workspace_file(tmp_path, "README.md", "markdown", text))

    assert len(chunked.display_chunks) == 1
    assert len(chunked.retrieval_chunks) == 2
    assert {chunk.chunk_role for chunk in chunked.retrieval_chunks} == {"child"}
    assert {chunk.parent_chunk_id for chunk in chunked.retrieval_chunks} == {
        chunked.display_chunks[0].display_chunk_id
    }
    assert chunked.retrieval_chunks[0].display_end_line == 151


def test_docstore_persists_display_chunks_by_id(tmp_path: Path) -> None:
    chunked = chunk_workspace_file(workspace_file(tmp_path, "notes.txt", "text", "hello\n"))
    docstore_path = tmp_path / ".egrep" / "docstore.jsonl"

    write_docstore(docstore_path, chunked.display_chunks)

    loaded = read_docstore(docstore_path)
    assert loaded == {chunk.display_chunk_id: chunk for chunk in chunked.display_chunks}
