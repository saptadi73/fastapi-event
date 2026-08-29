"""Inventory user-facing literals and stable error codes in backend Python files."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path


EXCEPTION_NAMES = {"ValidationException", "NotFoundException", "ConflictException", "AppException"}


def _literal(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def scan_file(path: Path) -> list[dict]:
    findings = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
        if name == "success_response" and node.args:
            message = _literal(node.args[0])
            if message:
                findings.append({"kind": "success", "message": message, "code": None, "file": str(path), "line": node.lineno})
        if name in EXCEPTION_NAMES:
            keywords = {item.arg: _literal(item.value) for item in node.keywords if item.arg}
            code = keywords.get("code") or (_literal(node.args[0]) if node.args else None)
            message = keywords.get("message") or (_literal(node.args[1]) if len(node.args) > 1 else None)
            if code or message:
                findings.append({"kind": "error", "message": message, "code": code, "file": str(path), "line": node.lineno})
    return findings


def scan_tree(root: Path) -> list[dict]:
    findings = []
    for path in sorted(root.rglob("*.py")):
        findings.extend(scan_file(path))
    return findings


def summary(findings: list[dict]) -> dict:
    success_messages = sorted({row["message"] for row in findings if row["kind"] == "success" and row["message"]})
    error_codes = sorted({row["code"] for row in findings if row["kind"] == "error" and row["code"]})
    error_messages = sorted({row["message"] for row in findings if row["kind"] == "error" and row["message"]})
    return {
        "success_message_count": len(success_messages),
        "error_code_count": len(error_codes),
        "error_message_count": len(error_messages),
        "success_messages": success_messages,
        "error_codes": error_codes,
        "error_messages": error_messages,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("app"))
    parser.add_argument("--details", action="store_true")
    args = parser.parse_args()
    findings = scan_tree(args.root)
    print(json.dumps(findings if args.details else summary(findings), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
