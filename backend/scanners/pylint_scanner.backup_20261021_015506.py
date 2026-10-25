"""Pylint scanner wrapper for AI Code Guardian.

Rule 1: Scanned code is never executed - pylint is static analysis only.
Rule 2: Our fixed pylintrc is passed via --rcfile, so repo configs are
        never auto-discovered. Neither CWD nor target-dir configs load.
Rule 3: Message text only is kept - no code snippets, no source lines.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from backend.core.config import WORKSPACE_DIR


class PylintError(Exception):
    """Raised when pylint scanning cannot proceed."""


_FIXED_RCFILE: Path = Path(__file__).resolve().parent / "pylintrc"

_TYPE_TO_SEVERITY: Dict[str, str] = {
    "convention": "LOW",
    "refactor": "LOW",
    "info": "LOW",
    "warning": "MEDIUM",
    "error": "HIGH",
    "fatal": "HIGH",
}

_EMPTY_SEVERITY: Dict[str, int] = {
    "LOW": 0,
    "MEDIUM": 0,
    "HIGH": 0,
    "UNDEFINED": 0,
}

_FATAL_BIT = 1
_USAGE_BIT = 32


def _validate_target(target_dir) -> Path:
    """Ensure the target is a real directory inside WORKSPACE_DIR."""
    target = Path(target_dir)
    try:
        target_r = target.resolve()
    except Exception as exc:
        raise PylintError(f"Invalid target path: {exc}") from exc

    workspace_r = Path(WORKSPACE_DIR).resolve()

    try:
        target_r.relative_to(workspace_r)
    except ValueError as exc:
        raise PylintError(
            f"Target '{target_r}' is outside workspace '{workspace_r}'"
        ) from exc

    if not target_r.is_dir():
        raise PylintError(f"Target is not a directory: {target_r}")

    return target_r


def _rel(target: Path, file_path: str) -> str:
    """Return path relative to target, or original path on failure."""
    if not file_path:
        return ""
    try:
        return str(Path(file_path).resolve().relative_to(target))
    except Exception:
        return file_path


def _severity_counts(issues: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = dict(_EMPTY_SEVERITY)
    for issue in issues:
        sev = issue.get("severity", "UNDEFINED")
        if sev not in counts:
            sev = "UNDEFINED"
        counts[sev] += 1
    return counts


def _empty_result(target: Path, errors: List[str], ok: bool = False) -> Dict[str, Any]:
    return {
        "ok": ok,
        "scanner": "pylint",
        "target": str(target),
        "total_issues": 0,
        "by_severity": dict(_EMPTY_SEVERITY),
        "issues": [],
        "scan_errors": errors,
    }


def scan_with_pylint(target_dir, timeout: int = 180) -> Dict[str, Any]:
    """Run pylint recursively on target_dir and return structured results."""
    target = _validate_target(target_dir)

    if not _FIXED_RCFILE.is_file():
        return _empty_result(
            target,
            [f"fixed pylintrc missing at {_FIXED_RCFILE}"],
            ok=False,
        )

    cmd = [
        sys.executable,
        "-m",
        "pylint",
        f"--rcfile={_FIXED_RCFILE}",
        "--output-format=json",
        "--reports=no",
        "--score=no",
        str(target),
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
    except subprocess.TimeoutExpired:
        return _empty_result(target, [f"pylint timed out after {timeout}s"], ok=False)
    except FileNotFoundError:
        return _empty_result(target, ["pylint module not installed"], ok=False)
    except Exception as exc:
        return _empty_result(target, [f"pylint subprocess failed: {exc}"], ok=False)

    scan_errors: List[str] = []
    if (proc.returncode & _FATAL_BIT) or (proc.returncode & _USAGE_BIT):
        stderr_tail = (proc.stderr or "").strip()[:500]
        scan_errors.append(
            f"pylint exited with code {proc.returncode}: {stderr_tail}"
        )

    raw = (proc.stdout or "").strip()
    if not raw:
        return _empty_result(
            target,
            scan_errors or ["pylint produced no output"],
            ok=not scan_errors,
        )

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _empty_result(
            target,
            scan_errors + [f"pylint output not JSON: {exc}"],
            ok=False,
        )

    if not isinstance(data, list):
        return _empty_result(
            target,
            scan_errors + ["pylint output was not a JSON array"],
            ok=False,
        )

    issues: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        msg_type = str(item.get("type", "")).lower()
        severity = _TYPE_TO_SEVERITY.get(msg_type, "UNDEFINED")
        issues.append({
            "scanner": "pylint",
            "rule_id": item.get("message-id", "") or "",
            "rule_name": item.get("symbol", "") or "",
            "severity": severity,
            "pylint_type": msg_type,
            "message": item.get("message", "") or "",
            "file": _rel(target, item.get("path", "")),
            "line": item.get("line", 0) or 0,
            "column": item.get("column", 0) or 0,
            "module": item.get("module", "") or "",
            "obj": item.get("obj", "") or "",
        })

    return {
        "ok": not scan_errors,
        "scanner": "pylint",
        "target": str(target),
        "total_issues": len(issues),
        "by_severity": _severity_counts(issues),
        "issues": issues,
        "scan_errors": scan_errors,
    }