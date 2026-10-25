"""Chunked batching helpers — Phase 2 STEP F2.

Pure helpers only — no I/O, no process launches, no network, no dynamic execution.
Only os.walk / os.path.getsize (same stat-style as resources.count_workspace).
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

_DEFAULT_MODE_FILES = 2000
_DEFAULT_MODE_BYTES = 100 * 1024 * 1024
_DEFAULT_CHUNK_FILES = 500
_DEFAULT_CHUNK_BYTES = 20 * 1024 * 1024


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        v = int(str(raw).strip())
        if v > 0:
            return v
    except (TypeError, ValueError):
        pass
    return default


def chunk_thresholds() -> Dict[str, int]:
    return {
        "mode_files": _env_int("GUARDIAN_CHUNK_MODE_FILES", _DEFAULT_MODE_FILES),
        "mode_bytes": _env_int("GUARDIAN_CHUNK_MODE_BYTES", _DEFAULT_MODE_BYTES),
        "chunk_files": _env_int("GUARDIAN_CHUNK_FILES", _DEFAULT_CHUNK_FILES),
        "chunk_bytes": _env_int("GUARDIAN_CHUNK_BYTES", _DEFAULT_CHUNK_BYTES),
    }


def should_chunk(file_count: int, total_bytes: int) -> bool:
    try:
        fc = int(file_count or 0)
        tb = int(total_bytes or 0)
    except (TypeError, ValueError):
        return False
    t = chunk_thresholds()
    return fc > t["mode_files"] or tb > t["mode_bytes"]


def collect_python_files(target: str) -> List[str]:
    """Walk target, return sorted absolute paths of .py files."""
    out: List[str] = []
    try:
        target_p = Path(target)
        if not target_p.is_dir():
            return out
        for root, _dirs, files in os.walk(target_p):
            for name in files:
                if name.endswith(".py"):
                    out.append(str(Path(root) / name))
    except OSError:
        return []
    out.sort()
    return out


def plan_chunks(
    files: Sequence[str],
    chunk_files: int,
    chunk_bytes: int,
) -> List[List[str]]:
    """Split files into chunks (path lists only — no copy)."""
    chunks: List[List[str]] = []
    cur: List[str] = []
    cur_bytes = 0
    try:
        cf = max(1, int(chunk_files))
        cb = max(1, int(chunk_bytes))
    except (TypeError, ValueError):
        cf, cb = _DEFAULT_CHUNK_FILES, _DEFAULT_CHUNK_BYTES
    for p in files:
        try:
            sz = os.path.getsize(p)
        except OSError:
            sz = 0
        if cur and (len(cur) >= cf or (cur_bytes + sz) > cb):
            chunks.append(cur)
            cur = []
            cur_bytes = 0
        cur.append(p)
        cur_bytes += sz
    if cur:
        chunks.append(cur)
    return chunks


def maybe_plan(
    target: str,
    file_count: int,
    total_bytes: int,
) -> Optional[List[List[str]]]:
    """Return None if chunking not needed, else list of chunks."""
    if not should_chunk(file_count, total_bytes):
        return None
    files = collect_python_files(target)
    if len(files) < 2:
        return None
    t = chunk_thresholds()
    chunks = plan_chunks(files, t["chunk_files"], t["chunk_bytes"])
    if len(chunks) < 2:
        return None
    return chunks


def merge_issues(
    issue_lists: Sequence[Sequence[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Dedupe by (file, rule_id, line, scanner), stable sort."""
    seen = set()
    out: List[Dict[str, Any]] = []
    for issues in issue_lists:
        for it in issues:
            if not isinstance(it, dict):
                continue
            try:
                line = int(it.get("line", 0) or 0)
            except (TypeError, ValueError):
                line = 0
            key = (
                str(it.get("file", "")),
                str(it.get("rule_id", "")),
                line,
                str(it.get("scanner", "")),
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(it)
    out.sort(
        key=lambda x: (
            str(x.get("file", "")),
            int(x.get("line", 0) or 0),
            str(x.get("rule_id", "")),
        )
    )
    return out