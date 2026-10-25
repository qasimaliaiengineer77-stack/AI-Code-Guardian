"""Ignore list + file hashes — NEVER auto-deleted (Rule 7)."""
from __future__ import annotations

from typing import Optional

from backend.storage.db import _connect, state_db_path, utcnow_iso


def add_ignored(
    *,
    scan_id: str,
    file: str,
    rule_id: str,
    line: Optional[int],
    message_hash: str,
) -> None:
    with _connect(state_db_path()) as c:
        c.execute(
            """
            INSERT OR IGNORE INTO ignored_findings
                (scan_id, file, rule_id, line, message_hash, added_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (scan_id, file, rule_id, line, message_hash, utcnow_iso()),
        )


def list_ignored(scan_id: Optional[str] = None) -> list[dict]:
    with _connect(state_db_path()) as c:
        if scan_id:
            rows = c.execute(
                "SELECT * FROM ignored_findings WHERE scan_id = ? "
                "ORDER BY added_at DESC",
                (scan_id,),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM ignored_findings ORDER BY added_at DESC"
            ).fetchall()
    return [dict(r) for r in rows]


def is_ignored(
    *,
    file: str,
    rule_id: str,
    line: Optional[int],
    message_hash: str,
) -> bool:
    with _connect(state_db_path()) as c:
        row = c.execute(
            """
            SELECT 1 FROM ignored_findings
            WHERE file = ? AND rule_id = ? AND line IS ? AND message_hash = ?
            LIMIT 1
            """,
            (file, rule_id, line, message_hash),
        ).fetchone()
    return row is not None


def save_file_hash(
    *,
    scan_id: str,
    file: str,
    sha256: str,
    size_bytes: Optional[int],
) -> None:
    with _connect(state_db_path()) as c:
        c.execute(
            """
            INSERT INTO file_hashes (scan_id, file, sha256, size_bytes, added_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (scan_id, file, sha256, size_bytes, utcnow_iso()),
        )


def list_file_hashes(scan_id: Optional[str] = None) -> list[dict]:
    with _connect(state_db_path()) as c:
        if scan_id:
            rows = c.execute(
                "SELECT * FROM file_hashes WHERE scan_id = ? ORDER BY file",
                (scan_id,),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM file_hashes ORDER BY added_at DESC"
            ).fetchall()
    return [dict(r) for r in rows]