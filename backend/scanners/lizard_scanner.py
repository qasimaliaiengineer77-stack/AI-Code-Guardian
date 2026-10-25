"""Lizard complexity scanner wrapper for AI Code Guardian.

Rule 1: Scanned code is never executed - Lizard parses only.
Rule 2: No external config file used - thresholds are Python constants.
Rule 3: Only numeric metrics + function names are kept - no source lines.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

try:
    import lizard
except ImportError:  # pragma: no cover
    lizard = None

from backend.core.config import WORKSPACE_DIR


class LizardError(Exception):
    """Raised when Lizard scanning cannot proceed."""


# Step 3 decisions (locked):
#   CCN <= 10 : not a finding
#   CCN 11-15 : MEDIUM
#   CCN > 15  : HIGH
_CCN_MEDIUM_THRESHOLD = 10
_CCN_HIGH_THRESHOLD = 15

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
        raise LizardError(f"Invalid target path: {exc}") from exc

    workspace_r = Path(WORKSPACE_DIR).resolve()

    try:
        target_r.relative_to(workspace_r)
    except ValueError as exc:
        raise LizardError(
            f"Target '{target_r}' is outside workspace '{workspace_r}'"
        ) from exc

    if not target_r.is_dir():
        raise LizardError(f"Target is not a directory: {target_r}")

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
        "scanner": "lizard",
        "target": str(target),
        "total_issues": 0,
        "by_severity": dict(_EMPTY_SEVERITY),
        "issues": [],
        "scan_errors": errors,
    }


def _severity_for_ccn(ccn: int) -> str:
    """Map CCN to severity: >15 HIGH, 11-15 MEDIUM, <=10 skip (empty string)."""
    if ccn > _CCN_HIGH_THRESHOLD:
        return "HIGH"
    if ccn > _CCN_MEDIUM_THRESHOLD:
        return "MEDIUM"
    return ""


def scan_with_lizard(target_dir) -> Dict[str, Any]:
    """Run Lizard complexity analysis on target_dir. Returns pylint-shaped dict."""
    target = _validate_target(target_dir)

    if lizard is None:
        return _empty_result(target, ["lizard module not installed"], ok=False)

    scan_errors: List[str] = []
    issues: List[Dict[str, Any]] = []

    try:
        for path in target.rglob("*.py"):
            if not path.is_file():
                continue
            try:
                info = lizard.analyze_file(str(path))
            except Exception as exc:
                scan_errors.append(
                    f"lizard failed to parse {_rel(target, str(path))}: "
                    f"{type(exc).__name__}"
                )
                continue

            for func in (info.function_list or []):
                try:
                    ccn = int(getattr(func, "cyclomatic_complexity", 0) or 0)
                except (TypeError, ValueError):
                    ccn = 0

                sev = _severity_for_ccn(ccn)
                if not sev:
                    continue

                nloc = int(getattr(func, "nloc", 0) or 0)
                tokens = int(getattr(func, "token_count", 0) or 0)
                params = int(getattr(func, "parameter_count", 0) or 0)
                start = int(getattr(func, "start_line", 0) or 0)
                fname = getattr(func, "name", "") or ""
                long_name = getattr(func, "long_name", "") or fname

                # Rule 3 safe: function name + numeric metrics only, no source.
                message = (
                    f"{long_name or fname} has cyclomatic complexity {ccn} "
                    f"(NLOC={nloc}, params={params}, tokens={tokens})"
                )

                issues.append({
                    "scanner": "lizard",
                    "rule_id": "CCN",
                    "rule_name": "cyclomatic-complexity",
                    "severity": sev,
                    "message": message,
                    "file": _rel(target, str(path)),
                    "line": start,
                    "column": 0,
                    "function": fname,
                    "ccn": ccn,
                    "nloc": nloc,
                    "params": params,
                    "tokens": tokens,
                })
    except Exception as exc:
        return _empty_result(
            target,
            scan_errors + [f"lizard scan failed: {type(exc).__name__}"],
            ok=False,
        )

    return {
        "ok": not scan_errors,
        "scanner": "lizard",
        "target": str(target),
        "total_issues": len(issues),
        "by_severity": _severity_counts(issues),
        "issues": issues,
        "scan_errors": scan_errors,
    }