"""Radon scanner — fixed config, workspace-only, static analysis only.

Rule 1: scanned code never executed (radon parses AST only).
Rule 2: repo configs (radon.cfg / setup.cfg / tox.ini / pyproject.toml)
        are hidden during the scan and restored afterwards.
Rule 3: only summary fields are returned; radon emits no code snippets.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from backend.core.config import WORKSPACE_DIR

_REPO_CONFIG_FILES = ("radon.cfg", "setup.cfg", "tox.ini", "pyproject.toml")
_HIDDEN_SUFFIX = ".guardian_hidden"
_EMPTY_SEVERITY = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}


class RadonError(Exception):
    """Raised when radon scan cannot be performed safely."""


def _validate_target(target_dir) -> Path:
    target = Path(target_dir).resolve()
    workspace = WORKSPACE_DIR.resolve()
    try:
        target.relative_to(workspace)
    except ValueError:
        raise RadonError(
            f"Target '{target}' is outside workspace '{workspace}'"
        )
    if not target.exists() or not target.is_dir():
        raise RadonError(f"Target '{target}' is not a directory")
    return target


def _hide_repo_configs(root: Path):
    hidden = []
    for name in _REPO_CONFIG_FILES:
        for cfg in root.rglob(name):
            if not cfg.is_file():
                continue
            hidden_path = cfg.with_name(cfg.name + _HIDDEN_SUFFIX)
            try:
                cfg.rename(hidden_path)
                hidden.append((cfg, hidden_path))
            except OSError:
                pass
    return hidden


def _restore_repo_configs(hidden):
    for original, hidden_path in hidden:
        try:
            if hidden_path.exists() and not original.exists():
                hidden_path.rename(original)
        except OSError:
            pass


def _rel(path_str: str, root: Path) -> str:
    try:
        return str(Path(path_str).resolve().relative_to(root).as_posix())
    except (ValueError, OSError):
        return Path(path_str).name


def _rank_to_severity(rank: str):
    if rank == "A":
        return None
    if rank == "B":
        return "LOW"
    if rank == "C":
        return "MEDIUM"
    if rank in ("D", "E", "F"):
        return "HIGH"
    return None


def _severity_counts(issues):
    counts = dict(_EMPTY_SEVERITY)
    for issue in issues:
        sev = issue.get("severity")
        if sev in counts:
            counts[sev] += 1
    return counts


def _empty_result(target: Path, ok: bool = True, errors=None):
    return {
        "ok": ok,
        "scanner": "radon",
        "target": str(target),
        "total_issues": 0,
        "by_severity": dict(_EMPTY_SEVERITY),
        "issues": [],
        "scan_errors": list(errors or []),
    }


def _iter_blocks(value):
    """Yield block dicts from radon's per-file JSON value.

    radon has emitted different shapes across versions: a list of blocks,
    a single block dict, or a dict of nested blocks. Anything that is not
    a block dict is ignored here; str values are handled by the caller.
    """
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                yield item
    elif isinstance(value, dict):
        if "rank" in value or "type" in value:
            yield value
        else:
            for sub in value.values():
                if isinstance(sub, dict):
                    yield sub
                elif isinstance(sub, list):
                    for item in sub:
                        if isinstance(item, dict):
                            yield item


def scan_with_radon(target_dir, timeout: int = 120, files=None):
    target = _validate_target(target_dir)
    hidden = _hide_repo_configs(target)
    try:
        cmd = [
            sys.executable, "-m", "radon",
            "cc", "-j", "-n", "B",
            *([str(f) for f in files] if files else [str(target)]),
        ]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout, shell=False,
            )
        except subprocess.TimeoutExpired:
            return _empty_result(
                target, ok=False,
                errors=[f"radon timed out after {timeout}s"],
            )
        except OSError as exc:
            return _empty_result(
                target, ok=False,
                errors=[f"radon launch failed: {exc}"],
            )

        scan_errors = []
        if not proc.stdout.strip():
            if proc.returncode != 0:
                msg = proc.stderr.strip()[:500] or "(no stderr)"
                return _empty_result(
                    target, ok=False,
                    errors=[f"radon exit {proc.returncode}: {msg}"],
                )
            return _empty_result(target)

        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            return _empty_result(
                target, ok=False,
                errors=[f"radon JSON parse error: {exc}"],
            )

        if not isinstance(data, dict):
            return _empty_result(
                target, ok=False,
                errors=["unexpected radon JSON root (expected object)"],
            )

        if proc.returncode != 0 and proc.stderr.strip():
            scan_errors.append(proc.stderr.strip()[:500])

        issues = []
        for file_path, value in data.items():
            rel = _rel(file_path, target)
            if isinstance(value, str):
                scan_errors.append(f"{rel}: radon reported '{value[:200]}'")
                continue
            for block in _iter_blocks(value):
                rank = (block.get("rank") or "").upper()
                severity = _rank_to_severity(rank)
                if severity is None:
                    continue
                btype = block.get("type", "block")
                name = block.get("name", "")
                complexity = block.get("complexity")
                issues.append({
                    "scanner": "radon",
                    "rule_id": f"radon-{rank}",
                    "rule_name": f"{btype}-complexity-{rank}",
                    "severity": severity,
                    "rank": rank,
                    "complexity": complexity,
                    "type": btype,
                    "name": name,
                    "classname": block.get("classname"),
                    "file": rel,
                    "line": block.get("lineno"),
                    "endline": block.get("endline"),
                    "column": block.get("col_offset"),
                    "message": (
                        f"{btype} '{name}' has cyclomatic complexity "
                        f"{complexity} (rank {rank})"
                    ),
                })

        return {
            "ok": True,
            "scanner": "radon",
            "target": str(target),
            "total_issues": len(issues),
            "by_severity": _severity_counts(issues),
            "issues": issues,
            "scan_errors": scan_errors,
        }
    finally:
        _restore_repo_configs(hidden)