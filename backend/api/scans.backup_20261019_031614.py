import sqlite3
import threading

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks

from ..orchestrator import run_scan, ScanRunError
from ..storage.scans import get_scan, list_scans, delete_scan
from ..storage.db import scans_db_path
from ..core.config import WORKSPACE_DIR


router = APIRouter(prefix="/api/scans", tags=["scans"])

_ALLOWED_LANGUAGES = {"en", "roman_urdu"}

# In-memory guard against concurrent runs of the same scan_id
_RUNNING = set()
_RUNNING_LOCK = threading.Lock()


def _mark_running(scan_id: str) -> None:
    """Best-effort: set status='running' on existing row. No-op if row absent."""
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
        # fresh upload: row not inserted yet — run_scan will create it
        pass


def _run_and_untrack(
    scan_id: str,
    language: str,
    explain: bool,
    security: bool,
    quality: bool,
) -> None:
    try:
        run_scan(
            scan_id,
            language=language,
            explain=explain,
            security=security,
            quality=quality,
        )
    except ScanRunError:
        # run_scan already wrote status='error' + message to DB
        pass
    except Exception:
        # never let a background-task exception crash the worker silently
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
):
    # NOTE: 'dependencies' is UI-only (Phase 2). It is intentionally NOT declared
    # here — FastAPI silently ignores the unknown query param, matching the
    # documented rule "backend never honors it".

    if language not in _ALLOWED_LANGUAGES:
        language = "en"

    # STEP 11c guard — refuse a scan that would run zero scanners.
    if not security and not quality:
        raise HTTPException(
            status_code=400,
            detail="At least one of 'security' or 'quality' must be enabled",
        )

    # Rule 10: reject non-existent / traversal-like scan_id BEFORE any mkdir
    target = WORKSPACE_DIR / scan_id
    if not target.is_dir():
        raise HTTPException(status_code=404, detail="Scan workspace not found")

    with _RUNNING_LOCK:
        if scan_id in _RUNNING:
            raise HTTPException(status_code=409, detail="Scan already running")
        _RUNNING.add(scan_id)

    _mark_running(scan_id)

    background_tasks.add_task(
        _run_and_untrack, scan_id, language, explain, security, quality
    )
    return {
        "scan_id": scan_id,
        "status": "running",
        "options": {
            "security": bool(security),
            "quality": bool(quality),
            "explain": bool(explain),
            "dependencies": False,  # UI-only; backend never honors it
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
    return row


@router.delete("/{scan_id}")
def delete_one(scan_id: str):
    ok = delete_scan(scan_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Scan not found")
    return {"deleted": scan_id}