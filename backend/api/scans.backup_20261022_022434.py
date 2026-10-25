import json
import re
import sqlite3
import threading

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Response
from pydantic import BaseModel

from ..orchestrator import run_scan, ScanRunError
from ..storage.scans import get_scan, list_scans, delete_scan
from ..storage.db import scans_db_path
from ..storage.persistent import (
    add_ignored,
    compute_project_key,
    delete_ignored,
    is_ignored,
    list_ignored,
    message_hash,
)
from ..core.config import WORKSPACE_DIR
from ..ai.redaction import redact_issue


router = APIRouter(prefix="/api/scans", tags=["scans"])

_ALLOWED_LANGUAGES = {"en", "roman_urdu"}

_RUNNING = set()
_RUNNING_LOCK = threading.Lock()


class IgnoreBody(BaseModel):
    file: str
    rule_id: str
    line: int | None = None
    message: str = ""


def _mark_running(scan_id: str) -> None:
    try:
        con = sqlite3.connect(str(scans_db_path()))
        try:
            con.execute(
                "UPDATE scans SET status='running' WHERE scan_id=?",
                (scan_id,),
            )
            con.commit()
        finally:
            con.close()
    except Exception:
        pass


def _run_and_untrack(
    scan_id: str,
    language: str,
    explain: bool,
    security: bool,
    quality: bool,
    dependencies: bool,
    retention_days: int,
) -> None:
    try:
        run_scan(
            scan_id,
            language=language,
            explain=explain,
            security=security,
            quality=quality,
            dependencies=dependencies,
            retention_days=retention_days,
        )
    except ScanRunError:
        pass
    except Exception:
        pass
    finally:
        with _RUNNING_LOCK:
            _RUNNING.discard(scan_id)


@router.post("/{scan_id}/run")
def run(
    scan_id: str,
    background_tasks: BackgroundTasks,
    language: str = Query("en"),
    explain: bool = Query(True),
    security: bool = Query(True),
    quality: bool = Query(True),
    dependencies: bool = Query(True),
    retention_days: int = Query(2),
):
    if language not in _ALLOWED_LANGUAGES:
        language = "en"

    if retention_days not in (1, 2):
        retention_days = 2

    if not security and not quality and not dependencies:
        raise HTTPException(
            status_code=400,
            detail="At least one of 'security', 'quality', or 'dependencies' must be enabled",
        )

    target = WORKSPACE_DIR / scan_id
    if not target.is_dir():
        raise HTTPException(status_code=404, detail="Scan workspace not found")

    with _RUNNING_LOCK:
        if scan_id in _RUNNING:
            raise HTTPException(status_code=409, detail="Scan already running")
        _RUNNING.add(scan_id)

    _mark_running(scan_id)

    background_tasks.add_task(
        _run_and_untrack, scan_id, language, explain, security, quality, dependencies, retention_days
    )
    return {
        "scan_id": scan_id,
        "status": "running",
        "options": {
            "security": bool(security),
            "quality": bool(quality),
            "explain": bool(explain),
            "dependencies": bool(dependencies),
            "retention_days": retention_days,
        },
    }


@router.get("")
def list_recent(limit: int = Query(50, ge=1, le=100)):
    return {"scans": list_scans(limit=limit)}


@router.get("/{scan_id}")
def get_one(scan_id: str):
    row = get_scan(scan_id)
    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")

    result = row.get("result")
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except Exception:
            return row
    if not isinstance(result, dict):
        return row

    issues = result.get("issues") or []
    if not issues:
        return row

    project_key = compute_project_key(scan_id)
    filtered = [
        i for i in issues
        if not is_ignored(
            project_key=project_key,
            file=(i.get("file") or ""),
            rule_id=(i.get("rule_id") or ""),
            line=i.get("line"),
            message_hash=message_hash(i.get("message") or ""),
        )
    ]

    if len(filtered) == len(issues):
        return row

    new_result = dict(result)
    new_result["issues"] = filtered
    new_result["total_issues"] = len(filtered)
    sev: dict = {}
    for i in filtered:
        s = (i.get("severity") or "LOW").upper()
        sev[s] = sev.get(s, 0) + 1
    new_result["by_severity"] = sev

    new_row = dict(row)
    new_row["result"] = new_result
    return new_row


