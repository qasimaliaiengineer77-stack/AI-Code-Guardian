"""Live test: redirect-block in github_fetch.py.

Test 1: Allowed redirect (github.com -> codeload.github.com) accepted.
Test 2: Disallowed redirect (github.com -> evil.com) rejected.

Run: python backend\tests\test_redirect_block.py
"""
import sys
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.input_handler.github_fetch import _RestrictedRedirect, ALLOWED_HOSTS


def _req(url="https://github.com/u/r/archive/refs/heads/main.zip"):
    return urllib.request.Request(url, method="HEAD")


def test_allowed():
    """Allowed redirect (codeload.github.com) should NOT be blocked."""
    opener = _RestrictedRedirect()
    try:
        result = opener.redirect_request(
            _req(), None, 302, "Found", {},
            "https://codeload.github.com/u/r/zip/refs/heads/main",
        )
        if result is None:
            print("FAIL: allowed redirect returned None (treated as blocked)")
            return False
        host = result.full_url.split("/")[2]
        print(f"PASS: allowed redirect accepted -> host={host}")
        return True
    except urllib.error.HTTPError as e:
        print(f"FAIL: allowed redirect was blocked (HTTPError {e.code})")
        return False
    except Exception as e:
        print(f"FAIL: allowed redirect raised {type(e).__name__}: {e}")
        return False


def test_disallowed():
    """Disallowed redirect (evil.com) MUST be rejected."""
    opener = _RestrictedRedirect()
    try:
        result = opener.redirect_request(
            _req(), None, 302, "Found", {},
            "https://evil.com/malware.zip",
        )
        if result is None:
            print("PASS: disallowed redirect blocked (returned None)")
            return True
        print(f"FAIL: disallowed redirect was allowed -> {result.full_url}")
        return False
    except urllib.error.HTTPError as e:
        print(f"PASS: disallowed redirect blocked (HTTPError {e.code})")
        return True
    except Exception as e:
        print(f"PASS: disallowed redirect blocked ({type(e).__name__})")
        return True


if __name__ == "__main__":
    print(f"ALLOWED_HOSTS = {sorted(ALLOWED_HOSTS)}")
    print("=" * 60)
    r1 = test_allowed()
    print("=" * 60)
    r2 = test_disallowed()
    print("=" * 60)
    if r1 and r2:
        print("RESULT: PASS")
        sys.exit(0)
    print("RESULT: FAIL")
    sys.exit(1)