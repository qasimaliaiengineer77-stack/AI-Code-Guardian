"""Step 1 manual verification. Raw sqlite3 — no persistent.py import in pre/post."""
import hashlib
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

STATE = "data/guardian_state.sqlite3"
SCANS = "data/guardian_scans.sqlite3"
SID = "aaaabbbbccccddddeeeeffff00001111"


def _rows(db, sql, params=()):
    with sqlite3.connect(db) as c:
        return c.execute(sql, params).fetchall()


def pre():
    rows = _rows(STATE, "SELECT file, sha256 FROM file_hashes WHERE scan_id=?", (SID,))
    parts = sorted(set(f"{f}:{h}" for f, h in rows))
    pk = hashlib.sha256("|".join(parts).encode()).hexdigest() if parts else "EMPTY"
    total = _rows(STATE, "SELECT COUNT(*) FROM file_hashes")[0][0]
    ign = _rows(STATE, "SELECT COUNT(*) FROM ignored_findings")[0][0]
    print(f"PRE_PK={pk}")
    print(f"PRE_TOTAL={total}")
    print(f"PRE_IGNORED={ign}")


def migrate():
    from backend.storage.persistent import _ensure_migration
    _ensure_migration()
    print("MIGRATE_OK")


def post():
    with sqlite3.connect(STATE) as c:
        fh_cols = [r[1] for r in c.execute("PRAGMA table_info(file_hashes)").fetchall()]
        fh_total = c.execute("SELECT COUNT(*) FROM file_hashes").fetchone()[0]
        if "project_key" in fh_cols:
            dup = c.execute(
                "SELECT project_key, file, COUNT(*) FROM file_hashes "
                "GROUP BY project_key, file HAVING COUNT(*)>1"
            ).fetchall()
        else:
            dup = "SKIP (no project_key column)"
    with sqlite3.connect(SCANS) as c:
        s_cols = [r[1] for r in c.execute("PRAGMA table_info(scans)").fetchall()]
        frozen = None
        if "project_key" in s_cols:
            r = c.execute("SELECT project_key FROM scans WHERE scan_id=?", (SID,)).fetchone()
            frozen = r[0] if r else None
    with sqlite3.connect(STATE) as c:
        ign = c.execute("SELECT COUNT(*) FROM ignored_findings").fetchone()[0]
    print(f"HAS_FH_PROJECT_KEY={'project_key' in fh_cols}")
    print(f"HAS_SCANS_PROJECT_KEY={'project_key' in s_cols}")
    print(f"FH_TOTAL={fh_total}")
    print(f"DUP_ROWS={dup}")
    print(f"FROZEN_PK={frozen}")
    print(f"IGNORED={ign}")


def trigger():
    from backend.orchestrator.runner import run_scan
    r = run_scan(SID, explain=False)
    print(f"TRIGGER_ISSUES={len(r.get('issues', []))}")
    print("TRIGGER_OK")


def verify_pk():
    from backend.storage.persistent import compute_project_key
    print(f"PK_NOW={compute_project_key(SID)}")


def sec():
    with sqlite3.connect(STATE) as c:
        fh_cols = [r[1] for r in c.execute("PRAGMA table_info(file_hashes)").fetchall()]
        ig_cols = [r[1] for r in c.execute("PRAGMA table_info(ignored_findings)").fetchall()]
    print(f"FH_COLS={fh_cols}")
    print(f"IG_COLS={ig_cols}")
    forbidden = [c for c in fh_cols if c.lower() in ("content", "body", "text", "code")]
    print(f"FORBIDDEN_FH_COLS={forbidden}")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "pre"
    {"pre": pre, "post": post, "migrate": migrate, "trigger": trigger, "verify_pk": verify_pk, "sec": sec}[action]()