"""Manual test: backend.orchestrator.runner._AI_CIRCUIT thread safety.

Run: python backend\\tests\\test_circuit_thread_safety.py
Exit 0 = pass, non-zero = fail.

Concurrency only - no scanned code executed, no AI calls made.
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    from backend.orchestrator import runner  # noqa: E402
except Exception as e:  # noqa: BLE001
    print(f"IMPORT FAILED: {e!r}")
    raise SystemExit(2)


def main() -> int:
    errors: list = []
    snapshots: list = []

    def worker(i: int) -> None:
        try:
            for _ in range(300):
                ok, rem = runner._ai_circuit_snapshot()
                if not isinstance(ok, bool) or not isinstance(rem, int):
                    raise AssertionError(f"bad snapshot types: {ok!r}, {rem!r}")
                if i % 2 == 0:
                    runner._mark_ai_failed(RuntimeError("test"))
                else:
                    runner._reset_ai_circuit()
            snapshots.append(runner._ai_circuit_snapshot())
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    alive = [t for t in threads if t.is_alive()]
    if alive:
        print(f"FAIL: {len(alive)} thread(s) did not finish (possible deadlock)")
        return 1
    if errors:
        print(f"FAIL: exceptions raised: {errors[:3]}")
        return 1
    if len(snapshots) != 20:
        print(f"FAIL: expected 20 final snapshots, got {len(snapshots)}")
        return 1
    for ok, rem in snapshots:
        if not isinstance(ok, bool) or not isinstance(rem, int):
            print(f"FAIL: snapshot type wrong: {ok!r}, {rem!r}")
            return 1
        if rem < 0:
            print(f"FAIL: negative remaining: {rem}")
            return 1

    runner._reset_ai_circuit()
    print("PASS: circuit thread-safety OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())