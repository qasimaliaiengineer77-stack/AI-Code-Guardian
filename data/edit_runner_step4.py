"""One-shot safe editor for runner.py Step 4 (semgrep integration).
Idempotent-ish: each replacement must match exactly once.
Creates a .bak before writing. Aborts on any mismatch.
"""
from pathlib import Path
import shutil
import sys

RUNNER = Path("backend/orchestrator/runner.py")

EDITS = [
    # (label, find, replace)
    (
        "1: docstring",
        "radon + lizard -> filter",
        "radon + lizard + semgrep -> filter",
    ),
    (
        "2: import",
        "from backend.scanners.lizard_scanner import scan_with_lizard\n",
        "from backend.scanners.lizard_scanner import scan_with_lizard\n"
        "from backend.scanners.semgrep_scanner import scan_with_semgrep\n",
    ),
    (
        "3: var init",
        "    liz = None\n    o = None\n",
        "    liz = None\n    sem = None\n    o = None\n",
    ),
    (
        "4: scan call",
        "            liz = scan_with_lizard(target)\n"
        "            # Radon: incremental or full\n",
        "            liz = scan_with_lizard(target)\n"
        "            # Semgrep: always full (v0.14 - optional, graceful skip)\n"
        "            sem = scan_with_semgrep(target)\n"
        "            # Radon: incremental or full\n",
    ),
    (
        "5: skipped append",
        "            skipped.append(\"lizard\")\n",
        "            skipped.append(\"lizard\")\n"
        "            skipped.append(\"semgrep\")\n",
    ),
    (
        "6: collect_issues",
        "    raw_issues = _collect_issues(b, g, p, r, liz, o)\n",
        "    raw_issues = _collect_issues(b, g, p, r, liz, sem, o)\n",
    ),
    (
        "7: summary",
        "    liz_sum = _scanner_summary(liz)\n    o_sum = _scanner_summary(o)\n",
        "    liz_sum = _scanner_summary(liz)\n"
        "    sem_sum = _scanner_summary(sem)\n"
        "    o_sum = _scanner_summary(o)\n",
    ),
    (
        "8: scanners dict",
        "            \"lizard\": liz_sum,\n            \"radon\": r_sum,\n",
        "            \"lizard\": liz_sum,\n"
        "            \"semgrep\": sem_sum,\n"
        "            \"radon\": r_sum,\n",
    ),
    (
        "9: by_severity merge",
        "            p_sum[\"by_severity\"], liz_sum[\"by_severity\"],\n"
        "            r_sum[\"by_severity\"], o_sum[\"by_severity\"],\n",
        "            p_sum[\"by_severity\"], liz_sum[\"by_severity\"],\n"
        "            sem_sum[\"by_severity\"],\n"
        "            r_sum[\"by_severity\"], o_sum[\"by_severity\"],\n",
    ),
]

def main():
    if not RUNNER.exists():
        print(f"FAIL: {RUNNER} not found")
        sys.exit(1)

    original = RUNNER.read_text(encoding="utf-8")
    text = original

    for label, find, replace in EDITS:
        count = text.count(find)
        if count == 0:
            print(f"FAIL [{label}]: find-string NOT FOUND in runner.py")
            print(f"  Looking for: {find[:80]!r}...")
            sys.exit(2)
        if count > 1:
            print(f"FAIL [{label}]: find-string appears {count} times (expected 1)")
            print(f"  Looking for: {find[:80]!r}...")
            sys.exit(3)
        text = text.replace(find, replace, 1)
        print(f"OK   [{label}]")

    backup = RUNNER.with_suffix(".py.bak_step4")
    shutil.copy2(RUNNER, backup)
    print(f"Backup: {backup}")

    RUNNER.write_text(text, encoding="utf-8")
    print(f"DONE: {len(EDITS)} edits applied to {RUNNER}")

if __name__ == "__main__":
    main()