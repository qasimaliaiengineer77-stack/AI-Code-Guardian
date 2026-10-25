"""Ignore list + file hashes — NEVER auto-deleted (Rule 7)."""
from __future__ import annotations

import hashlib
import logging
import threading
from typing import Optional

from backend.storage.db import _connect, scans_db_path, state_db_path, utcnow_iso


# ---------------- utilities ----------------

def message_hash(msg: str) -> str:
    """SHA-256 of a finding's message. Same on add & filter sides."""
    return hashlib.sha256((msg or "").encode("utf-8")).hexdigest()


def compute_project_key_from_pairs(pairs: list, scan_id: str) -> str:
    """Project fingerprint from in-memory (file, sha256) pairs. No DB touch."""
    parts = sorted(set(f"{f}:{h}" for f, h in pairs))
    if not parts:
        return hashlib.sha256((scan_id or "").encode("utf-8")).hexdigest()
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def compute_project_id(
    source: Optional[str],
    source_ref: Optional[str],
    paths: Optional[list] = None,
) -> Optional[str]:
    """Pure helper. Stable project fingerprint for Step 1b.

    GitHub : "gh:owner/repo" (normalized lowercase) — source_ref is the salt.
    Local  : "loc:" + sha256(sorted relative paths)
    Zip    : "zip:" + sha256(sorted relative paths)
    Uncomputable source -> None.
    """
    src = (source or "").strip().lower()
    ref = (source_ref or "").strip()

    if src == "github" and ref:
        return "gh:" + ref.lower()

    prefix = "zip:" if src == "zip" else "loc:"
    if paths:
        clean = sorted(set(str(p).replace("\\", "/") for p in paths if p))
        if clean:
            return prefix + hashlib.sha256("|".join(clean).encode("utf-8")).hexdigest()

    return None


def compute_project_key(scan_id: str) -> str:
    """Content-based fingerprint. Prefers frozen scans.project_key (D5b).
    Falls back to recomputing from file_hashes for legacy scans."""
    _ensure_migration()
    try:
        with _connect(scans_db_path()) as c:
            row = c.execute(
                "SELECT project_key FROM scans WHERE scan_id = ?", (scan_id,)
            ).fetchone()
            if row and row[0]:
                return row[0]
    except Exception:
        pass
    rows = list_file_hashes(scan_id)
    pairs = [(r.get("file", ""), r.get("sha256", "")) for r in rows]
    return compute_project_key_from_pairs(pairs, scan_id)


def compute_project_id_for_scan(scan_id: str) -> Optional[str]:
    """Stable project_id for a given scan_id.

    Prefers frozen scans.project_id. Falls back to (source, source_ref, paths)
    from scans + file_hashes. No code executed, no raw path leaked to callers
    except through the hashed result.
    """
    _ensure_migration()
    source = None
    source_ref = None
    try:
        with _connect(scans_db_path()) as c:
            row = c.execute(
                "SELECT project_id, source, source_ref FROM scans WHERE scan_id = ?",
                (scan_id,),
            ).fetchone()
            if row:
                frozen = row[0]
                if frozen:
                    return frozen
                source = row[1]
                source_ref = row[2]
    except Exception:
        pass

    paths: list = []
    try:
        with _connect(state_db_path()) as c:
            rows = c.execute(
                "SELECT DISTINCT file FROM file_hashes WHERE scan_id = ?",
                (scan_id,),
            ).fetchall()
            paths = [r[0] for r in rows]
    except Exception:
        pass

    return compute_project_id(source, source_ref, paths)


# ---------------- migration (lazy, idempotent) ----------------

_MIGRATION_DONE = False
_MIGRATION_LOCK = threading.Lock()


