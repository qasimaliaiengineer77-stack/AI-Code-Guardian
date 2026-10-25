"""Scan orchestration: bandit + pylint + radon -> redact -> explain -> save.

Rules enforced here:
- Rule 1: never executes scanned code (delegates to static scanners only).
- Rule 2: fixed configs (delegated to scanners).
- Rule 3: only redacted issues leave this module.
- Rule 4: explainer receives only safe issue dicts.
- Rule 7: results auto-expire via storage layer.
- Retry control: circuit breaker prevents repeated AI calls after a failure.
- Thread safety: _AI_CIRCUIT is guarded by _AI_CIRCUIT_LOCK.

STEP 11c — Scan Options:
- security=False  -> bandit skipped.
- quality=False   -> pylint + radon skipped.
- Guard: at least one of security/quality must be True (else 400).
- dependencies    -> UI-ONLY (Phase 2). Backend NEVER receives or honors it.
- explain=False   -> fallback (deterministic) explanations only.
"""
from __future__ import annotations

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
from backend.storage.db import cleanup_expired_scans, init_db
from backend.storage.scans import save_scan

_SCAN_ID_RE = re.compile(r"^[a-f0-9]{32}$")
_AI_COOLDOWN_SECONDS = 60
_AI_CIRCUIT_LOCK = threading.Lock()
_AI_CIRCUIT: dict = {"failed_until": None, "last_error": None}


class ScanRunError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def _ai_circuit_snapshot() -> Tuple[bool, int]:
    """Thread-safe read: (available, remaining_seconds_if_in_cooldown)."""
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
    return {
        "ok": bool(r.get("ok")),
        "total_issues": int(r.get("total_issues", 0) or 0),
        "by_severity": dict(r.get("by_severity") or {}),
        "scan_errors": list(r.get("scan_errors") or []),
    }


def _merge_severity(*dicts: dict) -> dict:
    out: dict = {}
    for d in dicts:
        for k, v in (d or {}).items():
            out[k] = out.get(k, 0) + int(v or 0)
    return out


def _collect_issues(*results: Optional[dict]) -> list:
    out = []
    for r in results:
        if r and r.get("ok"):
            out.extend(r.get("issues") or [])
    return out


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


def run_scan(
    scan_id: str,
    *,
    language: str = "en",
    explain: bool = True,
    security: bool = True,
    quality: bool = True,
) -> dict:
    # Rule 10 (traversal guard) — cheapest, security-critical, checked first.
    if not _SCAN_ID_RE.match(scan_id or ""):
        raise ScanRunError("invalid scan_id", 400)

    # STEP 11c guard — refuse a scan that would run zero scanners.
    if not security and not quality:
        raise ScanRunError(
            "at least one of 'security' or 'quality' must be enabled", 400
        )

    # scan_dir() may create the directory; check the raw path first.
    expected = Path(WORKSPACE_DIR) / scan_id
    if not expected.exists() or not expected.is_dir():
        raise ScanRunError("workspace not found", 404)

    target = Path(scan_dir(scan_id))

    init_db()
    cleanup_expired_scans()
    save_scan(scan_id, source="local", source_ref=scan_id, status="running")

    b = None
    p = None
    r = None
    skipped: list = []

    try:
        if security:
            b = scan_with_bandit(target)
        else:
            skipped.append("bandit")
        if quality:
            p = scan_with_pylint(target)
            r = scan_with_radon(target)
        else:
            skipped.append("pylint")
            skipped.append("radon")
    except Exception as e:
        err_name = type(e).__name__
        save_scan(scan_id, source="local", source_ref=scan_id, status="error", error_message=err_name)
        raise ScanRunError(f"scanner error: {err_name}", 500)

    raw_issues = _collect_issues(b, p, r)
    safe_issues = redact_issues(raw_issues)
    explained, ai_status, ai_message = _attach_explanations(safe_issues, language, explain)

    b_sum = _scanner_summary(b)
    p_sum = _scanner_summary(p)
    r_sum = _scanner_summary(r)

    result = {
        "scan_id": scan_id,
        "status": "done",
        "finished_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scanners": {"bandit": b_sum, "pylint": p_sum, "radon": r_sum},
        "total_issues": len(explained),
        "by_severity": _merge_severity(
            b_sum["by_severity"], p_sum["by_severity"], r_sum["by_severity"]
        ),
        "issues": explained,
        "ai_status": ai_status,
        "ai_message": ai_message,
        "options": {
            "security": bool(security),
            "quality": bool(quality),
            "explain": bool(explain),
            "dependencies": False,  # UI-only; backend never honors it
        },
        "skipped_scanners": skipped,
    }

    save_scan(scan_id, source="local", source_ref=scan_id, status="done", result=result)
    return result