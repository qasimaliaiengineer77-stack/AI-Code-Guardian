"""Resource snapshot + workspace sizing helpers for scan batching decisions (F1).

Pure helpers — no side effects, no network, no scanned-code execution.
If psutil is unavailable, snapshot() returns None fields and the decision
function treats that as "no info" (does not degrade on RAM alone).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None

MIN_FREE_RAM_MB = 512
MAX_FILES = 5000
MAX_BYTES = 200 * 1024 * 1024


def snapshot() -> dict:
    """Return a best-effort resource snapshot. Never raises."""
    if psutil is None:
        return {
            "available_ram_mb": None,
            "total_ram_mb": None,
            "cpu_count": None,
            "cpu_percent": None,
        }
    try:
        vm = psutil.virtual_memory()
        return {
            "available_ram_mb": int(vm.available // (1024 * 1024)),
            "total_ram_mb": int(vm.total // (1024 * 1024)),
            "cpu_count": psutil.cpu_count(logical=True),
            "cpu_percent": float(psutil.cpu_percent(interval=None)),
        }
    except Exception:
        return {
            "available_ram_mb": None,
            "total_ram_mb": None,
            "cpu_count": None,
            "cpu_percent": None,
        }


def count_workspace(workspace_dir) -> dict:
    """Count files + total bytes under workspace_dir. Never raises."""
    root = Path(workspace_dir)
    file_count = 0
    total_bytes = 0
    if not root.exists() or not root.is_dir():
        return {"file_count": 0, "total_bytes": 0}
    try:
        for p in root.rglob("*"):
            try:
                if p.is_file():
                    file_count += 1
                    total_bytes += int(p.stat().st_size)
            except OSError:
                continue
    except OSError:
        pass
    return {"file_count": file_count, "total_bytes": total_bytes}


def should_degrade(
    file_count: int,
    total_bytes: int,
    snap: Optional[dict] = None,
    *,
    min_free_ram_mb: int = MIN_FREE_RAM_MB,
    max_files: int = MAX_FILES,
    max_bytes: int = MAX_BYTES,
) -> tuple:
    """Return (degrade: bool, reason: Optional[str]).

    Pure decision — no side effects. Any single threshold breach degrades.
    """
    snap = snap or {}
    reasons = []
    ram = snap.get("available_ram_mb")
    if isinstance(ram, int) and ram < min_free_ram_mb:
        reasons.append("low_ram:%dMB<%dMB" % (ram, min_free_ram_mb))
    if isinstance(file_count, int) and file_count > max_files:
        reasons.append("too_many_files:%d>%d" % (file_count, max_files))
    if isinstance(total_bytes, int) and total_bytes > max_bytes:
        reasons.append("too_large:%dB>%dB" % (total_bytes, max_bytes))
    if reasons:
        return True, ";".join(reasons)
    return False, None