def _ensure_migration() -> None:
    """Idempotent migrations.
    Block 1: ignored_findings project_key (Rule 7, untouched).
    Block 2: scans.project_key backfill (D5b).
    Block 3: file_hashes rebuild only if project_key missing (D5).
    Block 4: project_id columns + indexes (Step 1b, P1 dual-key)."""
    global _MIGRATION_DONE
    if _MIGRATION_DONE:
        return
    with _MIGRATION_LOCK:
        if _MIGRATION_DONE:
            return
        ok = True
        # --- Block 1: ignored_findings (UNCHANGED, silent pass) ---
        try:
            with _connect(state_db_path()) as c:
                tables = [r[0] for r in c.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()]
                if "ignored_findings" in tables:
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
        except Exception:
            pass
        # --- Block 2: cache file_hashes (before any drop), then scans.project_key ---
        scan_pk_map = {}
        try:
            with _connect(state_db_path()) as sc:
                scan_ids = [r[0] for r in sc.execute(
                    "SELECT DISTINCT scan_id FROM file_hashes"
                ).fetchall()]
                for sid in scan_ids:
                    rows = sc.execute(
                        "SELECT file, sha256 FROM file_hashes WHERE scan_id=?",
                        (sid,),
                    ).fetchall()
                    pairs = [(r[0], r[1]) for r in rows]
                    scan_pk_map[sid] = compute_project_key_from_pairs(pairs, sid)
        except Exception as e:
            logging.warning("migration: cache file_hashes failed: %s", e)
            ok = False
        if ok:
            try:
                with _connect(scans_db_path()) as c:
                    cols = [r[1] for r in c.execute(
                        "PRAGMA table_info(scans)"
                    ).fetchall()]
                    if "project_key" not in cols:
                        c.execute("ALTER TABLE scans ADD COLUMN project_key TEXT")
                    for sid, pk in scan_pk_map.items():
                        c.execute(
                            "UPDATE scans SET project_key=? "
                            "WHERE scan_id=? AND project_key IS NULL",
                            (pk, sid),
                        )
                    c.execute(
                        "CREATE INDEX IF NOT EXISTS idx_scans_project "
                        "ON scans(project_key, created_at DESC)"
                    )
            except Exception as e:
                logging.warning("migration: scans.project_key failed: %s", e)
                ok = False
        # --- Block 3: file_hashes rebuild ONLY if project_key column missing ---
        if ok:
            try:
                with _connect(state_db_path()) as c:
                    cols = [r[1] for r in c.execute(
                        "PRAGMA table_info(file_hashes)"
                    ).fetchall()]
                    if "project_key" not in cols:
                        c.execute("DROP TABLE IF EXISTS file_hashes")
                        c.executescript(
                            """
                            CREATE TABLE file_hashes (
                                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                                scan_id     TEXT NOT NULL,
                                file        TEXT NOT NULL,
                                sha256      TEXT NOT NULL,
                                size_bytes  INTEGER,
                                added_at    TEXT NOT NULL,
                                project_key TEXT NOT NULL
                            );
                            CREATE INDEX idx_hash_scan ON file_hashes(scan_id);
                            CREATE INDEX idx_hash_sha  ON file_hashes(sha256);
                            """
                        )
                    c.execute(
                        "CREATE UNIQUE INDEX IF NOT EXISTS idx_hash_unique "
                        "ON file_hashes(project_key, file)"
                    )
            except Exception as e:
                logging.warning("migration: file_hashes rebuild failed: %s", e)
                ok = False
        # --- Block 4: project_id columns + indexes (Step 1b) ---
        if ok:
            try:
                with _connect(scans_db_path()) as c:
                    cols = [r[1] for r in c.execute(
                        "PRAGMA table_info(scans)"
                    ).fetchall()]
                    if "project_id" not in cols:
                        c.execute("ALTER TABLE scans ADD COLUMN project_id TEXT")
                    c.execute(
                        "CREATE INDEX IF NOT EXISTS idx_scans_project_id "
                        "ON scans(project_id, created_at DESC)"
                    )
            except Exception as e:
                logging.warning("migration: scans.project_id failed: %s", e)
                ok = False
        if ok:
            try:
                with _connect(state_db_path()) as c:
                    cols = [r[1] for r in c.execute(
                        "PRAGMA table_info(file_hashes)"
                    ).fetchall()]
                    if "project_id" not in cols:
                        c.execute("ALTER TABLE file_hashes ADD COLUMN project_id TEXT")
                    c.execute(
                        "CREATE INDEX IF NOT EXISTS idx_hash_project_file "
                        "ON file_hashes(project_id, file)"
                    )

                    cols_ig = [r[1] for r in c.execute(
                        "PRAGMA table_info(ignored_findings)"
                    ).fetchall()]
                    if "project_id" not in cols_ig:
                        c.execute("ALTER TABLE ignored_findings ADD COLUMN project_id TEXT")
                    c.execute(
                        "CREATE INDEX IF NOT EXISTS idx_ignored_project_id "
                        "ON ignored_findings(project_id)"
                    )
            except Exception as e:
                logging.warning("migration: state.project_id failed: %s", e)
                ok = False
        if ok:
            _MIGRATION_DONE = True


