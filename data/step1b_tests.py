"""Step 1b tests — T1, T2, T3. Run: python data/step1b_tests.py test1|test2|test3"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import hashlib  # noqa: E402

from backend.core.config import WORKSPACE_DIR  # noqa: E402
from backend.orchestrator.runner import run_scan  # noqa: E402
from backend.storage.db import _connect, scans_db_path, state_db_path  # noqa: E402
from backend.storage.persistent import (  # noqa: E402
    add_ignored,
    compute_project_key,
    message_hash,
)


def _new_scan_id(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()[:32]


def _prep_workspace(scan_id: str, files: dict) -> Path:
    target = Path(WORKSPACE_DIR) / scan_id
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        p = target / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return target


def _cleanup(scan_id: str) -> None:
    """Delete workspace + scan row + file_hashes + ignored_findings for this scan's project_ids."""
    d = Path(WORKSPACE_DIR) / scan_id
    if d.exists():
        shutil.rmtree(d)

    # Read project_ids BEFORE deleting file_hashes — used to purge ignores created by test
    pids = set()
    try:
        with _connect(state_db_path()) as c:
            rows = c.execute(
                "SELECT DISTINCT project_id FROM file_hashes "
                "WHERE scan_id = ? AND project_id IS NOT NULL",
                (scan_id,),
            ).fetchall()
            pids = {r[0] for r in rows}
    except Exception:
        pass

    try:
        with _connect(scans_db_path()) as c:
            c.execute("DELETE FROM scans WHERE scan_id = ?", (scan_id,))
    except Exception:
        pass

    try:
        with _connect(state_db_path()) as c:
            c.execute("DELETE FROM file_hashes WHERE scan_id = ?", (scan_id,))
            for pid in pids:
                c.execute("DELETE FROM ignored_findings WHERE project_id = ?", (pid,))
    except Exception:
        pass


def test1():
    """T1a: prev non-OSV skip -> full.
    T1b: unchanged file's High carries forward -> gate FAIL (no false PASS).
    T1c: options mismatch (security/quality) -> full scan."""
    print("=== T1 ===")
    fileA = (
        "import subprocess\n"
        "def run(cmd):\n"
        "    subprocess.Popen(cmd, shell=True)\n"
    )
    fileB_v1 = "X = 1\n"
    fileB_v2 = "X = 2\n"

    # --- T1a: previous partial (non-OSV skip via quality=False) ---
    sid1a = _new_scan_id("t1a-a")
    sid2a = _new_scan_id("t1a-b")
    try:
        _prep_workspace(sid1a, {"a.py": fileA, "b.py": fileB_v1})
        r1a = run_scan(sid1a, explain=False, dependencies=False, quality=False, retention_days=1)
        s1a = r1a.get("skipped_scanners") or []
        blocking = [s for s in s1a if s != "osv"]
        print(f"  T1a scan1 skipped_scanners={s1a} blocking={blocking}")
        assert blocking, f"T1a needs non-OSV skip; got {s1a}"

        _prep_workspace(sid2a, {"a.py": fileA, "b.py": fileB_v2})
        r2a = run_scan(sid2a, explain=False, dependencies=False, quality=False, retention_days=1)
        inc2a = r2a.get("incremental") or {}
        print(f"  T1a scan2 incremental.enabled={inc2a.get('enabled')} reason={inc2a.get('reason')}")
        assert inc2a.get("enabled") is False, f"T1a: should be full (prev partial), got {inc2a}"
        assert inc2a.get("reason") == "previous_partial", f"T1a: reason should be previous_partial, got {inc2a}"
        highs2a = [i for i in (r2a.get("issues") or []) if (i.get("severity") or "").lower() == "high"]
        print(f"  T1a scan2 highs={len(highs2a)}")
        assert len(highs2a) >= 1, f"T1a: full scan should find High"
        print("  T1a PASS")
    finally:
        _cleanup(sid1a)
        _cleanup(sid2a)

    # --- T1b: incremental + carry-forward (OSV exempt) ---
    sid1b = _new_scan_id("t1b-a")
    sid2b = _new_scan_id("t1b-b")
    try:
        _prep_workspace(sid1b, {"a.py": fileA, "b.py": fileB_v1})
        r1b = run_scan(sid1b, explain=False, dependencies=False, retention_days=1)
        s1b = r1b.get("skipped_scanners") or []
        blocking = [s for s in s1b if s != "osv"]
        print(f"  T1b scan1 skipped_scanners={s1b} blocking={blocking}")
        assert not blocking, f"T1b: scan1 must be clean (only OSV allowed), got {s1b}"

        _prep_workspace(sid2b, {"a.py": fileA, "b.py": fileB_v2})
        r2b = run_scan(sid2b, explain=False, dependencies=False, retention_days=1)
        inc2b = r2b.get("incremental") or {}
        issues2b = r2b.get("issues") or []
        highs2b = [i for i in issues2b if (i.get("severity") or "").lower() == "high"]
        print(
            f"  T1b scan2 incremental.enabled={inc2b.get('enabled')} "
            f"unchanged={inc2b.get('unchanged_count')} changed={inc2b.get('changed_count')} "
            f"carried={inc2b.get('carried_forward_count')} highs={len(highs2b)}"
        )
        assert inc2b.get("enabled") is True, f"T1b: should be incremental, got {inc2b}"
        assert (inc2b.get("carried_forward_count") or 0) >= 1, f"T1b: carry-forward missing"
        assert len(highs2b) >= 1, f"T1b: High from unchanged file must appear in scan2"

        from backend.api.scans import gate_scan
        g2b = gate_scan(sid2b)
        print(f"  T1b gate={g2b}")
        assert g2b.get("passed") is False, f"T1b: gate must FAIL, got {g2b}"
        print("  T1b PASS")
    finally:
        _cleanup(sid1b)
        _cleanup(sid2b)

    # --- T1c: options mismatch (security/quality) ---
    sid1c = _new_scan_id("t1c-a")
    sid2c = _new_scan_id("t1c-b")
    try:
        _prep_workspace(sid1c, {"a.py": fileA, "b.py": fileB_v1})
        r1c = run_scan(sid1c, explain=False, dependencies=False, security=True, quality=True, retention_days=1)
        s1c = r1c.get("skipped_scanners") or []
        blocking = [s for s in s1c if s != "osv"]
        print(f"  T1c scan1 skipped_scanners={s1c} blocking={blocking}")
        assert not blocking, f"T1c: scan1 must be clean, got {s1c}"

        _prep_workspace(sid2c, {"a.py": fileA, "b.py": fileB_v2})
        r2c = run_scan(sid2c, explain=False, dependencies=False, security=True, quality=False, retention_days=1)
        inc2c = r2c.get("incremental") or {}
        print(f"  T1c scan2 (quality=False) incremental.enabled={inc2c.get('enabled')} reason={inc2c.get('reason')}")
        assert inc2c.get("enabled") is False, f"T1c: should be full (options mismatch), got {inc2c}"
        assert inc2c.get("reason") == "options_mismatch", f"T1c: reason should be options_mismatch, got {inc2c}"
        print("  T1c PASS")
    finally:
        _cleanup(sid1c)
        _cleanup(sid2c)


