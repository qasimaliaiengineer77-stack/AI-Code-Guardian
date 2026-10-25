"""Scan orchestration: bandit + gitleaks + osv + pylint + radon -> filter -> redact -> save."""
from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple

from backend.ai.explainer import AIExplainer, AIExplainerError
from backend.ai.redaction import redact_issues
from backend.core.config import WORKSPACE_DIR
from backend.input_handler.uploads import scan_dir
from backend.scanners.bandit_scanner import scan_with_bandit
from backend.scanners.pylint_scanner import scan_with_pylint
from backend.scanners.radon_scanner import scan_with_radon
from backend.scanners.gitleaks_scanner import scan_with_gitleaks
from backend.scanners.osv_scanner import scan_with_osv
from backend.storage.db import (
    _connect,
    cleanup_expired_scans,
    init_db,
    scans_db_path,
    state_db_path,
)
from backend.storage.persistent import (
    compute_project_id,
    compute_project_key_from_pairs,
    is_ignored,
    message_hash as _hash_message,
    save_file_hash,
)
from backend.storage.scans import get_scan, save_scan
from backend.orchestrator.resources import count_workspace, should_degrade, snapshot
from backend.orchestrator.batching import maybe_plan, merge_issues

_SCAN_ID_RE = re.compile(r"^[a-f0-9]{32}$")
_AI_COOLDOWN_SECONDS = 60
_AI_CIRCUIT_LOCK = threading.Lock()
_AI_CIRCUIT: dict = {"failed_until": None, "last_error": None}


def _merge_scanner_parts(parts: list, scanner_name: str) -> Optional[dict]:
    """Merge per-chunk scanner results into one; None if all parts empty."""
    valid = [p for p in parts if isinstance(p, dict)]
    if not valid:
        return None
    if len(valid) == 1:
        return valid[0]
    base = dict(valid[0])
    all_issues: list = []
    all_errors: list = []
    sev: dict = {}
    ok_all = True
    for p in valid:
        all_issues.extend(p.get("issues") or [])
        all_errors.extend(p.get("scan_errors") or [])
        if not p.get("ok", False):
            ok_all = False
        for k, v in (p.get("by_severity") or {}).items():
            try:
                sev[k] = sev.get(k, 0) + int(v or 0)
            except (TypeError, ValueError):
                sev[k] = sev.get(k, 0)
    merged = merge_issues([all_issues])
    base["issues"] = merged
    base["total_issues"] = len(merged)
    if "total" in base:
        base["total"] = len(merged)
    base["scan_errors"] = all_errors
    base["by_severity"] = sev
    base["ok"] = ok_all
    return base


class ScanRunError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def _ai_circuit_snapshot() -> Tuple[bool, int]:
    with _AI_CIRCUIT_LOCK:
        until = _AI_CIRCUIT["failed_until"]
        _err = _AI_CIRCUIT["last_error"]
    if until is None:
        return True, 0
    remaining = int((until - datetime.now(timezone.utc)).total_seconds())
    if remaining <= 0:
        return True, 0
    return False, remaining


def _mark_ai_failed(err: Exception) -> None:
    with _AI_CIRCUIT_LOCK:
        _AI_CIRCUIT["failed_until"] = (
            datetime.now(timezone.utc) + timedelta(seconds=_AI_COOLDOWN_SECONDS)
        )
        _AI_CIRCUIT["last_error"] = type(err).__name__


def _reset_ai_circuit() -> None:
    with _AI_CIRCUIT_LOCK:
        _AI_CIRCUIT["failed_until"] = None
        _AI_CIRCUIT["last_error"] = None


def _scanner_summary(r: Optional[dict]) -> dict:
    if not r:
        return {"ok": False, "total_issues": 0, "by_severity": {}, "scan_errors": []}
    out = {
        "ok": bool(r.get("ok")),
        "total_issues": int(r.get("total_issues", r.get("total", 0)) or 0),
        "by_severity": dict(r.get("by_severity") or {}),
        "scan_errors": list(r.get("scan_errors") or []),
    }
    if r.get("skipped_reason"):
        out["skipped_reason"] = str(r["skipped_reason"])
    if r.get("network_unavailable"):
        out["network_unavailable"] = True
    return out


