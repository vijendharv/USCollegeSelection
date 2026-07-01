from __future__ import annotations

import ast
from pathlib import Path


def imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", maxsplit=1)[0])
    return roots


def test_infrastructure_dependencies_stay_in_their_layers() -> None:
    violations: list[str] = []
    for path in Path("app").rglob("*.py"):
        imports = imported_roots(path)
        if "httpx" in imports and Path("app/networking") not in path.parents:
            violations.append(f"{path}: httpx must stay in app/networking")
        if "duckdb" in imports and Path("app/storage") not in path.parents:
            violations.append(f"{path}: duckdb must stay in app/storage")

    assert violations == []
