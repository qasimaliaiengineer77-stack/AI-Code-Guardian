"""Gitleaks scanner wrapper for AI Code Guardian.

Rule 1: Scanned code is never executed — gitleaks static scanning only.
Rule 2: Gitleaks is ALWAYS invoked with `--config backend/scanners/gitleaks.toml`
        (fixed config). Any repo-local `.gitleaks.toml` / `.gitleaksignore` is
        also renamed during scan (belt-and-braces). Repo config never wins.
Rule 3: The `Secret`, `Match`, and `Fingerprint` fields are DROPPED at parse
        time. They never reach the AI, DB, UI, or logs. The temp report file
        is deleted in the finally block. Gitleaks is also run with `--redact`
        so the report on disk already has secrets masked — double defense.
Rule 9: Binary is pinned to v8.30.1 (backend/scanners/bin/gitleaks.exe) —
        SHA256 verified against official checksums.txt during setup.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.core.config import WORKSPACE_DIR


class GitleaksError(Exception):
    """Raised when gitleaks scanning cannot proceed."""


_GITLEAKS_DIR: Path = Path(__file__).resolve().parent
_GITLEAKS_EXE: Path = _GITLEAKS_DIR / "bin" / "gitleaks.exe"
_GITLEAKS_CONFIG: Path = _GITLEAKS_DIR / "gitleaks.toml"

_REPO_CONFIG_FILES: Tuple[str, ...] = (
    ".gitleaks.toml",
    ".gitleaksignore",
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
        raise GitleaksError(f"Invalid target path: {exc}") from exc

    workspace_r = Path(WORKSPACE_DIR).resolve()

    try:
        target_r.relative_to(workspace_r)
    except ValueError as exc:
        raise GitleaksError(
            f"Target '{target_r}' is outside workspace '{workspace_r}'"
        ) from exc

    if not target_r.is_dir():
        raise GitleaksError(f"Target is not a directory: {target_r}")

    return target_r


def _hide_repo_configs(root: Path) -> List[Tuple[Path, Path]]:
    """Rename repo gitleaks configs so they cannot be auto-discovered (Rule 2)."""
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
        "scanner": "gitleaks",
        "target": str(target),
        "total_issues": 0,
        "by_severity": dict(_EMPTY_SEVERITY),
        "issues": [],
        "scan_errors": errors,
    }


def scan_with_gitleaks(target_dir, timeout: int = 120) -> Dict[str, Any]:
    """Run gitleaks on target_dir with fixed config; return structured results."""
    target = _validate_target(target_dir)

    if not _GITLEAKS_EXE.is_file():
        return _empty_result(
            target,
            ["gitleaks binary missing at backend/scanners/bin/gitleaks.exe"],
            ok=False,
        )
    if not _GITLEAKS_CONFIG.is_file():
        return _empty_result(
            target,
            ["gitleaks config missing at backend/scanners/gitleaks.toml"],
            ok=False,
        )

    hidden = _hide_repo_configs(target)
    tmp_report: str = ""
    try:
        fd, tmp_report = tempfile.mkstemp(prefix="guardian_gl_", suffix=".json")
        os.close(fd)

        cmd = [
            str(_GITLEAKS_EXE),
            "detect",
            "--no-git",
            "--source", str(target),
            "--config", str(_GITLEAKS_CONFIG),
            "--report-format", "json",
            "--report-path", tmp_report,
            "--redact",
            "--no-banner",
            "--log-level", "error",
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
                target, [f"gitleaks timed out after {timeout}s"], ok=False
            )
        except FileNotFoundError:
            return _empty_result(
                target, ["gitleaks binary not executable"], ok=False
            )
        except Exception as exc:
            return _empty_result(
                target, [f"gitleaks subprocess failed: {exc}"], ok=False
            )

        # Gitleaks exit codes: 0 = no leaks, 1 = leaks found, >1 = error.
        scan_errors: List[str] = []
        if proc.returncode not in (0, 1):
            stderr_tail = (proc.stderr or "").strip()[:500]
            scan_errors.append(
                f"gitleaks exited with code {proc.returncode}: {stderr_tail}"
            )

        raw = ""
        try:
            with open(tmp_report, "r", encoding="utf-8") as f:
                raw = f.read().strip()
        except FileNotFoundError:
            return _empty_result(
                target,
                scan_errors or ["gitleaks produced no report file"],
                ok=(proc.returncode in (0, 1) and not scan_errors),
            )
        except Exception as exc:
            return _empty_result(
                target,
                scan_errors + [f"cannot read gitleaks report: {exc}"],
                ok=False,
            )

        issues: List[Dict[str, Any]] = []
        if raw:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                return _empty_result(
                    target,
                    scan_errors + [f"gitleaks report not JSON: {exc}"],
                    ok=False,
                )

            if isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    # Rule 3: DROP Secret, Match, Fingerprint.
                    # They are NOT stored, NOT logged, NOT passed to AI/UI.
                    rule_id = str(item.get("RuleID", "") or "")
                    description = str(item.get("Description", "") or "")
                    file_path = _rel(target, str(item.get("File", "") or ""))
                    try:
                        line = int(item.get("StartLine", 0) or 0)
                    except (TypeError, ValueError):
                        line = 0
                    rule_label = description or rule_id or "secret"
                    issues.append({
                        "scanner": "gitleaks",
                        "rule_id": rule_id,
                        "rule_name": rule_label,
                        "severity": "HIGH",
                        "confidence": "HIGH",
                        "message": f"Potential hardcoded secret detected ({rule_label})",
                        "file": file_path,
                        "line": line,
                        "cwe_id": 798,  # CWE-798: Use of Hard-coded Credentials
                        "more_info": "",
                    })

        return {
            "ok": proc.returncode in (0, 1) and not scan_errors,
            "scanner": "gitleaks",
            "target": str(target),
            "total_issues": len(issues),
            "by_severity": _severity_counts(issues),
            "issues": issues,
            "scan_errors": scan_errors,
        }
    finally:
        _restore_repo_configs(hidden)
        if tmp_report:
            try:
                os.remove(tmp_report)
            except OSError:
                pass