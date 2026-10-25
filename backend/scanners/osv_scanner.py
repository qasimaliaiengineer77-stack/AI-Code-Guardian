"""OSV-Scanner wrapper for AI Code Guardian.

Rule 1: static-only — requirements.txt/lockfiles parse hote hain, code run nahi.
Rule 2: hamesha --config backend\\scanners\\osv-scanner.toml; repo ka osv-scanner.toml hidden.
Rule 3: network par sirf package naam + version jate hain (OSV API); code, file paths, secrets nahi.
Rule 8: koi paid API nahi — OSV public free API.
Rule 9: binary v2.7.0 pinned + SHA256 verified (9964ed64...6438).
Offline: network fail -> graceful skip, crash nahi.
BOM: OSV v2.7.0 BOM-prefixed manifest ko invalid samajhta hai — call se pehle BOM strip, finally restore.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


class OSVError(RuntimeError):
    """Unrecoverable OSV-Scanner error."""


_SCANNERS_DIR = Path(__file__).resolve().parent
_OSV_DIR = _SCANNERS_DIR / "bin"
_OSV_EXE = _OSV_DIR / "osv-scanner.exe"
_OSV_CONFIG = _SCANNERS_DIR / "osv-scanner.toml"

_REPO_CONFIG_FILES = ("osv-scanner.toml",)
_HIDDEN_SUFFIX = ".guardian_hidden"

_NETWORK_ERROR_HINTS = (
    "dial tcp",
    "no such host",
    "connection refused",
    "network is unreachable",
    "i/o timeout",
    "tls handshake",
    "context deadline exceeded",
    "getaddrinfo",
    "proxyconnect",
    "connection reset by peer",
    "server misbehaving",
    "failed to query osv",
    "osv.dev",
)

_EMPTY_SEVERITY = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}

_BOM = b"\xef\xbb\xbf"
_MANIFEST_NAMES = (
    "requirements.txt",
    "requirements-dev.txt",
    "requirements.in",
    "requirements-dev.in",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "Pipfile",
    "Pipfile.lock",
    "poetry.lock",
    "uv.lock",
)


def _validate_target(target: Any) -> Path:
    if target is None:
        raise OSVError("target_dir required")
    p = Path(target).resolve()
    if not p.exists() or not p.is_dir():
        raise OSVError(f"target_dir does not exist: {p}")
    workspace_root = (_SCANNERS_DIR.parents[1] / "data" / "workspace").resolve()
    try:
        p.relative_to(workspace_root)
    except ValueError:
        raise OSVError(f"target_dir outside workspace: {p}")
    return p


def _hide_repo_configs(target_dir: Path) -> list[tuple[Path, Path]]:
    hidden: list[tuple[Path, Path]] = []
    for name in _REPO_CONFIG_FILES:
        candidates = [target_dir / name]
        try:
            candidates.extend(target_dir.rglob(name))
        except OSError:
            pass
        for candidate in candidates:
            if not candidate.is_file():
                continue
            hidden_path = candidate.with_name(candidate.name + _HIDDEN_SUFFIX)
            try:
                shutil.move(str(candidate), str(hidden_path))
                hidden.append((candidate, hidden_path))
            except OSError:
                pass
    return hidden


def _restore_repo_configs(hidden: list[tuple[Path, Path]]) -> None:
    for original, hidden_path in hidden:
        try:
            if hidden_path.exists() and not original.exists():
                shutil.move(str(hidden_path), str(original))
        except OSError:
            pass


def _manifest_candidates(target_dir: Path) -> list[Path]:
    found: list[Path] = []
    for name in _MANIFEST_NAMES:
        try:
            found.extend(p for p in target_dir.rglob(name) if p.is_file())
        except OSError:
            pass
    try:
        found.extend(p for p in target_dir.rglob("requirements*.txt") if p.is_file())
    except OSError:
        pass
    seen: set[Path] = set()
    unique: list[Path] = []
    for p in found:
        try:
            resolved = p.resolve()
        except OSError:
            continue
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def _strip_manifest_boms(target_dir: Path) -> list[tuple[Path, bytes]]:
    """Manifest files se UTF-8 BOM (EF BB BF) strip karta hai.

    Sirf BOM remove hota hai; baqi bytes bilkul wahi rehte hain.
    Return: (path, original_bytes) pairs — finally mein restore ke liye.
    """
    stripped: list[tuple[Path, bytes]] = []
    for path in _manifest_candidates(target_dir):
        try:
            original = path.read_bytes()
        except OSError:
            continue
        if not original.startswith(_BOM):
            continue
        try:
            path.write_bytes(original[len(_BOM):])
        except OSError:
            continue
        stripped.append((path, original))
    return stripped


def _restore_manifest_boms(stripped: list[tuple[Path, bytes]]) -> None:
    for path, original in stripped:
        try:
            path.write_bytes(original)
        except OSError:
            pass


def _rel(path_str: str, target_dir: Path) -> str:
    try:
        p = Path(path_str)
        if p.is_absolute():
            return str(p.relative_to(target_dir))
        return path_str
    except (ValueError, OSError):
        return path_str


def _severity_counts(issues: list[dict]) -> dict:
    counts = dict(_EMPTY_SEVERITY)
    for issue in issues:
        sev = str(issue.get("severity", "MEDIUM")).upper()
        if sev not in counts:
            sev = "MEDIUM"
        counts[sev] += 1
    return counts


def _empty_result(reason: str | None = None, network_unavailable: bool = False) -> dict:
    result: dict = {
        "scanner": "osv",
        "ok": True,
        "issues": [],
        "by_severity": dict(_EMPTY_SEVERITY),
        "total": 0,
    }
    if reason:
        result["skipped_reason"] = reason
    if network_unavailable:
        result["network_unavailable"] = True
    return result


def _is_network_error(returncode: int, stderr: str) -> bool:
    if returncode in (0, 1):
        return False
    lower = (stderr or "").lower()
    return any(hint in lower for hint in _NETWORK_ERROR_HINTS)


def _normalize_severity(raw: Any) -> str:
    if not raw:
        return "MEDIUM"
    s = str(raw).upper()
    if s in ("CRITICAL", "HIGH"):
        return "HIGH"
    if s in ("MODERATE", "MEDIUM"):
        return "MEDIUM"
    if s in ("LOW", "NEGLIGIBLE", "UNKNOWN"):
        return "LOW"
    return "MEDIUM"


def _extract_severity(vuln: dict) -> str:
    db = vuln.get("database_specific") or {}
    if isinstance(db, dict) and db.get("severity"):
        return _normalize_severity(db["severity"])
    return "MEDIUM"


def _extract_cwe(vuln: dict) -> int | None:
    db = vuln.get("database_specific") or {}
    if not isinstance(db, dict):
        return None
    cwe_list = db.get("cwe_ids")
    if isinstance(cwe_list, list) and cwe_list:
        first = cwe_list[0]
        if isinstance(first, str) and first.upper().startswith("CWE-"):
            try:
                return int(first.split("-", 1)[1])
            except (ValueError, IndexError):
                return None
    return None


def _transform(data: dict, target_dir: Path) -> list[dict]:
    issues: list[dict] = []
    target_resolved = target_dir.resolve()
    for result in data.get("results") or []:
        source = result.get("source") or {}
        raw_path = str(source.get("path") or "")

        # Workspace boundary: drop any finding whose source path resolves
        # outside target_dir. Defense-in-depth (Rule 1 + workspace rule).
        if raw_path:
            candidate = Path(raw_path)
            if not candidate.is_absolute():
                candidate = target_resolved / candidate
            try:
                resolved = candidate.resolve()
                resolved.relative_to(target_resolved)
            except (ValueError, OSError):
                continue
            file_path = _rel(str(resolved), target_resolved)
        else:
            file_path = ""

        for pkg_wrap in result.get("packages") or []:
            pkg = pkg_wrap.get("package") or {}
            name = pkg.get("name") or "unknown"
            version = pkg.get("version") or ""
            for vuln in pkg_wrap.get("vulnerabilities") or []:
                vid = vuln.get("id") or "OSV-UNKNOWN"
                summary = (vuln.get("summary") or "").strip() or (
                    f"Known vulnerability in {name} {version}"
                )
                issues.append(
                    {
                        "rule_id": vid,
                        "message": summary,
                        "file": file_path,
                        "line": 0,
                        "severity": _extract_severity(vuln),
                        "scanner": "osv",
                        "package": f"{name}@{version}",
                        "cwe_id": _extract_cwe(vuln),
                    }
                )
    return issues


def scan_with_osv(target_dir: Any, timeout: int = 180) -> dict:
    """Run OSV-Scanner on target_dir (Python lockfiles / requirements.txt only)."""
    if not _OSV_EXE.is_file():
        raise OSVError(f"osv-scanner binary missing: {_OSV_EXE}")
    if not _OSV_CONFIG.is_file():
        raise OSVError(f"osv-scanner config missing: {_OSV_CONFIG}")

    target = _validate_target(target_dir)
    hidden = _hide_repo_configs(target)
    stripped = _strip_manifest_boms(target)

    fd, tmp_name = tempfile.mkstemp(prefix="guardian_osv_", suffix=".json")
    os.close(fd)
    tmp_path = Path(tmp_name).resolve()

    try:
        cmd = [
            str(_OSV_EXE),
            "scan", "source",
            "-r",
            "--no-ignore",
            f"--config={_OSV_CONFIG}",
            "--format=json",
            f"--output-file={tmp_path}",
            str(target),
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(target),
            )
        except subprocess.TimeoutExpired:
            raise OSVError(f"osv-scanner timed out after {timeout}s")
        except FileNotFoundError:
            raise OSVError("osv-scanner executable not found")

        stderr = (proc.stderr or "").strip()

        if _is_network_error(proc.returncode, stderr):
            return _empty_result(
                reason="Internet not available - dependencies check skipped",
                network_unavailable=True,
            )

        if proc.returncode not in (0, 1):
            snippet = stderr[:300] if stderr else "(no stderr)"
            raise OSVError(f"osv-scanner exit {proc.returncode}: {snippet}")

        if not tmp_path.exists() or tmp_path.stat().st_size == 0:
            return _empty_result()

        try:
            with open(tmp_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            raise OSVError(f"osv-scanner JSON parse failed: {exc}")

        issues = _transform(data if isinstance(data, dict) else {}, target)
        return {
            "scanner": "osv",
            "ok": True,
            "issues": issues,
            "by_severity": _severity_counts(issues),
            "total": len(issues),
        }
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        _restore_manifest_boms(stripped)
        _restore_repo_configs(hidden)