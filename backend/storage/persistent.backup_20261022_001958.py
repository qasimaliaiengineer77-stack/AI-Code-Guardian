"""Ignore list + file hashes — NEVER auto-deleted (Rule 7)."""
from __future__ import annotations

import hashlib
import threading
from typing import Optional

from backend.storage.db import _connect, state_db_path, utcnow_iso


# ---------------- utilities ----------------

def message_hash(msg: str) -> str:
    """SHA-256 of a finding's message. Same on add & filter sides."""
    return hashlib.sha256((msg or "").encode("utf-8")).hexdigest()


def compute_project_key(scan_id: str) -> str:
    """Project fingerprint = SHA-256 of sorted (file:sha256) pairs.

    Same project, same content -> same key -> ignores persist across scans.
    Different project -> different key -> no cross-project ignore leak.
    Falls back to sha256(scan_id) if no file hashes exist.
    """
    rows = list_file_hashes(scan_id)
    parts = sorted(f"{r.get('file','')}:{r.get('sha256','')}" for r in rows)
    if not parts:
        return hashlib.sha256((scan_id or "").encode("utf-8")).hexdigest()
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


# ---------------- migration (lazy, idempotent) ----------------

_MIGRATION_DONE = False
_MIGRATION_LOCK = threading.Lock()


def _ensure_migration() -> None:
    """Add project_key column + rebuild unique index if not present."""
    global _MIGRATION_DONE
    if _MIGRATION_DONE:
        return
    with _MIGRATION_LOCK:
        if _MIGRATION_DONE:
            return
        try:
            with _connect(state_db_path()) as c:
                tables = [r[0] for r in c.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()]
                if "ignored_findings" not in tables:
                    _MIGRATION_DONE = True
                    return
                cols = [r[1] for r in c.execute(
                    "PRAGMA table_info(ignored_findings)"
                ).fetchall()]
                if "project_key" not in cols:
                    c.execute("ALTER TABLE ignored_findings ADD COLUMN project_key TEXT")
                    c.execute("DROP INDEX IF EXISTS idx_ignored_unique")
                    c.execute(
                        "CREATE UNIQUE INDEX IF NOT EXISTS idx_ignored_unique "
                        "ON ignored_findings(project_key, file, rule_id, line, message_hash)"
                    )
            _MIGRATION_DONE = True
        except Exception:
            pass


# ---------------- ignore list ----------------

def add_ignored(
    *,
    project_key: str,
    file: str,
    rule_id: str,
    line: Optional[int],
    message_hash: str,
) -> None:
    _ensure_migration()
    with _connect(state_db_path()) as c:
        c.execute(
            """
            INSERT OR IGNORE INTO ignored_findings
                (scan_id, project_key, file, rule_id, line, message_hash, added_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (project_key, project_key, file, rule_id, line, message_hash, utcnow_iso()),
        )


def list_ignored(project_key: Optional[str] = None) -> list[dict]:
    _ensure_migration()
    with _connect(state_db_path()) as c:
        if project_key:
            rows = c.execute(
                "SELECT id, file, rule_id, line, message_hash, added_at "
                "FROM ignored_findings WHERE project_key = ? "
                "ORDER BY added_at DESC",
                (project_key,),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT id, file, rule_id, line, message_hash, added_at "
                "FROM ignored_findings ORDER BY added_at DESC"
            ).fetchall()
    return [dict(r) for r in rows]


def is_ignored(
    *,
    project_key: str,
    file: str,
    rule_id: str,
    line: Optional[int],
    message_hash: str,
) -> bool:
    _ensure_migration()
    with _connect(state_db_path()) as c:
        row = c.execute(
            """
            SELECT 1 FROM ignored_findings
            WHERE project_key = ? AND file = ? AND rule_id = ?
              AND line IS ? AND message_hash = ?
            LIMIT 1
            """,
            (project_key, file, rule_id, line, message_hash),
        ).fetchone()
    return row is not None


def delete_ignored(ignore_id: int, project_key: str) -> bool:
    _ensure_migration()
    with _connect(state_db_path()) as c:
        cur = c.execute(
            "DELETE FROM ignored_findings WHERE id = ? AND project_key = ?",
            (ignore_id, project_key),
        )
        return cur.rowcount > 0


# ---------------- file hashes ----------------

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