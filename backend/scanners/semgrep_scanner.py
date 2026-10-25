"""Semgrep scanner adapter for AI Code Guardian (Step 4, v0.14).

Design:
- Optional dependency: semgrep installed in SEPARATE venv (venv-semgrep/).
  Main venv untouched. If missing, graceful skip (ok=True, no issues).
- Sandbox copy: only *.py copied to temp dir, so repo's .semgrepignore /
  .gitignore cannot change scan scope (Fixed Rule 2).
- Fixed rules only: --config points to backend/scanners/semgrep_rules/.
  Never --config auto, p/python, or registry URLs.
- No telemetry/network: --metrics=off, --disable-version-check, env vars set.
- Rule 3 safe: only rule_id, file, line, column, message, severity.
  extra.fix / extra.metavars / extra.lines are dropped.
- Always full (not in _INCREMENTAL_SCANNERS, same as lizard).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List


class SemgrepError(Exception):
    pass


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SEMGREP_EXE = _PROJECT_ROOT / "venv-semgrep" / "Scripts" / "semgrep.exe"
_RULES_DIR = Path(__file__).resolve().parent / "semgrep_rules"

_SEVERITY_MAP = {
    "ERROR": "HIGH",
    "WARNING": "MEDIUM",
    "INFO": "LOW",
}
_EMPTY_SEVERITY = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "UNDEFINED": 0}

_TIMEOUT_SECONDS = 60
_MAX_TARGET_BYTES = 1000000
_JOBS = 2

# Semgrep exit: 0 = clean, 1 = findings, other = error
_OK_EXIT_CODES = {0, 1}

# Rule id namespace used in our YAML rules
_RULE_NAMESPACE = "ai-code-guardian."


def _validate_target(target_dir) -> Path:
    p = Path(target_dir)
    if not p.exists():
        raise SemgrepError(f"target does not exist: {target_dir}")
    if not p.is_dir():
        raise SemgrepError(f"target is not a directory: {target_dir}")
    return p.resolve()


def _severity_counts(issues: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = dict(_EMPTY_SEVERITY)
    for i in issues:
        sev = (i.get("severity") or "UNDEFINED").upper()
        if sev in counts:
            counts[sev] += 1
        else:
            counts["UNDEFINED"] += 1
    return counts


def _empty_result(target: Path, scan_errors: List[str], ok: bool = True) -> Dict[str, Any]:
    return {
        "ok": ok,
        "scanner": "semgrep",
        "target": str(target),
        "total_issues": 0,
        "by_severity": dict(_EMPTY_SEVERITY),
        "issues": [],
        "scan_errors": scan_errors,
    }


def _copy_py_files_to_sandbox(target: Path) -> Path:
    """Copy only *.py files to temp dir. Defeats .semgrepignore/.gitignore."""
    sandbox = Path(tempfile.mkdtemp(prefix="guardian_semgrep_"))
    for path in target.rglob("*.py"):
        if not path.is_file():
            continue
        rel = path.relative_to(target)
        dest = sandbox / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(path, dest)
        except OSError:
            continue
    return sandbox


def _run_semgrep(sandbox: Path, output_file: Path):
    """Run semgrep. Returns (returncode, stderr)."""
    env = os.environ.copy()
    env["SEMGREP_SEND_METRICS"] = "off"
    env["SEMGREP_ENABLE_VERSION_CHECK"] = "0"
    env.pop("SEMGREP_APP_TOKEN", None)

    empty_settings = sandbox / ".semgrep_empty_settings.yml"
    empty_settings.write_text("", encoding="utf-8")
    env["SEMGREP_SETTINGS_FILE"] = str(empty_settings)

    cmd = [
        str(_SEMGREP_EXE),
        "scan",
        "--config", str(_RULES_DIR),
        "--json",
        "--output", str(output_file),
        "--metrics", "off",
        "--disable-version-check",
        "--no-git-ignore",
        "--quiet",
        "--timeout", "30",
        "--max-target-bytes", str(_MAX_TARGET_BYTES),
        "--jobs", str(_JOBS),
        str(sandbox),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return (-1, f"semgrep timed out after {_TIMEOUT_SECONDS}s")
    except OSError as exc:
        return (-1, f"semgrep launch failed: {type(exc).__name__}: {exc}")
    return (proc.returncode, (proc.stderr or "").strip())


def _normalize_rule_id(raw: str) -> str:
    """Strip Semgrep's config-path prefix from check_id.

    Semgrep returns e.g. 'backend.scanners.semgrep_rules.ai-code-guardian.eval-usage'
    because --config was a directory. We want 'ai-code-guardian.eval-usage'.
    """
    raw = (raw or "").strip()
    if not raw:
        return ""
    idx = raw.find(_RULE_NAMESPACE)
    if idx >= 0:
        return raw[idx:]
    return raw


def _parse_findings(data: Dict[str, Any], sandbox: Path) -> List[Dict[str, Any]]:
    """Convert semgrep JSON to our schema. Rule 3: drop fix/metavars/lines."""
    issues: List[Dict[str, Any]] = []
    for r in (data.get("results") or []):
        try:
            path_str = str(r.get("path", "") or "")
            try:
                rel_path = str(Path(path_str).relative_to(sandbox))
            except ValueError:
                rel_path = path_str.replace(str(sandbox), "").lstrip("\\/")
            start = r.get("start", {}) or {}
            line = int(start.get("line", 0) or 0)
            col = int(start.get("col", 0) or 0)
            extra = r.get("extra", {}) or {}
            sev = _SEVERITY_MAP.get(str(extra.get("severity", "INFO") or "INFO").upper(), "UNDEFINED")
            message = str(extra.get("message", "") or "").strip()
            rule_id = _normalize_rule_id(str(r.get("check_id", "") or ""))
            if not rule_id:
                continue
            rule_name = rule_id.split(".")[-1] if "." in rule_id else rule_id
            issues.append({
                "scanner": "semgrep",
                "rule_id": rule_id,
                "rule_name": rule_name,
                "message": message,
                "file": rel_path.replace("\\", "/"),
                "line": line,
                "column": col,
                "severity": sev,
            })
        except (ValueError, TypeError, AttributeError):
            continue
    return issues


def scan_with_semgrep(target_dir) -> Dict[str, Any]:
    """Run Semgrep on target_dir. Returns pylint-shaped dict.

    Missing semgrep = graceful skip (ok=True, no issues).
    """
    target = _validate_target(target_dir)

    if not _SEMGREP_EXE.exists():
        return _empty_result(target, ["semgrep not installed (venv-semgrep missing)"], ok=True)

    if not _RULES_DIR.is_dir():
        return _empty_result(target, ["semgrep rules directory missing"], ok=False)

    sandbox = None
    output_file = None
    scan_errors: List[str] = []
    try:
        sandbox = _copy_py_files_to_sandbox(target)
        if not any(sandbox.rglob("*.py")):
            return _empty_result(target, [], ok=True)

        fd, out_name = tempfile.mkstemp(prefix="guardian_semgrep_out_", suffix=".json")
        os.close(fd)
        output_file = Path(out_name)

        rc, stderr = _run_semgrep(sandbox, output_file)

        if rc not in _OK_EXIT_CODES:
            scan_errors.append(f"semgrep exit code {rc}: {stderr[:200]}")
            return _empty_result(target, scan_errors, ok=False)

        if not output_file.exists() or output_file.stat().st_size == 0:
            return _empty_result(target, scan_errors, ok=True)

        try:
            data = json.loads(output_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            scan_errors.append(f"semgrep output parse failed: {type(exc).__name__}")
            return _empty_result(target, scan_errors, ok=False)

        issues = _parse_findings(data, sandbox)
        return {
            "ok": True,
            "scanner": "semgrep",
            "target": str(target),
            "total_issues": len(issues),
            "by_severity": _severity_counts(issues),
            "issues": issues,
            "scan_errors": scan_errors,
        }
    except Exception as exc:
        scan_errors.append(f"semgrep unexpected error: {type(exc).__name__}: {exc}")
        return _empty_result(target, scan_errors, ok=False)
    finally:
        if sandbox is not None and sandbox.exists():
            try:
                shutil.rmtree(sandbox, ignore_errors=True)
            except OSError:
                pass
        if output_file is not None and output_file.exists():
            try:
                output_file.unlink()
            except OSError:
                pass