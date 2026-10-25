import os
from backend.storage.db import (
    init_db, cleanup_expired_scans, scans_db_path, state_db_path, _connect,
)
from backend.storage.scans import save_scan, get_scan, list_scans
from backend.storage.persistent import (
    add_ignored, list_ignored, is_ignored, save_file_hash, list_file_hashes,
)

# TEST 1 — normal: init + insert + read
init_db()
assert scans_db_path().exists(), 'scan db missing'
assert state_db_path().exists(), 'state db missing'
save_scan('t7b-normal', source='zip', source_ref='x.zip', status='done', result={'ok': True})
r = get_scan('t7b-normal')
assert r and r['scan_id'] == 't7b-normal'
assert r['status'] == 'done' and r['result'] == {'ok': True}
assert 'result_json' not in r
print('TEST1 PASS')

# TEST 2 — edge: expired scan auto-deleted, fresh scan kept
with _connect(scans_db_path()) as c:
    c.execute(
        'INSERT OR REPLACE INTO scans (scan_id, created_at, expires_at, source, source_ref, status) '
        'VALUES (?,?,?,?,?,?)',
        ('t7b-expired', '2020-01-01T00:00:00Z', '2020-01-02T00:00:00Z', 'zip', 'old.zip', 'done'),
    )
n = cleanup_expired_scans()
assert n >= 1, 'cleanup removed nothing'
assert get_scan('t7b-expired') is None, 'expired still present'
assert get_scan('t7b-normal') is not None, 'fresh was wrongly deleted'
print('TEST2 PASS')

# TEST 3 — Rule 7 security: cleanup must NOT touch state DB
add_ignored(scan_id='t7b-old2', file='a.py', rule_id='B101', line=1, message_hash='h1')
save_file_hash(scan_id='t7b-old2', file='a.py', sha256='a'*64, size_bytes=10)
with _connect(scans_db_path()) as c:
    c.execute(
        'INSERT OR REPLACE INTO scans (scan_id, created_at, expires_at, source, source_ref, status) '
        'VALUES (?,?,?,?,?,?)',
        ('t7b-old2', '2020-01-01T00:00:00Z', '2020-01-02T00:00:00Z', 'zip', 'z.zip', 'done'),
    )
cleanup_expired_scans()
assert get_scan('t7b-old2') is None, 'scan-db row should be gone'
assert is_ignored(file='a.py', rule_id='B101', line=1, message_hash='h1'), 'ignore list lost!'
assert any(h['scan_id']=='t7b-old2' for h in list_file_hashes()), 'file hashes lost!'
assert 'guardian_scans.sqlite3' != 'guardian_state.sqlite3'
print('TEST3 PASS')