"""SQLite setup for AI Code Guardian.

Two databases (Rule 7):
  - guardian_scans.sqlite3 -> scan results, auto-deleted after SCAN_RETENTION_DAYS
  - guardian_state.sqlite3 -> ignore list + file hashes, NEVER auto-deleted

Only parameterized SQL is used. Nothing in a scanned repo is executed.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from backend.core.config import DATA_DIR

SCAN_RETENTION_DAYS = 2  # Rule 7: 1-2 din mein auto-delete

SCANS_DB_NAME = "guardian_scans.sqlite3"
STATE_DB_NAME = "guardian_state.sqlite3"


def scans_db_path() -> Path:
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
    return Path(DATA_DIR) / SCANS_DB_NAME


def state_db_path() -> Path:
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
    return Path(DATA_DIR) / STATE_DB_NAME


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def expiry_iso(days: int = SCAN_RETENTION_DAYS) -> str:
    return (
        datetime.now(timezone.utc) + timedelta(days=days)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")


@contextmanager
def _connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


_SCANS_SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    scan_id       TEXT PRIMARY KEY,
    created_at    TEXT NOT NULL,
    expires_at    TEXT NOT NULL,
    source        TEXT,
    source_ref    TEXT,
    status        TEXT NOT NULL,
    result_json   TEXT,
    error_message TEXT,
    project_key   TEXT,
    project_id    TEXT
);
CREATE INDEX IF NOT EXISTS idx_scans_expires ON scans(expires_at);
CREATE INDEX IF NOT EXISTS idx_scans_created ON scans(created_at DESC);
"""

_STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS ignored_findings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id      TEXT NOT NULL,
    file         TEXT NOT NULL,
    rule_id      TEXT NOT NULL,
    line         INTEGER,
    message_hash TEXT NOT NULL,
    added_at     TEXT NOT NULL,
    project_id   TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ignored_unique
    ON ignored_findings(scan_id, file, rule_id, line, message_hash);
CREATE TABLE IF NOT EXISTS file_hashes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id     TEXT NOT NULL,
    file        TEXT NOT NULL,
    sha256      TEXT NOT NULL,
    size_bytes  INTEGER,
    added_at    TEXT NOT NULL,
    project_key TEXT NOT NULL,
    project_id  TEXT
);
CREATE INDEX IF NOT EXISTS idx_hash_scan ON file_hashes(scan_id);
CREATE INDEX IF NOT EXISTS idx_hash_sha  ON file_hashes(sha256);
"""


def init_db() -> None:
    """Idempotent: create both DBs and all tables if missing."""
    with _connect(scans_db_path()) as c:
        c.executescript(_SCANS_SCHEMA)
    with _connect(state_db_path()) as c:
        c.executescript(_STATE_SCHEMA)


def cleanup_expired_scans() -> int:
    """Delete expired scan rows. Returns number removed. Never touches state DB."""
    with _connect(scans_db_path()) as c:
        cur = c.execute("DELETE FROM scans WHERE expires_at < ?", (utcnow_iso(),))
        return cur.rowcount