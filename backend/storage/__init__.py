"""Storage package for AI Code Guardian.

Public surface:
- db.py         -> paths, schema init, retention cleanup, time helpers
- scans.py      -> scan-results CRUD (auto-expiring DB)
- persistent.py -> ignore list + file hashes (never auto-deleted)

Consumers should import submodules directly, e.g.:
    from backend.storage.scans import save_scan, get_scan
"""
from backend.storage.db import (
    SCAN_RETENTION_DAYS,
    init_db,
    cleanup_expired_scans,
    scans_db_path,
    state_db_path,
    utcnow_iso,
    expiry_iso,
)

__all__ = [
    "SCAN_RETENTION_DAYS",
    "init_db",
    "cleanup_expired_scans",
    "scans_db_path",
    "state_db_path",
    "utcnow_iso",
    "expiry_iso",
]