def _merge_severity(*dicts: dict) -> dict:
    out: dict = {}
    for d in dicts:
        for k, v in (d or {}).items():
            out[k] = out.get(k, 0) + int(v or 0)
    return out


def _count_severity(issues: list) -> dict:
    out: dict = {}
    for i in issues:
        s = (i.get("severity") or "").lower()
        if s:
            out[s] = out.get(s, 0) + 1
    return out


def _collect_issues(*results: Optional[dict]) -> list:
    out = []
    for r in results:
        if r and r.get("ok"):
            out.extend(r.get("issues") or [])
    return out


def _filter_ignored(issues: list, project_key: str, project_id: Optional[str] = None) -> list:
    """Drop findings in the project's ignore list (dual-key P1)."""
    kept = []
    for i in issues:
        if is_ignored(
            project_key=project_key,
            project_id=project_id,
            file=i.get("file", "") or "",
            rule_id=i.get("rule_id", "") or "",
            line=i.get("line"),
            message_hash=_hash_message(i.get("message", "") or ""),
        ):
            continue
        kept.append(i)
    return kept


def _merge_explanations(issues: list, explained: list) -> list:
    out = []
    for issue, ex in zip(issues, explained):
        merged = dict(issue)
        if ex:
            merged["explanation"] = ex.get("explanation", "")
            merged["explanation_available"] = bool(ex.get("available", False))
            merged["explanation_provider"] = ex.get("provider", "none")
        else:
            merged["explanation"] = ""
            merged["explanation_available"] = False
            merged["explanation_provider"] = "none"
        out.append(merged)
    return out


def _attach_explanations(
    issues: list, language: str, explain_enabled: bool
) -> Tuple[list, str, Optional[str]]:
    if not issues:
        return [], ("ok" if explain_enabled else "disabled"), None

    if not explain_enabled:
        explainer = AIExplainer(provider="none")
        explained = explainer.explain_issues(issues, language)
        return _merge_explanations(issues, explained), "disabled", "AI explanation skipped by request"

    base = AIExplainer()
    if not base.available:
        explainer = AIExplainer(provider="none")
        explained = explainer.explain_issues(issues, language)
        return (
            _merge_explanations(issues, explained),
            "disabled",
            "AI explanation disabled (no API key configured)",
        )

    available, remaining = _ai_circuit_snapshot()
    if not available:
        explainer = AIExplainer(provider="none")
        explained = explainer.explain_issues(issues, language)
        return (
            _merge_explanations(issues, explained),
            "cooldown",
            f"AI explanation temporarily unavailable (retry in {remaining}s)",
        )

    try:
        explained = base.explain_issues(issues, language)
        _reset_ai_circuit()
        return _merge_explanations(issues, explained), "ok", None
    except AIExplainerError as e:
        _mark_ai_failed(e)
        explainer = AIExplainer(provider="none")
        explained = explainer.explain_issues(issues, language)
        return (
            _merge_explanations(issues, explained),
            "unavailable",
            "AI explanation temporarily unavailable",
        )


# ---------------- Step 1b helpers ----------------

