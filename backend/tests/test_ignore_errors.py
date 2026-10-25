"""Test: 404/400 on bad inputs (no 500 crashes)."""
import json
import sys
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000"


def _req(method, path, body=None):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, {}


def main():
    # 1. POST ignore on non-existent scan -> 404
    st, _ = _req("POST", "/api/scans/" + "a" * 32 + "/ignore", {
        "file": "x.py", "rule_id": "R1", "line": 1, "message": "m",
    })
    assert st == 404, f"expected 404, got {st}"
    print("PASS: ignore on missing scan -> 404")

    # 2. GET ignored on non-existent scan -> 404
    st, _ = _req("GET", "/api/scans/" + "b" * 32 + "/ignored")
    assert st == 404, f"expected 404, got {st}"
    print("PASS: list ignored on missing scan -> 404")

    # 3. DELETE bad ignore id on real scan -> 404
    st, body = _req("GET", "/api/scans?limit=1")
    assert st == 200
    scans = body.get("scans") or []
    if not scans:
        print("SKIP: no scans to test against")
        sys.exit(0)
    sid = scans[0]["scan_id"]
    st, _ = _req("DELETE", f"/api/scans/{sid}/ignored/999999999")
    assert st == 404, f"expected 404, got {st}"
    print("PASS: delete bad ignore id -> 404")

    print("\nAll Test 2 assertions passed.")


if __name__ == "__main__":
    main()