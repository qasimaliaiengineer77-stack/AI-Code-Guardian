"""Scan-results CRUD for the auto-expiring DB (Rule 7)."""
from __future__ import annotations

import json
from typing import Any, Optional

from backend.storage.db import _connect, scans_db_path, utcnow_iso, expiry_iso


def save_scan(
    scan_id: str,
    *,
    source: str,
    source_ref: str,
    status: str,
    result: Optional[Any] = None,
    error_message: Optional[str] = None,
    retention_days: int = 2,
    project_key: Optional[str] = None,
) -> None:
    """Insert or update a scan row. Expiry always reset on write."""
    result_json = json.dumps(result, ensure_ascii=False) if result is not None else None
    with _connect(scans_db_path()) as c:
        c.execute(
            """
            INSERT INTO scans
                (scan_id, created_at, expires_at, source, source_ref,
                 status, result_json, error_message, project_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(scan_id) DO UPDATE SET
                status        = excluded.status,
                result_json   = excluded.result_json,
                error_message = excluded.error_message,
                expires_at    = excluded.expires_at,
                project_key   = COALESCE(excluded.project_key, scans.project_key)
            """,
            (
                scan_id, utcnow_iso(), expiry_iso(days=retention_days),
                source, source_ref, status,
                result_json, error_message, project_key,
            ),
        )


def get_scan(scan_id: str) -> Optional[dict]:
    with _connect(scans_db_path()) as c:
        row = c.execute(
            "SELECT * FROM scans WHERE scan_id = ?", (scan_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_scans(limit: int = 50) -> list[dict]:
    with _connect(scans_db_path()) as c:
        rows = c.execute(
            "SELECT scan_id, created_at, expires_at, source, source_ref, "
            "status, error_message FROM scans "
            "ORDER BY created_at DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_scan(scan_id: str) -> bool:
    with _connect(scans_db_path()) as c:
        cur = c.execute("DELETE FROM scans WHERE scan_id = ?", (scan_id,))
        return cur.rowcount > 0


def _row_to_dict(row) -> dict:
    d = dict(row)
    raw = d.pop("result_json", None)
    if raw:
        try:
            d["result"] = json.loads(raw)
        except json.JSONDecodeError:
            d["result"] = None
    else:
        d["result"] = None
    return d