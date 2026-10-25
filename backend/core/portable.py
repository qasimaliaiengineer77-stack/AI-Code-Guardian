"""Portable helper for AI Code Guardian.

Commands:
    --verify-binaries  Compare scanner binaries' SHA256 with PINNED_SHA256.txt (warn-only).
    --ensure-dirs      Create data/, data/workspace/, data/uploads/ if missing.

Read-only by default. Never edits files, never makes network calls.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_PINNED_FILE = _PROJECT_ROOT / "backend" / "scanners" / "PINNED_SHA256.txt"
_BIN_DIR = _PROJECT_ROOT / "backend" / "scanners" / "bin"
_DATA_DIR = _PROJECT_ROOT / "data"
_DATA_SUBDIRS = ("workspace", "uploads")


def _load_pinned_hashes(path: Path) -> dict:
    if not path.exists():
        return {}
    pinned: dict = {}
    current_bin = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("bin/"):
            current_bin = line.split("/", 1)[1].strip()
        elif line.startswith("sha256:") and current_bin:
            pinned[current_bin] = line.split(":", 1)[1].strip().lower()
            current_bin = None
    return pinned


def _sha256_of(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_binaries() -> int:
    if not _PINNED_FILE.exists():
        print(f"[WARN] PINNED_SHA256.txt not found at {_PINNED_FILE}")
        return 0
    pinned = _load_pinned_hashes(_PINNED_FILE)
    if not pinned:
        print("[WARN] PINNED_SHA256.txt contains no parseable entries")
        return 0
    failed = 0
    for name, expected in pinned.items():
        binary = _BIN_DIR / name
        if not binary.exists():
            print(f"[WARN] {name}: binary missing at {binary}")
            continue
        actual = _sha256_of(binary)
        if actual == expected:
            print(f"[OK]   {name}: SHA256 matches pinned")
        else:
            failed += 1
            print(f"[WARN] {name}: SHA256 mismatch (pinned={expected}, actual={actual})")
    return 0 if failed == 0 else 1


def ensure_dirs() -> int:
    created = []
    for d in (_DATA_DIR,) + tuple(_DATA_DIR / s for s in _DATA_SUBDIRS):
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            created.append(str(d))
    if created:
        print(f"[OK] created: {', '.join(created)}")
    else:
        print("[OK] data directories already present")
    return 0


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="portable", description="AI Code Guardian portable helper")
    parser.add_argument("--verify-binaries", action="store_true", help="verify scanner binary SHA256")
    parser.add_argument("--ensure-dirs", action="store_true", help="create data directories if missing")
    args = parser.parse_args(argv)
    if not (args.verify_binaries or args.ensure_dirs):
        parser.print_help()
        return 0
    rc = 0
    if args.verify_binaries:
        rc |= verify_binaries()
    if args.ensure_dirs:
        rc |= ensure_dirs()
    return rc


if __name__ == "__main__":
    sys.exit(main())