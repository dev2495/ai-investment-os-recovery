#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path


RUNTIME_ROOT = Path(__file__).absolute().parents[1]
SCAN_ROOTS = [RUNTIME_ROOT / "scripts", RUNTIME_ROOT / "api", RUNTIME_ROOT / "mcp_server"]


def assigned_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
    return names


def main() -> int:
    checked: list[str] = []
    violations: list[dict[str, str]] = []
    for root in SCAN_ROOTS:
        for path in sorted(root.glob("*.py")):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            if "VAULT_ROOT" not in assigned_names(tree):
                continue
            checked.append(str(path.relative_to(RUNTIME_ROOT)))
            for key in ("AI_OS_RUNTIME_ROOT", "AI_OS_VAULT_ROOT"):
                if key not in source:
                    violations.append({"path": str(path.relative_to(RUNTIME_ROOT)), "missing": key})
    result = {
        "status": "passed" if not violations else "failed",
        "checked_count": len(checked),
        "checked": checked,
        "violations": violations,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
