"""Step 2 tests — T1, T2, T3. Run: python data/step2_tests.py t1|t2|t3"""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import hashlib  # noqa: E402

from backend.core.config import WORKSPACE_DIR  # noqa: E402
from backend.orchestrator.runner import run_scan  # noqa: E402
from backend.storage.db import _connect, scans_db_path, state_db_path  # noqa: E402


# --- 12-line duplicate block (min-similarity-lines=10 triggers R0801) ---
DUPLICATE_BLOCK = (
    "def compute_total(values):\n"
    "    total = 0\n"
    "    count = 0\n"
    "    for v in values:\n"
    "        if v is None:\n"
    "            continue\n"
    "        total += v\n"
    "        count += 1\n"
    "    average = total / count if count else 0\n"
    "    if average > 100:\n"
    "        average = 100\n"
    "    return average\n"
)

_CHUNK_ENV_KEYS = (
    "GUARDIAN_CHUNK_MODE_FILES",
    "GUARDIAN_CHUNK_MODE_BYTES",
    "GUARDIAN_CHUNK_FILES",
    "GUARDIAN_CHUNK_BYTES",
)


def _clear_chunk_env() -> None:
    for k in _CHUNK_ENV_KEYS:
        os.environ.pop(k, None)


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


def _r0801_issues(result: dict) -> list:
    return [
        i for i in (result.get("issues") or [])
        if (i.get("rule_id") or "") == "R0801"
    ]


def t1():
    """T1: normal (no chunk), 2 files with identical 12-line block -> R0801 fires."""
    print("=== T1: normal mode, duplicate code detected ===")
    _clear_chunk_env()
    sid = _new_scan_id("t1-dup")
    files = {
        "a.py": "VERSION = 'a'\n\n" + DUPLICATE_BLOCK,
        "b.py": "VERSION = 'b'\n\n" + DUPLICATE_BLOCK,
    }
    try:
        _prep_workspace(sid, files)
        r = run_scan(sid, explain=False, dependencies=False, retention_days=1)
        chunk = r.get("chunking") or {}
        r0801 = _r0801_issues(r)
        print(f"  chunking.enabled={chunk.get('enabled')} chunk_count={chunk.get('chunk_count')} "
              f"pylint_cross_file_limited={chunk.get('pylint_cross_file_limited')}")
        print(f"  R0801 count={len(r0801)}")
        for i in r0801:
            print(f"    {i.get('rule_id')} | sev={i.get('severity')} | "
                  f"file={i.get('file')} line={i.get('line')}")
        assert chunk.get("enabled") is False, f"T1: chunk must be off, got {chunk}"
        assert len(r0801) >= 1, f"T1: R0801 expected, got 0"
        sevs = {i.get("severity") for i in r0801}
        assert "LOW" in sevs, f"T1: R0801 severity should include LOW, got {sevs}"
        print("  T1 PASS")
    finally:
        _cleanup(sid)


def t2():
    """T2: chunk mode, cross-chunk duplicate (a.py & c.py) caught by dedicated pass."""
    print("=== T2: chunk mode, cross-chunk duplicate caught ===")
    _saved = {}
    for k in _CHUNK_ENV_KEYS:
        _saved[k] = os.environ.pop(k, None)
    os.environ["GUARDIAN_CHUNK_MODE_FILES"] = "2"
    os.environ["GUARDIAN_CHUNK_FILES"] = "1"

    sid = _new_scan_id("t2-chunk")
    files = {
        "a.py": "VERSION = 'a'\n\n" + DUPLICATE_BLOCK,
        "b.py": "VERSION = 'b'\n\n",
        "c.py": "VERSION = 'c'\n\n" + DUPLICATE_BLOCK,
    }
    try:
        _prep_workspace(sid, files)
        r = run_scan(sid, explain=False, dependencies=False, retention_days=1)
        chunk = r.get("chunking") or {}
        r0801 = _r0801_issues(r)
        print(f"  chunking.enabled={chunk.get('enabled')} chunk_count={chunk.get('chunk_count')} "
              f"pylint_cross_file_limited={chunk.get('pylint_cross_file_limited')}")
        print(f"  R0801 count={len(r0801)}")
        for i in r0801:
            print(f"    {i.get('rule_id')} | sev={i.get('severity')} | "
                  f"file={i.get('file')} line={i.get('line')}")
        assert chunk.get("enabled") is True, f"T2: chunk must be on, got {chunk}"
        assert (chunk.get("chunk_count") or 0) >= 2, f"T2: chunk_count must be >=2, got {chunk}"
        assert chunk.get("pylint_cross_file_limited") is False, \
            f"T2: cross_file_limited must be False, got {chunk}"
        assert len(r0801) >= 1, \
            f"T2: R0801 (cross-chunk) expected, got 0 — fix not working?"
        print("  T2 PASS (cross-chunk duplicate caught)")
    finally:
        _cleanup(sid)
        for k, v in _saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def t3():
    """T3: incremental 2nd scan (files unchanged) — R0801 count same (no carry duplication)."""
    print("=== T3: incremental, no R0801 duplication + gate check ===")
    _clear_chunk_env()
    sid1 = _new_scan_id("t3-inc-a")
    sid2 = _new_scan_id("t3-inc-b")
    files = {
        "a.py": "VERSION = 'a'\n\n" + DUPLICATE_BLOCK,
        "b.py": "VERSION = 'b'\n\n" + DUPLICATE_BLOCK,
    }
    try:
        _prep_workspace(sid1, files)
        r1 = run_scan(sid1, explain=False, dependencies=False, retention_days=1)
        r0801_1 = _r0801_issues(r1)
        print(f"  scan1 R0801 count={len(r0801_1)}")
        assert len(r0801_1) >= 1, f"T3: scan1 R0801 expected, got 0"
        pid1 = (r1.get("incremental") or {}).get("project_id")

        # Same files → unchanged → incremental
        _prep_workspace(sid2, files)
        r2 = run_scan(sid2, explain=False, dependencies=False, retention_days=1)
        inc2 = r2.get("incremental") or {}
        r0801_2 = _r0801_issues(r2)
        pid2 = inc2.get("project_id")
        print(f"  scan2 incremental.enabled={inc2.get('enabled')} "
              f"unchanged={inc2.get('unchanged_count')} changed={inc2.get('changed_count')} "
              f"carried={inc2.get('carried_forward_count')} pid_same={pid1 == pid2}")
        print(f"  scan2 R0801 count={len(r0801_2)}")
        assert pid1 == pid2, f"T3: project_id must match: {pid1} vs {pid2}"
        assert inc2.get("enabled") is True, f"T3: should be incremental, got {inc2}"
        assert len(r0801_2) == len(r0801_1), \
            f"T3: R0801 count changed (duplication?): {len(r0801_1)} -> {len(r0801_2)}"

        # Gate (record only — LOW severity shouldn't fail)
        try:
            from backend.api.scans import gate_scan
            g2 = gate_scan(sid2)
            print(f"  scan2 gate passed={g2.get('passed')} (LOW severity: should not force FAIL)")
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
        print("usage: python data/step2_tests.py t1|t2|t3")