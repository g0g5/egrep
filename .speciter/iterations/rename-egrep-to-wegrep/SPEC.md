# Rename egrep To wegrep

## Goal

Rename the product from `egrep` to `wegrep` to avoid overlapping with the existing Unix-like `egrep` tool. The rename must cover product-facing behavior, Python import/package names, distribution metadata, command names, workspace/global state paths, docs, tests, and generated product metadata with no compatibility alias or migration for the old name.

## Background

The current project is a Python 3.12 CLI named `egrep` with a `src/egrep/` package, an installed `egrep` console script, and `python -m egrep` module entrypoint. `pyproject.toml` declares `[project] name = "egrep"` and `[project.scripts] egrep = "egrep.cli:main"` using Hatchling as the build backend.

Runtime state currently uses `.egrep/` in the workspace and `~/.config/egrep/provider.json` for global config. Index artifacts include `.egrep/manifest.json`, `.egrep/docstore.jsonl`, `.egrep/chroma/`, `.egrep/bm25/`, and Chroma collection names prefixed with `egrep_`.

User-facing references appear in `README.md`, CLI help/errors, the packaged skill at `src/egrep/skills/SKILL.md`, tests, and launcher/import paths. Historical `.speciter` iteration notes and research notes contain old-name references but are not product files.

## Requirements

1. Rename the Python package directory from `src/egrep/` to `src/wegrep/` and update all product imports, monkeypatch paths, resource lookups, and `python -m` behavior accordingly.
2. Rename the installed console command from `egrep` to `wegrep`; do not keep an `egrep` command alias.
3. Rename the distribution/project metadata from `egrep` to `wegrep` in `pyproject.toml` and regenerate `uv.lock` with `uv`, not manual lock editing.
4. Rename workspace state paths from `.egrep/` to `.wegrep/` and global config paths from `~/.config/egrep/` to `~/.config/wegrep/`.
5. Rename generated/index metadata that embeds the product name, including Chroma collection prefixes from `egrep_` to `wegrep_`.
6. Rename product-facing errors, help text, install instructions, command examples, packaged skill name/path, and README content from `egrep` to `wegrep`.
7. Rename product tests and expectations to the new package, command, paths, and messages.
8. Preserve functional behavior apart from the rename: indexing, config, search, list, skill install/uninstall, providers, retrieval, chunking, and output semantics must remain unchanged.
9. Do not add migration, fallback, compatibility aliases, or old-path detection for `.egrep`, `~/.config/egrep`, `egrep_*`, `egrep` commands, or `egrep` imports.
10. Update repository/project-name references in product docs where feasible, such as install URLs and examples, to use `wegrep`.

## Acceptance Criteria

1. `uv run pytest` passes.
2. `uv build` succeeds and produces `wegrep` distribution artifacts.
3. `uv run wegrep --help` shows `usage: wegrep` and no product-facing `egrep` command text.
4. `uv run python -m wegrep --help` works.
5. The project does not define an `egrep` console script in `pyproject.toml`.
6. `wegrep config` writes workspace config to `.wegrep/provider.json` by default and global config to `~/.config/wegrep/provider.json` with `--global`.
7. `wegrep init` writes `.wegrep/manifest.json`, `.wegrep/docstore.jsonl`, `.wegrep/chroma/`, and `.wegrep/bm25/` while preserving `.wegrep/provider.json`.
8. Missing config/index messages instruct users to run `wegrep config` or `wegrep init`.
9. Packaged skill install/uninstall uses `~/.claude/skills/wegrep` and skill frontmatter `name: wegrep`.
10. Source search for product/runtime files finds no remaining `egrep`, `Egrep`, or `EGREP` references except intentionally excluded historical `.speciter` notes or external references needed to explain the old Unix tool conflict.

## Scope

Expected areas to touch:

- `pyproject.toml` and `uv.lock`
- `main.py`
- `src/egrep/` renamed to `src/wegrep/`
- `src/wegrep/cli.py`, `config.py`, `indexing.py`, `retrieval.py`, `list.py`, `errors.py`, `__main__.py`, `__init__.py`, and packaged skill files
- tests under `tests/`
- `README.md`
- product-relevant repository/project references and install examples

Out-of-repo actions such as physically renaming the parent checkout directory or remote GitHub repository are only in scope as documented references; actual remote/repository operations require a separate explicit request.

## Non-Goals

1. No migration from `.egrep/` to `.wegrep/`.
2. No fallback to `~/.config/egrep/provider.json`.
3. No support for old Chroma collection names prefixed with `egrep_`.
4. No `egrep` command alias, deprecation wrapper, or compatibility script.
5. No support for `python -m egrep` or `import egrep` after the rename.
6. No behavior changes to indexing, retrieval ranking, provider APIs, chunking, output formatting, or prompts beyond renamed strings and paths.
7. No broad rewrite of historical `.speciter` iteration notes or prior research docs.

## Behavior Details

Inputs remain the same except command/module names change to `wegrep` and `python -m wegrep`. Existing command arguments such as `init`, `config`, `list`, `--root`, `--include`, `--exclude`, `--top-k`, `--no-rerank`, and `--verbose` keep their current semantics.

Outputs and filesystem paths must use `wegrep` names. Workspace config/index state is created under `.wegrep/`; global config is read from and written to `~/.config/wegrep/provider.json`. The application must ignore old `.egrep/` and `~/.config/egrep/` locations because no compatibility is required.

Error handling remains aligned with existing expected error classes and exit codes. If `EgrepError` is renamed to `WegrepError`, all imports, catches, and tests must move together without changing exit-code behavior.

Edge cases:

- Existing users with only `.egrep/` state should receive normal missing-config or missing-index errors that mention `wegrep` commands.
- System `/bin/egrep` may still exist; the project must not install its own `egrep` script.
- Resource loading for packaged skills must use the renamed package, for example `importlib.resources.files("wegrep")`.
- Built-in ignore docs should mention `.wegrep/`; discovery already ignores hidden directories broadly, but explicit product docs/tests should reflect the new state directory.

## Dependencies And Research

No new runtime library is required for this rename. Existing runtime dependencies remain in place.

Key tooling/docs reviewed:

- `.speciter/docs/pytest.md`: existing pytest notes for imports, monkeypatching, temporary paths, and CLI testing.
- `.speciter/docs/uv-rename-packaging.md`: current `uv` lock/build/editable install guidance; use `uv lock`, `uv sync`, `uv run`, and `uv build` after project metadata changes.
- `.speciter/docs/hatchling-rename-packaging.md`: Hatchling package discovery, `[project.scripts]`, and wheel build target guidance.

## Verification

Run these checks after implementation:

```sh
uv lock
uv run pytest
uv build
uv run wegrep --help
uv run python -m wegrep --help
```

Manual or targeted checks:

```sh
uv run wegrep config
uv run wegrep config --global
uv run wegrep init --root . --max-file-size 2MB
uv run wegrep list
uv run wegrep "where is provider configuration loaded?" --no-rerank
```

Search checks:

```sh
rg 'egrep|Egrep|EGREP' pyproject.toml README.md main.py src tests
```

Expected remaining matches should be none in product/runtime files unless a reference is intentionally retained to describe the Unix command conflict.

## Shifts

N/A. No requirement, scope, acceptance, behavior, dependency, or verification shifts have occurred yet.