def _hash_workspace(target: Path) -> Tuple[list, dict]:
    """SHA-256 every file. Returns (pairs [(path,sha)], sizes {path:size}). No DB touch."""
    pairs: list = []
    sizes: dict = {}
    for p in target.rglob("*"):
        if not p.is_file():
            continue
        try:
            h = hashlib.sha256()
            with p.open("rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            rel_path = str(p.relative_to(target)).replace("\\", "/")
            pairs.append((rel_path, h.hexdigest()))
            sizes[rel_path] = p.stat().st_size
        except Exception:
            pass
    return pairs, sizes


def _persist_hashes(scan_id: str, pairs: list, sizes: dict, project_key: str, project_id: Optional[str]) -> None:
    for rel_path, sha in pairs:
        try:
            save_file_hash(
                scan_id=scan_id,
                file=rel_path,
                sha256=sha,
                size_bytes=sizes.get(rel_path),
                project_key=project_key,
                project_id=project_id,
            )
        except Exception:
            pass


def _find_previous_scan(scan_id: str, project_id: Optional[str]) -> Optional[dict]:
    """Most recent 'done' scan (excluding current) with same project_id."""
    if not project_id:
        return None
    try:
        with _connect(scans_db_path()) as c:
            row = c.execute(
                "SELECT scan_id, result_json FROM scans "
                "WHERE project_id = ? AND scan_id != ? AND status = 'done' "
                "ORDER BY created_at DESC LIMIT 1",
                (project_id, scan_id),
            ).fetchone()
    except Exception:
        return None
    if not row:
        return None
    result = None
    if row[1]:
        try:
            result = json.loads(row[1])
        except Exception:
            result = None
    return {"scan_id": row[0], "result": result}


def _is_partial_result(result) -> bool:
    """True if any (non-OSV) scanner was skipped or failed in the previous result.

    OSV is exempt: it always runs whole-workspace (condition 2) and legit-skips
    on missing manifest / offline / network. It never participates in incremental.
    """
    if not isinstance(result, dict):
        return True
    blocking_skips = [
        s for s in (result.get("skipped_scanners") or []) if s != "osv"
    ]
    if blocking_skips:
        return True
    for name, sc in (result.get("scanners") or {}).items():
        if name == "osv":
            continue
        if isinstance(sc, dict) and sc.get("ok") is False:
            return True
    return False


def _read_prev_hashes(project_id: Optional[str]) -> dict:
    """{file: sha256} — latest hash per file for the given project_id."""
    if not project_id:
        return {}
    try:
        with _connect(state_db_path()) as c:
            rows = c.execute(
                "SELECT file, sha256 FROM file_hashes "
                "WHERE project_id = ? ORDER BY added_at DESC",
                (project_id,),
            ).fetchall()
    except Exception:
        return {}
    seen: dict = {}
    for r in rows:
        if r[0] not in seen:
            seen[r[0]] = r[1]
    return seen


def _diff_files(curr_pairs: list, prev_hashes: dict) -> Tuple[list, list, list, list]:
    """Return (unchanged, changed, added, deleted) file paths."""
    curr = {p: h for p, h in curr_pairs}
    unchanged = [p for p, h in curr.items() if p in prev_hashes and prev_hashes[p] == h]
    changed = [p for p, h in curr.items() if p in prev_hashes and prev_hashes[p] != h]
    added = [p for p in curr if p not in prev_hashes]
    deleted = [p for p in prev_hashes if p not in curr]
    return unchanged, changed, added, deleted


def _carry_forward(prev_result, unchanged_paths: list) -> list:
    """Issues from prev_result whose file is in unchanged set."""
    if not isinstance(prev_result, dict) or not unchanged_paths:
        return []
    unchanged_set = set(unchanged_paths)
    out = []
    for issue in (prev_result.get("issues") or []):
        if isinstance(issue, dict) and (issue.get("file") or "") in unchanged_set:
            out.append(dict(issue))
    return out


def _filter_chunks(chunk_plan, keep_paths: list):
    """Filter chunk_plan to only include files in keep_paths. None if empty."""
    if not chunk_plan or not keep_paths:
        return None
    keep_set = set(str(p).replace("\\", "/") for p in keep_paths)
    filtered = []
    for chunk in chunk_plan:
        sub = []
        for f in chunk:
            s = str(f).replace("\\", "/")
            if s in keep_set:
                sub.append(f)
        if sub:
            filtered.append(sub)
    return filtered or None


# ---------------- main entry ----------------

def run_scan(
    scan_id: str,
    *,
    language: str = "en",
    explain: bool = True,
    security: bool = True,
    quality: bool = True,
    dependencies: bool = True,
    retention_days: int = 2,
) -> dict:
    if not _SCAN_ID_RE.match(scan_id or ""):
        raise ScanRunError("invalid scan_id", 400)

    if not security and not quality and not dependencies:
        raise ScanRunError(
            "at least one of 'security', 'quality' or 'dependencies' must be enabled", 400
        )

    expected = Path(WORKSPACE_DIR) / scan_id
    if not expected.exists() or not expected.is_dir():
        raise ScanRunError("workspace not found", 404)

    target = Path(scan_dir(scan_id))

    # --- 1. Existing scan row for source/source_ref (github may be pre-set) ---
    _existing = get_scan(scan_id) or {}
    _source = _existing.get("source") or "local"
    _source_ref = _existing.get("source_ref") or scan_id

    # --- 2. Hash workspace (no DB write yet) ---
    _pairs, _sizes = _hash_workspace(target)
    _paths = [p for p, _ in _pairs]

    # --- 3. Compute keys ---
    project_key = compute_project_key_from_pairs(_pairs, scan_id)
    project_id = compute_project_id(_source, _source_ref, _paths)

    # --- 4. Previous scan + hashes (BEFORE persisting) ---
    _prev = _find_previous_scan(scan_id, project_id)
    _prev_result = (_prev or {}).get("result")
    _prev_partial = _is_partial_result(_prev_result) if _prev else False
    _prev_hashes = _read_prev_hashes(project_id)

    # --- 5. Diff + incremental decision ---
    _prev_options = (_prev_result or {}).get("options") or {}
    _options_mismatch = bool(_prev) and (
        bool(_prev_options.get("security")) != bool(security)
        or bool(_prev_options.get("quality")) != bool(quality)
    )

    if _paths and _prev and not _prev_partial and not _options_mismatch and _prev_hashes:
        _unchanged, _changed, _added, _deleted = _diff_files(_pairs, _prev_hashes)
        _incremental_on = True
        _incremental_reason = None
    else:
        _unchanged, _changed, _added, _deleted = [], [], [], []
        _incremental_on = False
        if not _paths:
            _incremental_reason = "empty_workspace"
        elif _prev is None:
            _incremental_reason = "no_previous_scan"
        elif _prev_partial:
            _incremental_reason = "previous_partial"
        elif _options_mismatch:
            _incremental_reason = "options_mismatch"
        elif not _prev_hashes:
            _incremental_reason = "no_previous_hashes"
        else:
            _incremental_reason = None

    # --- 6. Persist current hashes ---
    _persist_hashes(scan_id, _pairs, _sizes, project_key, project_id)

    # --- 7. Save running ---
    init_db()
    cleanup_expired_scans()
    save_scan(
        scan_id,
        source=_source, source_ref=_source_ref, status="running",
        project_key=project_key, project_id=project_id,
        retention_days=retention_days,
    )
    _res_snap = snapshot()
    _res_counts = count_workspace(target)
    _degrade, _degrade_reason = should_degrade(
        _res_counts["file_count"], _res_counts["total_bytes"], _res_snap
    )
    print(
        "[resources] free_ram=%sMB cpu=%s files=%s bytes=%s degrade=%s%s"
        % (
            _res_snap.get("available_ram_mb"),
            _res_snap.get("cpu_count"),
            _res_counts["file_count"],
            _res_counts["total_bytes"],
            _degrade,
            (" reason=" + _degrade_reason) if _degrade_reason else "",
        )
    )
    _chunk_plan = maybe_plan(target, _res_counts["file_count"], _res_counts["total_bytes"])
    _chunk_count = len(_chunk_plan) if _chunk_plan else 0
    if _chunk_plan and _degrade:
        _free_ram = _res_snap.get("available_ram_mb")
        if _free_ram is not None and _free_ram >= 512:
            _degrade = False
            _degrade_reason = None
    if _chunk_plan and not _degrade:
        print(
            "[batching] chunk_count=%s pylint_cross_file_limited=True"
            % (_chunk_count,)
        )
    if _incremental_on:
        print(
            "[incremental] on unchanged=%s changed=%s added=%s deleted=%s"
            % (len(_unchanged), len(_changed), len(_added), len(_deleted))
        )

    # --- 8. Scan targets for incremental (changed+added) ---
    _scan_files = None
    if _incremental_on:
        _scan_files = list(_changed) + list(_added)

    b = None
    g = None
    p = None
    r = None
    o = None
    skipped: list = []
    try:
        if security:
            # Bandit: incremental or full
            if _incremental_on:
                if _scan_files:
                    if _chunk_plan:
                        _filtered = _filter_chunks(_chunk_plan, _scan_files)
                        if _filtered:
                            b = _merge_scanner_parts(
                                [scan_with_bandit(target, files=c) for c in _filtered],
                                "bandit",
                            )
                    else:
                        b = scan_with_bandit(target, files=_scan_files)
            else:
                if _chunk_plan:
                    b = _merge_scanner_parts(
                        [scan_with_bandit(target, files=chunk) for chunk in _chunk_plan],
                        "bandit",
                    )
                else:
                    b = scan_with_bandit(target)
            # Gitleaks: always full
            g = scan_with_gitleaks(target)
        else:
            skipped.append("bandit")
            skipped.append("gitleaks")

        if quality and not _degrade:
            # Pylint: always full
            if _chunk_plan:
                p = _merge_scanner_parts(
                    [scan_with_pylint(target, files=chunk) for chunk in _chunk_plan],
                    "pylint",
                )
            else:
                p = scan_with_pylint(target)
            # Radon: incremental or full
            if _incremental_on:
                if _scan_files:
                    if _chunk_plan:
                        _filtered_r = _filter_chunks(_chunk_plan, _scan_files)
                        if _filtered_r:
                            r = _merge_scanner_parts(
                                [scan_with_radon(target, files=c) for c in _filtered_r],
                                "radon",
                            )
                    else:
                        r = scan_with_radon(target, files=_scan_files)
            else:
                if _chunk_plan:
                    r = _merge_scanner_parts(
                        [scan_with_radon(target, files=chunk) for chunk in _chunk_plan],
                        "radon",
                    )
                else:
                    r = scan_with_radon(target)
        else:
            skipped.append("pylint")
            skipped.append("radon")

        if dependencies:
            try:
                o = scan_with_osv(target)
            except Exception:
                o = None
                skipped.append("osv")
        else:
            skipped.append("osv")
    except Exception as e:
        err_name = type(e).__name__
        save_scan(
            scan_id,
            source=_source, source_ref=_source_ref, status="error",
            error_message=err_name,
            project_key=project_key, project_id=project_id,
            retention_days=retention_days,
        )
        raise ScanRunError(f"scanner error: {err_name}", 500)

    # --- 9. Fresh issues + carry-forward ---
    raw_issues = _collect_issues(b, g, p, r, o)
    safe_issues = redact_issues(raw_issues)
    filtered_fresh = _filter_ignored(safe_issues, project_key, project_id)

    _carried = _carry_forward(_prev_result, _unchanged) if _incremental_on else []
    filtered_carried = _filter_ignored(_carried, project_key, project_id)

    # --- 10. Explanations (fresh only — carried keeps previous explanation) ---
    explained_fresh, ai_status, ai_message = _attach_explanations(
        filtered_fresh, language, explain
    )
    explained = explained_fresh + filtered_carried

    b_sum = _scanner_summary(b)
    g_sum = _scanner_summary(g)
    p_sum = _scanner_summary(p)
    r_sum = _scanner_summary(r)
    o_sum = _scanner_summary(o)

    result = {
        "scan_id": scan_id,
        "status": "done",
        "finished_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scanners": {"bandit": b_sum, "gitleaks": g_sum, "pylint": p_sum, "radon": r_sum, "osv": o_sum},
        "total_issues": len(explained),
        "by_severity": _merge_severity(
            b_sum["by_severity"], g_sum["by_severity"],
            p_sum["by_severity"], r_sum["by_severity"], o_sum["by_severity"],
            _count_severity(filtered_carried),
        ),
        "issues": explained,
        "ai_status": ai_status,
        "ai_message": ai_message,
        "options": {
            "security": bool(security),
            "quality": bool(quality),
            "explain": bool(explain),
            "dependencies": bool(dependencies),
        },
        "skipped_scanners": skipped,
        "chunking": {
            "enabled": bool(_chunk_plan) and not _degrade,
            "chunk_count": _chunk_count if _chunk_plan else 0,
            "pylint_cross_file_limited": bool(_chunk_plan) and not _degrade and bool(quality),
        },
        "incremental": {
            "enabled": _incremental_on,
            "project_id": project_id,
            "reason": _incremental_reason,
            "unchanged_count": len(_unchanged),
            "changed_count": len(_changed),
            "added_count": len(_added),
            "deleted_count": len(_deleted),
            "carried_forward_count": len(filtered_carried),
        },
    }

    save_scan(
        scan_id,
        source=_source, source_ref=_source_ref, status="done",
        result=result,
        project_key=project_key, project_id=project_id,
        retention_days=retention_days,
    )
    return result