# uv Rename Packaging Notes

Sources checked: official uv docs, current through Jun 2026.

## Rename Checklist

```toml
# pyproject.toml
[project]
name = "new-dist-name"          # distribution name on PyPI / uv.lock
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []

[project.scripts]
new-cli = "new_package.cli:main" # console command -> import path callable

[build-system]
requires = ["uv_build>=0.11.19,<0.12"]
build-backend = "uv_build"
```

```text
src/
  new_package/
    __init__.py
    cli.py
```

```python
# src/new_package/cli.py
def main() -> None:
    print("hello")
```

## If Distribution Name Differs From Import Package

```toml
[project]
name = "new-dist-name"

[tool.uv.build-backend]
module-name = "new_package"
```

## Hatchling Variant

```toml
[project]
name = "new-dist-name"

[project.scripts]
new-cli = "new_package.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

## Lock After Rename

```sh
uv lock
uv lock --check
```

Use `--locked` in CI to fail if `pyproject.toml` and `uv.lock` drift:

```sh
uv run --locked pytest
```

Use `--frozen` only when intentionally skipping lock freshness checks:

```sh
uv run --frozen pytest
```

## Editable Project Install

Default project sync/run installs the project editable when a build system exists:

```sh
uv sync
uv run new-cli
uv run python -c "import new_package; print(new_package.__name__)"
```

Deployment-style non-editable install:

```sh
uv sync --no-editable
uv run --no-editable new-cli
```

If the project should not be installed despite a build system:

```toml
[tool.uv]
package = false
```

If the project must be installed without a build system:

```toml
[tool.uv]
package = true
```

## Build After Rename

```sh
rm -rf dist
uv build
```

Expected artifacts use the normalized distribution name:

```text
dist/new_dist_name-0.1.0-py3-none-any.whl
dist/new_dist_name-0.1.0.tar.gz
```

Smoke test the wheel:

```sh
uv run --isolated --with ./dist/new_dist_name-0.1.0-py3-none-any.whl new-cli
uv run --isolated --with ./dist/new_dist_name-0.1.0-py3-none-any.whl python -c "import new_package"
```

## Rename Diff Pattern

```diff
 [project]
-name = "old-dist-name"
+name = "new-dist-name"

 [project.scripts]
-old-cli = "old_package.cli:main"
+new-cli = "new_package.cli:main"

 [tool.uv.build-backend]
-module-name = "old_package"
+module-name = "new_package"
```

```sh
mv src/old_package src/new_package
uv lock
uv sync
uv run new-cli
uv build
```

## Notes

- `uv.lock` is managed by uv; do not edit it manually.
- `uv run` and `uv sync` automatically lock and sync unless flags say otherwise.
- `[project.scripts]` requires a build system to create installed console commands.
- `uv_build` defaults to `src/<normalized_project_name>/__init__.py`; dashes and dots become underscores.
- Set `[tool.uv.build-backend].module-name` when the import module is not the normalized project name.

## References

- https://docs.astral.sh/uv/concepts/projects/layout/
- https://docs.astral.sh/uv/concepts/projects/config/
- https://docs.astral.sh/uv/concepts/projects/sync/
- https://docs.astral.sh/uv/concepts/build-backend/
- https://docs.astral.sh/uv/guides/projects/
