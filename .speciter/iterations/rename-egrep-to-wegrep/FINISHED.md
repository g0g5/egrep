# Iteration Complete

Iteration `rename-egrep-to-wegrep` is complete.

## Implemented

- Renamed the runtime package, module entrypoint, console script, project metadata, and lockfile package identity from `egrep` to `wegrep`.
- Updated workspace/global state paths, generated metadata, Chroma collection prefixes, error class naming, CLI help, prompts, README examples, AGENTS guidance, and packaged skill content to use `wegrep`.
- Updated tests, imports, monkeypatch paths, fixtures, and expectations for the renamed command, package, paths, and skill install location.
- Removed old `egrep` package files without adding aliases, migrations, fallback path lookup, or old command support.

## Verification

- `uv lock` regenerated the lockfile for `wegrep` metadata.
- `uv run pytest` passed with 80 tests during implementation.
- `uv build` produced `dist/wegrep-0.1.0.tar.gz` and `dist/wegrep-0.1.0-py3-none-any.whl`.
- `uv run wegrep --help` and `uv run python -m wegrep --help` both showed `usage: wegrep`.
- Targeted config/index checks confirmed `.wegrep/`, `~/.config/wegrep/provider.json`, and `wegrep_` collection naming.
