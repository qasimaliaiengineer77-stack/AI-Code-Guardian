"""Bandit scanner wrapper for AI Code Guardian.

Rule 1: Scanned code is never executed — bandit is static analysis only.
Rule 2: Repo configs (.bandit, setup.cfg, pyproject.toml, tox.ini) are
        temporarily hidden during scan, so bandit runs with fixed defaults.
Rule 3: The 'code' field is dropped; it never reaches the AI or the UI.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.core.config import WORKSPACE_DIR


class BanditError(Exception):
    """Raised when bandit scanning cannot proceed."""


_REPO_CONFIG_FILES: Tuple[str, ...] = (
    ".bandit",
    ".bandit.yaml",
    ".bandit.yml",
    "setup.cfg",
    "tox.ini",
    "pyproject.toml",
)

_HIDDEN_SUFFIX = ".guardian_hidden"

_EMPTY_SEVERITY: Dict[str, int] = {
    "LOW": 0,
    "MEDIUM": 0,
    "HIGH": 0,
    "UNDEFINED": 0,
}


def _validate_target(target_dir) -> Path:
    """Ensure the target is a real directory inside WORKSPACE_DIR."""
    target = Path(target_dir)
    try:
        target_r = target.resolve()
    except Exception as exc:
        raise BanditError(f"Invalid target path: {exc}") from exc

    workspace_r = Path(WORKSPACE_DIR).resolve()

    try:
        target_r.relative_to(workspace_r)
    except ValueError as exc:
        raise BanditError(
            f"Target '{target_r}' is outside workspace '{workspace_r}'"
        ) from exc

    if not target_r.is_dir():
        raise BanditError(f"Target is not a directory: {target_r}")

    return target_r


def _hide_repo_configs(root: Path) -> List[Tuple[Path, Path]]:
    """Rename repo config files so bandit uses fixed defaults only (Rule 2)."""
    hidden: List[Tuple[Path, Path]] = []
    for name in _REPO_CONFIG_FILES:
        path = root / name
        if not path.is_file():
            continue
        hidden_path = path.with_name(name + _HIDDEN_SUFFIX)
        try:
            path.rename(hidden_path)
            hidden.append((hidden_path, path))
        except OSError:
            # If we cannot hide it, skip — bandit defaults still hold for
            # configs it does not auto-discover from here.
            continue
    return hidden


def _restore_repo_configs(hidden: List[Tuple[Path, Path]]) -> None:
    """Undo _hide_repo_configs — best effort."""
    for hidden_path, original_path in hidden:
        try:
            if hidden_path.exists() and not original_path.exists():
                hidden_path.rename(original_path)
        except OSError:
            continue


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
        sev = str(issue.get("severity", "UNDEFINED")).upper()
        if sev not in counts:
            sev = "UNDEFINED"
        counts[sev] += 1
    return counts


def _empty_result(target: Path, errors: List[str], ok: bool = False) -> Dict[str, Any]:
    return {
        "ok": ok,
        "scanner": "bandit",
        "target": str(target),
        "total_issues": 0,
        "by_severity": dict(_EMPTY_SEVERITY),
        "issues": [],
        "scan_errors": errors,
    }


def scan_with_bandit(target_dir, timeout: int = 120) -> Dict[str, Any]:
    """Run bandit recursively on target_dir and return structured results."""
    target = _validate_target(target_dir)

    hidden = _hide_repo_configs(target)
    try:
        cmd = [
            sys.executable,
            "-m",
            "bandit",
            "-r",
            str(target),
            "-f",
            "json",
            "-q",
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
            return _empty_result(
                target, [f"bandit timed out after {timeout}s"], ok=False
            )
        except FileNotFoundError:
            return _empty_result(
                target, ["bandit module not installed"], ok=False
            )
        except Exception as exc:
            return _empty_result(
                target, [f"bandit subprocess failed: {exc}"], ok=False
            )

        # bandit exit codes: 0 = no issues, 1 = issues found, >1 = error.
        scan_errors: List[str] = []
        if proc.returncode not in (0, 1):
            stderr_tail = (proc.stderr or "").strip()[:500]
            scan_errors.append(
                f"bandit exited with code {proc.returncode}: {stderr_tail}"
            )

        raw = (proc.stdout or "").strip()
        if not raw:
            return _empty_result(
                target,
                scan_errors or ["bandit produced no output"],
                ok=(proc.returncode in (0, 1) and not scan_errors),
            )

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            return _empty_result(
                target, scan_errors + [f"bandit output not JSON: {exc}"], ok=False
            )

        issues: List[Dict[str, Any]] = []
        for item in (data.get("results") or []):
            cwe = item.get("issue_cwe")
            cwe_id = cwe.get("id") if isinstance(cwe, dict) else None
            issues.append({
                "scanner": "bandit",
                "rule_id": item.get("test_id", "") or "",
                "rule_name": item.get("test_name", "") or "",
                "severity": str(item.get("issue_severity", "UNDEFINED")).upper(),
                "confidence": str(item.get("issue_confidence", "UNDEFINED")).upper(),
                "message": item.get("issue_text", "") or "",
                # Rule 3: 'code' field is intentionally NOT surfaced.
                "file": _rel(target, item.get("filename", "")),
                "line": item.get("line_number", 0) or 0,
                "cwe_id": cwe_id,
                "more_info": item.get("more_info", "") or "",
            })

        return {
            "ok": proc.returncode in (0, 1) and not scan_errors,
            "scanner": "bandit",
            "target": str(target),
            "total_issues": len(issues),
            "by_severity": _severity_counts(issues),
            "issues": issues,
            "scan_errors": scan_errors,
        }
    finally:
        _restore_repo_configs(hidden)