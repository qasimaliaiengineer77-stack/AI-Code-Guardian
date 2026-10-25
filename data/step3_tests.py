"""Step 3 tests — Lizard complexity scanner (gitignored via data/ rule)."""
import re
import shutil
import sys
import uuid
from pathlib import Path

# Ensure project root is importable when running: python data/step3_tests.py
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.core.config import WORKSPACE_DIR
from backend.orchestrator.runner import run_scan
from backend.storage.db import _connect, scans_db_path, state_db_path


# ---------------- helpers ----------------

def _new_scan_id():
    return uuid.uuid4().hex  # 32 lowercase hex chars


def _prep_workspace(sid, files):
    """files: dict {relative_path: content}. Creates fresh workspace/<sid>/."""
    root = Path(WORKSPACE_DIR) / sid
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return root


def _cleanup(sid):
    """Delete scan row + hashes/ignores by project_id + workspace dir."""
    pid = None
    try:
        with _connect(scans_db_path()) as c:
            row = c.execute(
                "SELECT project_id FROM scans WHERE scan_id = ?", (sid,)
            ).fetchone()
            if row:
                pid = row[0]
            c.execute("DELETE FROM scans WHERE scan_id = ?", (sid,))
            c.commit()
    except Exception:
        pass
    if pid:
        try:
            with _connect(state_db_path()) as c:
                c.execute("DELETE FROM file_hashes WHERE project_id = ?", (pid,))
                c.execute("DELETE FROM ignored_findings WHERE project_id = ?", (pid,))
                c.commit()
        except Exception:
            pass
    root = Path(WORKSPACE_DIR) / sid
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)


def _lizard_issues(result):
    return [i for i in (result.get("issues") or []) if i.get("scanner") == "lizard"]


def _ccn_from_message(msg):
    """Extract CCN from 'X has cyclomatic complexity N (...)'.
    redaction whitelist drops the custom 'ccn' key, so parse from message."""
    m = re.search(r"cyclomatic complexity (\d+)", msg or "")
    return int(m.group(1)) if m else None


# ---------------- fixtures ----------------

SIMPLE_FILE = """
def add(a, b):
    return a + b

def greet(name):
    return "Hello " + name
"""

# CCN = 1 + 12 ifs = 13 -> MEDIUM (10 < ccn <= 15)
MEDIUM_FILE = (
    "def medium_function(x):\n"
    + "\n".join("    if x == %d: return %d" % (i, i) for i in range(1, 13))
    + "\n    return 0\n"
)

# CCN = 1 + 19 ifs = 20 -> HIGH (ccn > 15)
HIGH_FILE = (
    "def big_function(x):\n"
    + "\n".join("    if x == %d: return %d" % (i, i) for i in range(1, 20))
    + "\n    return 0\n"
)


# ---------------- tests ----------------

def t1():
    print("=== T1: low complexity -> 0 lizard findings ===")
    sid = _new_scan_id()
    try:
        _prep_workspace(sid, {"simple.py": SIMPLE_FILE})
        r = run_scan(sid, explain=False, dependencies=False, retention_days=1)
        liz = _lizard_issues(r)
        sc = (r.get("scanners") or {}).get("lizard") or {}
        print(f"  scanners.lizard.ok={sc.get('ok')} total={sc.get('total_issues')}")
        print(f"  lizard issues in result: {len(liz)}")
        assert sc.get("ok") is True, f"lizard scanner not ok: {sc}"
        assert len(liz) == 0, f"expected 0 lizard issues, got {len(liz)}: {liz}"
        print("  T1 PASS")
    finally:
        _cleanup(sid)


def t2():
    print("=== T2: high + medium CCN detected with correct severity ===")
    sid = _new_scan_id()
    try:
        _prep_workspace(sid, {"high.py": HIGH_FILE, "medium.py": MEDIUM_FILE})
        r = run_scan(sid, explain=False, dependencies=False, retention_days=1)
        liz = _lizard_issues(r)
        for i in liz:
            print(
                f"    {i.get('file')}:{i.get('line')} "
                f"ccn={_ccn_from_message(i.get('message'))} "
                f"sev={i.get('severity')} rule={i.get('rule_id')}"
            )
        highs = [i for i in liz if i.get("severity") == "HIGH"]
        mediums = [i for i in liz if i.get("severity") == "MEDIUM"]
        assert len(highs) >= 1, f"expected >=1 HIGH, got {len(highs)}"
        assert len(mediums) >= 1, f"expected >=1 MEDIUM, got {len(mediums)}"
        assert all(i.get("rule_id") == "CCN" for i in liz), "rule_id must be CCN"
        assert all(i.get("scanner") == "lizard" for i in liz), "scanner must be lizard"
        for h in highs:
            ccn_h = _ccn_from_message(h.get("message"))
            assert ccn_h is not None and ccn_h > 15, f"HIGH ccn must be >15, got {ccn_h}"
        for m in mediums:
            ccn_m = _ccn_from_message(m.get("message"))
            assert ccn_m is not None and 10 < ccn_m <= 15, f"MEDIUM ccn must be 11-15, got {ccn_m}"
        for i in liz:
            msg = i.get("message", "")
            assert "cyclomatic complexity" in msg, f"message format bad: {msg}"
        print(f"  HIGH={len(highs)} MEDIUM={len(mediums)}")
        print("  T2 PASS")
    finally:
        _cleanup(sid)


def t3():
    print("=== T3: incremental on, lizard always-full, no duplication ===")
    sid1 = _new_scan_id()
    sid2 = _new_scan_id()
    try:
        files = {"big.py": HIGH_FILE}
        _prep_workspace(sid1, files)
        r1 = run_scan(sid1, explain=False, dependencies=False, retention_days=1)
        liz1 = _lizard_issues(r1)
        pid1 = (r1.get("incremental") or {}).get("project_id")
        print(f"  scan1 lizard count={len(liz1)}")
        assert len(liz1) >= 1, "scan1 should have at least 1 lizard issue"
        sev1 = {i.get("severity") for i in liz1}
        assert "HIGH" in sev1, f"expected HIGH in scan1, got {sev1}"

        _prep_workspace(sid2, files)
        r2 = run_scan(sid2, explain=False, dependencies=False, retention_days=1)
        inc2 = r2.get("incremental") or {}
        liz2 = _lizard_issues(r2)
        pid2 = inc2.get("project_id")
        print(
            f"  scan2 incremental.enabled={inc2.get('enabled')} "
            f"unchanged={inc2.get('unchanged_count')} "
            f"carried={inc2.get('carried_forward_count')} "
            f"pid_same={pid1 == pid2}"
        )
        print(f"  scan2 lizard count={len(liz2)}")

        assert inc2.get("enabled") is True, f"T3: incremental should be ON, got {inc2}"
        assert len(liz2) == len(liz1), (
            f"T3: lizard issues count changed (duplication or loss): "
            f"{len(liz1)} -> {len(liz2)}"
        )
        # Lizard is NOT in _INCREMENTAL_SCANNERS, so it never carries.
        # If it carried (bug), count above would be 2x. Match proves no dup.

        try:
            from backend.api.scans import gate_scan
            g2 = gate_scan(sid2)
            print(f"  scan2 gate passed={g2.get('passed')} (HIGH severity typically FAIL)")
        except Exception as e:
            print(f"  gate_scan skipped: {type(e).__name__}: {e}")

        print("  T3 PASS")
    finally:
        _cleanup(sid1)
        _cleanup(sid2)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    if which == "t1":
        t1()
    elif which == "t2":
        t2()
    elif which == "t3":
        t3()
    else:
        print("usage: python data/step3_tests.py t1|t2|t3")