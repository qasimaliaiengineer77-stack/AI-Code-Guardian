"""Live folder-upload limits test against http://127.0.0.1:8000.

Hits real POST /api/input/upload/folder with multipart body (stdlib only).

Scenarios:
  1. Normal small folder      -> 200 + file_count=2, workspace created
  2. Path traversal '../'     -> 400, no orphan workspace left
  3. Too many files (>MAX)    -> 400, no orphan workspace left

No scanned code executed. Network limited to 127.0.0.1:8000.

Run: python backend\\tests\\test_folder_upload_limits.py
Exit 0 = all pass.
"""
from __future__ import annotations

import io
import json
import shutil
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.core.config import MAX_FILES, WORKSPACE_DIR  # noqa: E402

ENDPOINT = "http://127.0.0.1:8000/api/input/upload/folder"


def _workspace_count() -> int:
    if not WORKSPACE_DIR.exists():
        return 0
    return sum(1 for p in WORKSPACE_DIR.iterdir() if p.is_dir())


def _build_multipart(entries: list) -> tuple:
    """entries: list of (filename, path, content_bytes). Returns (body, content_type)."""
    boundary = "----guardian" + uuid.uuid4().hex
    buf = io.BytesIO()
    for filename, path, content in entries:
        buf.write(f"--{boundary}\r\n".encode())
        buf.write(
            f'Content-Disposition: form-data; name="files"; filename="{filename}"\r\n'.encode()
        )
        buf.write(b"Content-Type: application/octet-stream\r\n\r\n")
        buf.write(content)
        buf.write(b"\r\n")
        buf.write(f"--{boundary}\r\n".encode())
        buf.write(b'Content-Disposition: form-data; name="paths"\r\n\r\n')
        buf.write(path.encode())
        buf.write(b"\r\n")
    buf.write(f"--{boundary}--\r\n".encode())
    return buf.getvalue(), f"multipart/form-data; boundary={boundary}"


def _post(entries: list, timeout: float = 30.0) -> tuple:
    body, ctype = _build_multipart(entries)
    req = Request(ENDPOINT, data=body, method="POST")
    req.add_header("Content-Type", ctype)
    try:
        with urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode(errors="replace")
    except HTTPError as e:
        return e.code, e.read().decode(errors="replace")


def _cleanup_from_body(body: str) -> None:
    try:
        scan_id = json.loads(body).get("scan_id")
    except Exception:
        return
    if not scan_id:
        return
    d = Path(WORKSPACE_DIR) / scan_id
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def _test_normal() -> str:
    before = _workspace_count()
    status, body = _post([("a.py", "a.py", b"print(1)\n"), ("b.py", "b.py", b"print(2)\n")])
    after = _workspace_count()
    if status != 200:
        return f"FAIL normal: HTTP {status} body={body[:200]}"
    compact = body.replace(" ", "")
    if '"file_count":2' not in compact:
        return f"FAIL normal: unexpected body {body[:200]}"
    if after != before + 1:
        _cleanup_from_body(body)
        return f"FAIL normal: workspace not created (before={before} after={after})"
    _cleanup_from_body(body)
    return "PASS normal: 2-file folder uploaded, workspace created then cleaned"


def _test_traversal() -> str:
    before = _workspace_count()
    status, body = _post([("evil.txt", "../evil.txt", b"x")])
    after = _workspace_count()
    if status != 400:
        return f"FAIL traversal: expected 400 got {status} body={body[:200]}"
    if after != before:
        return f"FAIL traversal: orphan workspace left (before={before} after={after})"
    return "PASS traversal: blocked with 400, no orphan workspace"


def _test_too_many() -> str:
    n = MAX_FILES + 5
    entries = [(f"f{i}.py", f"f{i}.py", b"#\n") for i in range(n)]
    before = _workspace_count()
    status, body = _post(entries)
    after = _workspace_count()
    if status != 400:
        return f"FAIL too-many: expected 400 got {status} body={body[:200]}"
    if after != before:
        return f"FAIL too-many: orphan workspace left (before={before} after={after})"
    return f"PASS too-many: {n} files rejected, no orphan workspace"


def main() -> int:
    print(f"target: {ENDPOINT}")
    print(f"MAX_FILES={MAX_FILES}  workspace={WORKSPACE_DIR}")
    results = []
    for name, fn in (
        ("normal", _test_normal),
        ("traversal", _test_traversal),
        ("too-many", _test_too_many),
    ):
        try:
            results.append(fn())
        except URLError as e:
            results.append(f"FAIL {name}: server unreachable ({e})")
            break
        except Exception as e:  # noqa: BLE001
            results.append(f"FAIL {name}: {e!r}")
    for r in results:
        print(r)
    failed = [r for r in results if r.startswith("FAIL")]
    if failed:
        print(f"FAIL: {len(failed)} test(s) failed")
        return 1
    print("PASS: all folder-upload limit tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())