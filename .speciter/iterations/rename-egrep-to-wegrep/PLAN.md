# Rename egrep To wegrep Implementation Plan

## Phase 1: Package And Project Metadata

1. Rename the runtime package directory from `src/egrep/` to `src/wegrep/`.
2. Update all imports, module references, monkeypatch targets, and resource lookups from `egrep` to `wegrep`.
3. Update `main.py`, `src/wegrep/__main__.py`, and package entrypoints so `python -m wegrep` works and `python -m egrep` is not supported.
4. Update `pyproject.toml` project metadata from `egrep` to `wegrep`.
5. Replace the console script definition with `wegrep = "wegrep.cli:main"` and remove any `egrep` script definition.
6. Regenerate `uv.lock` using `uv lock` after metadata changes.

Completion log, 2026-06-04 16:22:46 MSK: Renamed the runtime package to `src/wegrep/`, removed moved bytecode cache files, updated package imports, test monkeypatch targets, `main.py`, package resource lookup, project metadata, and console script metadata to `wegrep`, regenerated `uv.lock` with `uv lock`, and verified `uv run pytest`, `uv run wegrep --help`, and `uv run python -m wegrep --help` execute successfully.

## Phase 2: Runtime Names, Paths, And Metadata

1. Replace workspace state paths from `.egrep/` to `.wegrep/` across config, indexing, discovery documentation strings, tests, and error messages.
2. Replace global config paths from `~/.config/egrep/` to `~/.config/wegrep/`.
3. Rename generated product metadata from `egrep` to `wegrep`, including Chroma collection prefixes from `egrep_` to `wegrep_`.
4. If `EgrepError` is renamed to `WegrepError`, update every import, catch, and test expectation together without changing exit-code behavior.
5. Ensure no fallback, migration, alias, old-path lookup, or old collection-name support remains.

Completion log, 2026-06-04 16:25:20 MSK: Updated runtime workspace state paths from `.egrep/` to `.wegrep/`, global provider config paths from `~/.config/egrep/` to `~/.config/wegrep/`, missing-config and missing-index guidance to `wegrep` commands, Chroma collection prefixes from `egrep_` to `wegrep_`, and renamed `EgrepError` to `WegrepError` with exit-code behavior unchanged. Updated matching path and error expectations in config, indexing, retrieval, list, and chunking tests, confirmed no phase 2 old-name path/error leftovers in `src/wegrep` or tests, and verified `uv run pytest` passes.

## Phase 3: CLI And User-Facing Text

1. Update argparse program names, help text, usage output, prompts, and expected error guidance to use `wegrep`.
2. Update missing-config and missing-index messages to instruct users to run `wegrep config` or `wegrep init`.
3. Update command examples and install instructions in product-facing documentation.
4. Update packaged skill resources so install and uninstall target `~/.claude/skills/wegrep`.
5. Update packaged skill frontmatter and content to use `name: wegrep` and the new command/package names.

Completion log, 2026-06-04 16:27:04 MSK: Updated argparse program names and query help usage to `wegrep`, renamed CLI skill install/uninstall help text and destinations to `~/.claude/skills/wegrep`, updated packaged skill frontmatter/content and README product-facing commands, paths, install examples, and documentation text to `wegrep`, adjusted CLI skill dispatch test expectations, and verified `uv run pytest`, `uv run wegrep --help`, and `uv run python -m wegrep --help` pass.

## Phase 4: Tests And Fixtures

1. Rename test imports and monkeypatch paths from `egrep` to `wegrep`.
2. Update CLI tests for the `wegrep` console command and `python -m wegrep` behavior.
3. Update config and indexing tests to expect `.wegrep/`, `~/.config/wegrep/`, and `wegrep_` generated metadata.
4. Update skill install/uninstall tests to expect `~/.claude/skills/wegrep` and `name: wegrep`.
5. Keep functional assertions for indexing, retrieval, config, providers, chunking, output, list, and skill behavior otherwise unchanged.

Completion log, 2026-06-04 16:28:17 MSK: Audited the test suite for remaining standalone `egrep`, `Egrep`, `EGREP`, `.egrep`, and `egrep_` references; confirmed imports, monkeypatch paths, CLI expectations, config/index paths, generated metadata expectations, and skill install/uninstall fixtures already target `wegrep`. Verified functional assertions remain unchanged and `uv run pytest` passes with 80 tests.

## Phase 5: Documentation And Repository References

1. Update `README.md` product references, commands, paths, install URLs, and examples from `egrep` to `wegrep`.
2. Update product-relevant repository references where feasible while leaving historical `.speciter` notes and prior research documents untouched unless they affect product behavior.
3. Retain old-name references only where needed to explain the conflict with the existing Unix-like `egrep` tool.

Completion log, 2026-06-04 16:29:28 MSK: Audited product-facing documentation and repository guidance for old-name references, confirmed `README.md` commands, paths, install URLs, and examples use `wegrep`, corrected the pip VCS install example to `pip install git+https://github.com/g0g5/wegrep`, updated `AGENTS.md` project/package/entrypoint references from `egrep` to `wegrep`, left historical `.speciter` notes untouched, and verified product/runtime files have no unintended old-name documentation references.

## Phase 6: Verification

1. Run `uv lock` after metadata edits and review the generated lockfile changes.
2. Run `uv run pytest` and fix any rename-related failures.
3. Run `uv build` and confirm the generated distribution artifacts use `wegrep`.
4. Run `uv run wegrep --help` and confirm it shows `usage: wegrep` with no product-facing old command text.
5. Run `uv run python -m wegrep --help` and confirm the module entrypoint works.
6. Run targeted config/index checks to confirm `.wegrep/` workspace state and `~/.config/wegrep/provider.json` global config behavior.
7. Run `rg 'egrep|Egrep|EGREP' pyproject.toml README.md main.py src tests` and resolve unintended product/runtime matches.

Completion log, 2026-06-04 16:32:14 MSK: Ran `uv lock` and reviewed the lockfile diff confirming the editable package metadata is now `wegrep`; ran `uv run pytest` with 80 passing tests; ran `uv build` and confirmed `dist/wegrep-0.1.0.tar.gz` and `dist/wegrep-0.1.0-py3-none-any.whl`; verified `uv run wegrep --help` and `uv run python -m wegrep --help` both show `usage: wegrep`; ran isolated config/index checks confirming `.wegrep/provider.json`, `~/.config/wegrep/provider.json`, `.wegrep/manifest.json`, `.wegrep/docstore.jsonl`, `.wegrep/chroma/`, `.wegrep/bm25/`, and `wegrep_` collection naming; ran the required raw old-name scan and a stricter standalone old-name scan, with no unintended legacy `egrep`, `Egrep`, or `EGREP` references found.
