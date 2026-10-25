"""Verify _DOWNLOAD_SEMAPHORE caps concurrent GitHub downloads at 2.

Run: python backend\\tests\\test_download_semaphore.py
Exit 0 = pass, non-zero = fail.

Threads use a Barrier so all 3 attempt acquire() simultaneously.
Hold time (0.6s) is longer than acquire timeout (0.2s), so the
third thread must time out -> exactly 2 acquired, 1 failed.

No scanned code executed. No network. Only semaphore behavior tested.
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    from backend.api import github_scans as gs
except Exception as e:  # noqa: BLE001
    print(f"IMPORT FAILED: {e!r}")
    raise SystemExit(2)


_ACQUIRE_TIMEOUT = 0.2
_HOLD_SECONDS = 0.6


def main() -> int:
    limit = getattr(gs._DOWNLOAD_SEMAPHORE, "_value", None)
    print(f"semaphore initial value: {limit}")
    if limit != 2:
        print(f"FAIL: expected limit 2, got {limit!r}")
        return 1

    barrier = threading.Barrier(3)
    acquired: list = []
    failed: list = []
    errors: list = []
    lock = threading.Lock()

    def worker() -> None:
        try:
            barrier.wait(timeout=5)
        except threading.BrokenBarrierError:
            with lock:
                errors.append("barrier-broken")
            return
        try:
            ok = gs._DOWNLOAD_SEMAPHORE.acquire(timeout=_ACQUIRE_TIMEOUT)
            if ok:
                with lock:
                    acquired.append(True)
                time.sleep(_HOLD_SECONDS)
                gs._DOWNLOAD_SEMAPHORE.release()
            else:
                with lock:
                    failed.append(False)
        except Exception as e:  # noqa: BLE001
            with lock:
                errors.append(repr(e))

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    alive = [t for t in threads if t.is_alive()]
    if alive:
        print(f"FAIL: {len(alive)} thread(s) still alive (deadlock?)")
        return 1
    if errors:
        print(f"FAIL: errors raised: {errors[:3]}")
        return 1

    print(f"acquired={len(acquired)} failed_to_acquire={len(failed)}")
    if len(acquired) != 2:
        print(f"FAIL: expected 2 acquire, got {len(acquired)}")
        return 1
    if len(failed) != 1:
        print(f"FAIL: expected 1 fail, got {len(failed)}")
        return 1

    back = getattr(gs._DOWNLOAD_SEMAPHORE, "_value", None)
    if back != 2:
        print(f"FAIL: semaphore not fully released, value={back!r}")
        return 1

    print("PASS: download semaphore caps concurrency at 2 and releases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())