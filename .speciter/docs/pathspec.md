# pathspec for egrep init discovery

Latest docs found: PathSpec 1.1.1. Use `GitIgnoreSpec` for closest Git `.gitignore` behavior, including edge cases around negation and excluded directories.

```bash
pip install pathspec
```

## Compile rules

```python
from pathlib import Path
from pathspec import GitIgnoreSpec

root = Path.cwd()
rules = root.joinpath(".gitignore").read_text().splitlines()
spec = GitIgnoreSpec.from_lines(rules)
```

## Ignore one relative path

```python
rel = "build/output.txt"
ignored = spec.match_file(rel)
```

## Keep files during custom workspace walk

```python
from pathlib import Path
from pathspec import GitIgnoreSpec

root = Path.cwd()
spec = GitIgnoreSpec.from_lines(root.joinpath(".gitignore").read_text().splitlines())

for path in root.rglob("*"):
    if not path.is_file():
        continue
    rel = path.relative_to(root).as_posix()
    if spec.match_file(rel):
        continue
    print(rel)
```

## Get ignored files from pathspec walker

```python
ignored = set(spec.match_tree_files(root))
```

## Get kept files from pathspec walker

```python
kept = set(spec.match_tree_files(root, negate=True))
```

## Combine built-in egrep init ignores with .gitignore

```python
from pathlib import Path
from pathspec import GitIgnoreSpec

root = Path.cwd()
lines = [
    ".git/",
    ".speciter/",
    "__pycache__/",
    "*.pyc",
]
gitignore = root / ".gitignore"
if gitignore.exists():
    lines.extend(gitignore.read_text().splitlines())

spec = GitIgnoreSpec.from_lines(lines)
files = [
    p.relative_to(root).as_posix()
    for p in root.rglob("*")
    if p.is_file() and not spec.match_file(p.relative_to(root).as_posix())
]
```

## Optional backend selection

```python
spec = GitIgnoreSpec.from_lines(lines, backend="simple")  # always available
spec = GitIgnoreSpec.from_lines(lines, backend="best")    # default; prefers re2, hyperscan, simple
```

## Notes

- `PathSpec.from_lines("gitignore", lines)` works, but `GitIgnoreSpec.from_lines(lines)` better replicates Git behavior.
- Match paths relative to the workspace root and normalize separators with `.as_posix()`.
- `match_file()` returns `True` when the path is ignored/matched by ignore rules.
- `match_tree_files(root, negate=True)` flips results to return files not ignored.

## Sources

- https://python-path-specification.readthedocs.io/en/latest/readme.html
- https://python-path-specification.readthedocs.io/en/latest/api.html
- https://pypi.org/project/pathspec/
