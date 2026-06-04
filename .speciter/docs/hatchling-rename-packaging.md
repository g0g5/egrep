# Hatchling Rename Packaging

Current: Hatchling 1.30.1, released 2026-06-02.

## Build Backend

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

## Distribution Name vs Import Package

```toml
[project]
name = "new-distribution-name"
version = "0.1.0"

[tool.hatch.build.targets.wheel]
packages = ["src/old_import_name"]
```

Installs as `new-distribution-name`; imports as `old_import_name`.

## Rename Import Package

```text
src/new_import_name/__init__.py
```

```toml
[project]
name = "new-distribution-name"
version = "0.1.0"

[tool.hatch.build.targets.wheel]
packages = ["src/new_import_name"]
```

## Src Layout Package Discovery

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/my_package"]
```

Equivalent:

```toml
[tool.hatch.build.targets.wheel]
only-include = ["src/my_package"]
sources = ["src"]
```

## Multiple Packages

```toml
[tool.hatch.build.targets.wheel]
packages = [
  "src/my_package",
  "src/my_other_package",
]
```

## Explicit Wheel Contents

```toml
[tool.hatch.build.targets.wheel]
only-include = [
  "src/my_package",
  "py.typed",
]
sources = ["src"]
```

## Exclude Non-Packages

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/my_package"]
only-packages = true
```

## Rewrite Paths

```toml
[tool.hatch.build.targets.wheel.sources]
"src/old_import_name" = "new_import_name"
```

Ships `src/old_import_name/mod.py` as `new_import_name/mod.py`.

## Include Generated Or External Files

```toml
[tool.hatch.build.targets.wheel.force-include]
"../artifacts/lib.so" = "my_package/lib.so"
"generated" = "my_package/generated"
```

## Sdist Contents

```toml
[tool.hatch.build.targets.sdist]
include = [
  "/src",
  "/tests",
  "/README.md",
  "/pyproject.toml",
]
exclude = [
  "*.tmp",
]
```

## Console Script

```toml
[project.scripts]
my-command = "my_package.cli:main"
```

Equivalent runtime wrapper:

```python
import sys
from my_package.cli import main

sys.exit(main())
```

## GUI Script

```toml
[project.gui-scripts]
my-gui = "my_package.gui:main"
```

## Plugin Entry Points

```toml
[project.entry-points."my.plugins"]
plugin-a = "my_package.plugins:a"
plugin-b = "my_package.plugins:b"
```

Do not use `[project.entry-points.console_scripts]`; use `[project.scripts]`.

## Minimal Rename Example

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "new-cli-name"
version = "0.1.0"
requires-python = ">=3.10"

[project.scripts]
new-cli = "old_pkg.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/old_pkg"]
```

## Sources

- https://pypi.org/project/hatchling/
- https://hatch.pypa.io/latest/config/build/
- https://hatch.pypa.io/latest/config/metadata/
- https://packaging.python.org/specifications/declaring-project-metadata/