@router.delete("/{scan_id}")
def delete_one(scan_id: str):
    ok = delete_scan(scan_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Scan not found")
    return {"deleted": scan_id}


# ---------------- ignore endpoints ----------------

@router.post("/{scan_id}/ignore")
def ignore_finding(scan_id: str, body: IgnoreBody):
    row = get_scan(scan_id)
    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")

    project_key = compute_project_key(scan_id)
    add_ignored(
        project_key=project_key,
        file=body.file or "",
        rule_id=body.rule_id or "",
        line=body.line,
        message_hash=message_hash(body.message or ""),
    )
    return {"ok": True}


@router.get("/{scan_id}/ignored")
def list_ignored_findings(scan_id: str):
    row = get_scan(scan_id)
    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")
    project_key = compute_project_key(scan_id)
    items = list_ignored(project_key=project_key)
    return {"items": items}


@router.delete("/{scan_id}/ignored/{ignore_id}")
def unignore(scan_id: str, ignore_id: int):
    row = get_scan(scan_id)
    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")
    project_key = compute_project_key(scan_id)
    ok = delete_ignored(ignore_id, project_key)
    if not ok:
        raise HTTPException(status_code=404, detail="Ignored finding not found")
    return {"deleted": ignore_id}


# ---------------- Phase 2 STEP 4: SARIF/JSON export ----------------

_SCAN_ID_RE = re.compile(r"^[a-f0-9]{32}$")
_EXPORT_FIELDS = ("file", "rule_id", "line", "message", "severity", "scanner", "package", "cwe_id")
_SARIF_LEVEL = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "note",
    "info": "note",
}
_GATE_FAIL_SEVERITIES = ("critical", "high")


def _export_issue(issue: dict) -> dict:
    redacted = redact_issue(dict(issue))
    return {k: redacted.get(k) for k in _EXPORT_FIELDS}


def _build_json_export(scan_id: str, result: dict, issues: list) -> dict:
    return {
        "scan_id": scan_id,
        "tool": "AI Code Guardian",
        "version": "1.0.0",
        "finished_at": result.get("finished_at"),
        "total_issues": len(issues),
        "by_severity": result.get("by_severity") or {},
        "issues": issues,
    }


def _build_sarif_export(issues: list) -> dict:
    rules_by_id: dict = {}
    results: list = []
    for it in issues:
        rule_id = it.get("rule_id") or it.get("scanner") or "unknown"
        if rule_id not in rules_by_id:
            rules_by_id[rule_id] = {
                "id": rule_id,
                "shortDescription": {"text": (it.get("message") or "")[:200]},
            }
        try:
            line_no = int(it.get("line") or 1)
        except (TypeError, ValueError):
            line_no = 1
        results.append({
            "ruleId": rule_id,
            "level": _SARIF_LEVEL.get((it.get("severity") or "").lower(), "note"),
            "message": {"text": it.get("message") or ""},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {"uri": it.get("file") or ""},
                    "region": {"startLine": line_no},
                }
            }],
            "properties": {
                "scanner": it.get("scanner"),
                "package": it.get("package"),
                "cwe_id": it.get("cwe_id"),
            },
        })
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": "AI Code Guardian",
                "version": "1.0.0",
                "rules": list(rules_by_id.values()),
            }},
            "results": results,
        }],
    }


@router.get("/{scan_id}/export")
def export_scan(scan_id: str, fmt: str = Query(..., alias="format")):
    if fmt not in ("sarif", "json"):
        raise HTTPException(status_code=400, detail="format must be 'sarif' or 'json'")
    if not _SCAN_ID_RE.match(scan_id):
        raise HTTPException(status_code=400, detail="invalid scan_id")

    row = get_scan(scan_id)
    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")

    if row.get("status") != "done":
        raise HTTPException(status_code=409, detail="scan not finished")

    result = row.get("result")
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except Exception:
            result = {}
    if not isinstance(result, dict):
        result = {}

    raw_issues = result.get("issues") or []
    issues = [_export_issue(i) for i in raw_issues if isinstance(i, dict)]

    if fmt == "json":
        body = json.dumps(
            _build_json_export(scan_id, result, issues),
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        return Response(
            content=body,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="guardian-{scan_id}.json"'
            },
        )

    body = json.dumps(
        _build_sarif_export(issues),
        ensure_ascii=False,
        indent=2,
        default=str,
    )
    return Response(
        content=body,
        media_type="application/sarif+json",
        headers={
            "Content-Disposition": f'attachment; filename="guardian-{scan_id}.sarif"'
        },
    )


# ---------------- Phase 2: Severity quality gate ----------------

def _count_gate_issues(issues: list) -> dict:
    critical_count = 0
    high_count = 0
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        sev = str(issue.get("severity") or "").strip().lower()
        if sev not in _GATE_FAIL_SEVERITIES:
            continue
        if sev == "critical":
            critical_count += 1
        elif sev == "high":
            high_count += 1
    return {"critical_count": critical_count, "high_count": high_count}


@router.get("/{scan_id}/gate")
def gate_scan(scan_id: str):
    if not _SCAN_ID_RE.match(scan_id):
        raise HTTPException(status_code=400, detail="invalid scan_id")

    row = get_scan(scan_id)
    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")

    if row.get("status") != "done":
        raise HTTPException(status_code=409, detail="scan not finished")

    result = row.get("result")
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except Exception:
            result = {}
    if not isinstance(result, dict):
        result = {}

    raw_issues = result.get("issues") or []
    counts = _count_gate_issues(raw_issues)
    passed = (counts["critical_count"] + counts["high_count"]) == 0
    return {
        "passed": passed,
        "high_count": counts["high_count"],
        "critical_count": counts["critical_count"],
    }