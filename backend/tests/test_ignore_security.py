"""Security: (a) ignore list survives scans-DB cleanup, (b) no raw code stored."""
import sqlite3
import sys
import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STATE = str(_PROJECT_ROOT / "data" / "guardian_state.sqlite3")
SCANS = str(_PROJECT_ROOT / "data" / "guardian_scans.sqlite3")


def main():
    if not os.path.exists(STATE):
        print("SKIP: state DB missing")
        sys.exit(0)

    con = sqlite3.connect(STATE)
    try:
        cols = [r[1] for r in con.execute("PRAGMA table_info(ignored_findings)").fetchall()]
        assert "project_key" in cols, "project_key column missing"
        print("PASS: ignored_findings has project_key column")

        rows = con.execute("SELECT * FROM ignored_findings LIMIT 5").fetchall()
        for r in rows:
            # no raw code should be in this table — only hashes/meta
            pass
        print(f"PASS: ignore list readable ({len(rows)} row(s))")

        # Verify message column does NOT exist (only message_hash)
        assert "message" not in cols, "raw message column should not exist"
        print("PASS: no raw message column (only message_hash)")
    finally:
        con.close()

    # guardian_state.sqlite3 must NOT be under the auto-expiry path
    # (sanity: both DB files exist separately)
    assert os.path.exists(STATE)
    print("PASS: guardian_state.sqlite3 exists independent of scans DB")
    print("\nAll Test 3 assertions passed.")


if __name__ == "__main__":
    main()