# ---------------- ignore list (dual-key P1) ----------------

def add_ignored(
    *,
    project_key: str,
    project_id: Optional[str] = None,
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
                (scan_id, project_key, project_id, file, rule_id, line, message_hash, added_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_key, project_key, project_id,
                file, rule_id, line, message_hash, utcnow_iso(),
            ),
        )


def list_ignored(
    project_key: Optional[str] = None,
    project_id: Optional[str] = None,
) -> list[dict]:
    _ensure_migration()
    with _connect(state_db_path()) as c:
        if project_id:
            rows = c.execute(
                "SELECT id, file, rule_id, line, message_hash, added_at "
                "FROM ignored_findings WHERE (project_id = ? OR project_key = ?) "
                "ORDER BY added_at DESC",
                (project_id, project_key),
            ).fetchall()
        elif project_key:
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
    project_id: Optional[str] = None,
    file: str,
    rule_id: str,
    line: Optional[int],
    message_hash: str,
) -> bool:
    _ensure_migration()
    with _connect(state_db_path()) as c:
        if project_id:
            row = c.execute(
                """
                SELECT 1 FROM ignored_findings
                WHERE (project_id = ? OR project_key = ?)
                  AND file = ? AND rule_id = ?
                  AND line IS ? AND message_hash = ?
                LIMIT 1
                """,
                (project_id, project_key, file, rule_id, line, message_hash),
            ).fetchone()
        else:
            row = c.execute(
                """
                SELECT 1 FROM ignored_findings
                WHERE project_key = ?
                  AND file = ? AND rule_id = ?
                  AND line IS ? AND message_hash = ?
                LIMIT 1
                """,
                (project_key, file, rule_id, line, message_hash),
            ).fetchone()
    return row is not None


def delete_ignored(
    ignore_id: int,
    project_key: Optional[str] = None,
    project_id: Optional[str] = None,
) -> bool:
    with _connect(state_db_path()) as c:
        if project_id:
            cur = c.execute(
                "DELETE FROM ignored_findings "
                "WHERE id = ? AND (project_id = ? OR project_key = ?)",
                (ignore_id, project_id, project_key),
            )
        elif project_key:
            cur = c.execute(
                "DELETE FROM ignored_findings WHERE id = ? AND project_key = ?",
                (ignore_id, project_key),
            )
        else:
            return False
        return cur.rowcount > 0


# ---------------- file hashes (dual-key P1) ----------------

def save_file_hash(
    *,
    scan_id: str,
    file: str,
    sha256: str,
    size_bytes: Optional[int],
    project_key: str,
    project_id: Optional[str] = None,
) -> None:
    _ensure_migration()
    with _connect(state_db_path()) as c:
        c.execute(
            """
            INSERT INTO file_hashes
                (scan_id, file, sha256, size_bytes, project_key, project_id, added_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_key, file) DO UPDATE SET
                scan_id    = excluded.scan_id,
                sha256     = excluded.sha256,
                size_bytes = excluded.size_bytes,
                project_id = COALESCE(excluded.project_id, file_hashes.project_id),
                added_at   = excluded.added_at
            """,
            (
                scan_id, file, sha256, size_bytes,
                project_key, project_id, utcnow_iso(),
            ),
        )


def list_file_hashes(scan_id: Optional[str] = None) -> list[dict]:
    with _connect(state_db_path()) as c:
        if scan_id:
            rows = c.execute(
                "SELECT * FROM file_hashes WHERE scan_id = ? ORDER BY file",
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM file_hashes ORDER BY added_at DESC"
            ).fetchall()
    return [dict(r) for r in rows]