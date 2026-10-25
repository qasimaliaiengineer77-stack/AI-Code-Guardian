"""Setup: Insert a dummy 'done' scan with an issue so test_ignore_list can run."""
import sys
import os

# Fix path to import 'backend' properly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.storage.scans import save_scan
from backend.storage.db import init_db

def main():
    init_db()
    scan_id = "1234567890abcdef1234567890abcdef"
    result = {
        "scan_id": scan_id,
        "status": "done",
        "finished_at": "2026-10-19T00:00:00Z",
        "scanners": {},
        "total_issues": 1,
        "by_severity": {"LOW": 1},
        "issues": [
            {
                "file": "dummy_test.py",
                "rule_id": "B101",
                "rule_name": "assert_used",
                "line": 1,
                "message": "Use of assert detected.",
                "severity": "LOW",
                "scanner": "bandit",
                "explanation": "Dummy issue for testing ignore list."
            }
        ],
        "ai_status": "ok",
        "options": {}
    }
    save_scan(scan_id, source="local", source_ref=scan_id, status="done", result=result)
    print("PASS: Dummy scan inserted successfully ->", scan_id)

if __name__ == "__main__":
    main()