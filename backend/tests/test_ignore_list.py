"""Test: add ignore -> filter on GET -> list contains it -> delete."""
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
        return e.code, json.loads(e.read().decode() or "{}")


def main():
    scan_id = "1234567890abcdef1234567890abcdef"
    
    # Fetch the dummy scan directly
    st, row = _req("GET", f"/api/scans/{scan_id}")
    assert st == 200, f"get scan failed: {st}"
    result = row.get("result")
    if isinstance(result, str):
        result = json.loads(result)
    
    issues = result.get("issues") or []
    if not issues:
        print("SKIP: dummy scan has no issues")
        sys.exit(0)
        
    issue = issues[0]
    print(f"Using scan: {scan_id}, issue file={issue.get('file')}, rule={issue.get('rule_id')}")

    # Ignore it
    st, _ = _req("POST", f"/api/scans/{scan_id}/ignore", {
        "file": issue.get("file", ""),
        "rule_id": issue.get("rule_id", ""),
        "line": issue.get("line"),
        "message": issue.get("message", ""),
    })
    assert st == 200, f"ignore failed: {st}"
    print("PASS: ignore POST returned 200")

    # GET scan -> issue filtered out
    st, row = _req("GET", f"/api/scans/{scan_id}")
    assert st == 200, f"get scan failed: {st}"
    result = row.get("result")
    if isinstance(result, str):
        result = json.loads(result)
    remaining = result.get("issues") or []
    for i in remaining:
        if (i.get("file") == issue.get("file") and
                i.get("rule_id") == issue.get("rule_id") and
                i.get("line") == issue.get("line")):
            print("FAIL: ignored issue still present after GET")
            sys.exit(1)
    print(f"PASS: GET filtered it out (remaining issues: {len(remaining)})")
    assert result.get("total_issues") == len(remaining), "total_issues not recalculated"
    print("PASS: total_issues recalculated")

    # List ignored
    st, lst = _req("GET", f"/api/scans/{scan_id}/ignored")
    assert st == 200, f"list ignored failed: {st}"
    assert len(lst.get("items", [])) >= 1, "ignore list empty"
    print(f"PASS: list /ignored returned {len(lst.get('items'))} items")

    # Cleanup: un-ignore the one we added
    target = lst["items"][0]
    st, _ = _req("DELETE", f"/api/scans/{scan_id}/ignored/{target['id']}")
    assert st == 200, f"un-ignore failed: {st}"
    print("PASS: un-ignore deleted")
    print("\nAll Test 1 assertions passed.")


if __name__ == "__main__":
    main()