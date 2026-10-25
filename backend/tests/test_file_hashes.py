import sys
import sqlite3
from pathlib import Path
import hashlib
import shutil

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.storage.db import state_db_path
from backend.storage.persistent import list_file_hashes
from backend.orchestrator.runner import _compute_file_hashes

def run_tests():
    print("--- Testing File Hashes ---")
    
    test_scan_id = "test_scan_hash_123"
    workspace = Path("data") / "workspace" / test_scan_id
    workspace.mkdir(parents=True, exist_ok=True)
    
    # FIX: Clean up DB from any previous failed runs
    with sqlite3.connect(state_db_path()) as c:
        c.execute("DELETE FROM file_hashes WHERE scan_id = ?", (test_scan_id,))
    
    test_file = workspace / "dummy_test.py"
    test_file.write_bytes(b"print('hello')\n")
    
    actual_bytes = test_file.read_bytes()
    expected_hash = hashlib.sha256(actual_bytes).hexdigest()
    print(f"  File size on disk: {len(actual_bytes)} bytes")
    print(f"  Expected hash: {expected_hash}")
    
    _compute_file_hashes(test_scan_id, workspace)
    hashes = list_file_hashes(test_scan_id)
    
    if not hashes:
        print("FAIL: No hashes found in DB")
        sys.exit(1)
    
    row = hashes[0]
    print(f"  DB hash: {row.get('sha256')}")
    
    # Test 1: Hash correctness
    if row.get("sha256") == expected_hash:
        print("PASS: SHA-256 hash matches actual file content")
    else:
        print(f"FAIL: Hash mismatch. Expected {expected_hash}, got {row.get('sha256')}")
        sys.exit(1)
    
    # Test 2: Data Privacy
    if "content" not in row and "code" not in row:
        print("PASS: No code/content saved in DB")
    else:
        print("FAIL: Code or content found in DB!")
        sys.exit(1)
    
    # Test 3: Relative path is correct
    if row.get("file") == "dummy_test.py":
        print("PASS: Relative path is correct")
    else:
        print(f"FAIL: Path mismatch. Got {row.get('file')}")
        sys.exit(1)
    
    # Cleanup
    shutil.rmtree(workspace, ignore_errors=True)
    with sqlite3.connect(state_db_path()) as c:
        c.execute("DELETE FROM file_hashes WHERE scan_id = ?", (test_scan_id,))
    
    print("\nTotal: All tests passed.")
    sys.exit(0)

if __name__ == "__main__":
    run_tests()