def test2():
    """T2: gitleaks full workspace in incremental scan (unchanged secret re-detected, no duplicate carry)."""
    print("=== T2 ===")
    sid1 = _new_scan_id("t2-a")
    sid2 = _new_scan_id("t2-b")
    secret_block = 'GITHUB_TOKEN = "ghp_aB3xK9mN2pQ7rT5vW8yZ1cF4hJ6kL0sD3gH"\n'
    fileA1 = "X = 1\n"
    fileA2 = "X = 2\n"
    try:
        _prep_workspace(sid1, {"a.py": fileA1, "leak.py": secret_block})
        r1 = run_scan(sid1, explain=False, dependencies=False, retention_days=1)
        g1 = (r1.get("scanners") or {}).get("gitleaks") or {}
        leak1 = [i for i in (r1.get("issues") or []) if (i.get("scanner") or "") == "gitleaks"]
        print(f"  scan1 gitleaks.ok={g1.get('ok')} findings={len(leak1)}")
        assert g1.get("ok") is True, f"gitleaks not ok in scan1: {g1}"
        assert len(leak1) == 1, f"gitleaks should find exactly 1 secret in scan1, got {len(leak1)}"

        _prep_workspace(sid2, {"a.py": fileA2, "leak.py": secret_block})
        r2 = run_scan(sid2, explain=False, dependencies=False, retention_days=1)
        g2 = (r2.get("scanners") or {}).get("gitleaks") or {}
        leak2 = [i for i in (r2.get("issues") or []) if (i.get("scanner") or "") == "gitleaks"]
        inc2 = r2.get("incremental") or {}
        print(f"  scan2 incremental={inc2.get('enabled')} gitleaks.ok={g2.get('ok')} findings={len(leak2)}")
        assert g2.get("ok") is True, f"gitleaks not ok in scan2"
        assert len(leak2) == 1, f"gitleaks should find exactly 1 secret in scan2 (no duplicate carry), got {len(leak2)}"
        print("  T2 PASS (gitleaks full-workspace verified, no duplicate)")
    finally:
        _cleanup(sid1)
        _cleanup(sid2)


def test3():
    """T3: ignore survives file content change (stable project_id)."""
    print("=== T3 ===")
    sid1 = _new_scan_id("t3-a")
    sid2 = _new_scan_id("t3-b")
    fileA_v1 = "def f(x):\n    assert x > 0\n    return x\n"
    fileA_v2 = fileA_v1 + "\n# trailing comment\n"
    try:
        _prep_workspace(sid1, {"a.py": fileA_v1})
        r1 = run_scan(sid1, explain=False, dependencies=False, retention_days=1)
        issues1 = r1.get("issues") or []
        target = next(
            (i for i in issues1 if (i.get("scanner") or "") == "bandit"),
            None,
        )
        assert target is not None, "no bandit issue in scan1"
        pid1 = (r1.get("incremental") or {}).get("project_id")
        print(f"  scan1 pid={pid1} file={target.get('file')} line={target.get('line')} rule={target.get('rule_id')}")

        pk1 = compute_project_key(sid1)
        add_ignored(
            project_key=pk1,
            project_id=pid1,
            file=target.get("file") or "",
            rule_id=target.get("rule_id") or "",
            line=target.get("line"),
            message_hash=message_hash(target.get("message") or ""),
        )

        _prep_workspace(sid2, {"a.py": fileA_v2})
        r2 = run_scan(sid2, explain=False, dependencies=False, retention_days=1)
        inc2 = r2.get("incremental") or {}
        pid2 = inc2.get("project_id")
        same = [
            i for i in (r2.get("issues") or [])
            if (i.get("scanner") or "") == "bandit"
            and (i.get("file") or "") == (target.get("file") or "")
        ]
        print(f"  scan2 pid={pid2} pid_same={pid1 == pid2} bandit_on_file={len(same)}")
        assert pid1 == pid2, f"project_id must be stable: {pid1} vs {pid2}"
        assert len(same) == 0, f"ignore must filter bandit issue after edit; got {len(same)}"
        print("  T3 PASS")
    finally:
        _cleanup(sid1)
        _cleanup(sid2)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    if which == "test1":
        test1()
    elif which == "test2":
        test2()
    elif which == "test3":
        test3()
    else:
        print("usage: python data/step1b_tests.py test1|test2|test3")