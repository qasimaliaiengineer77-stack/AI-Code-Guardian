import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.ai.redaction import redact_text, redact_issue

def test_secrets():
    cases = [
        ("Groq Key", "gsk_1234567890abcdefghij", "gsk_"),
        ("Google Key", "AIzaSyA1234567890abcdefghijklmnopqrstuv", "AIza"),
        ("AWS Key (AKIA)", "AKIAIOSFODNN7EXAMPLE", "AKIA"),
        ("AWS Key (ASIA)", "ASIAIOSFODNN7EXAMPLE", "ASIA"),
        ("GitHub Token (classic)", "ghp_1234567890abcdefghijklmnopqrstuvwxyz", "ghp_"),
        ("GitHub Token (PAT)", "github_pat_1234567890abcdefghij", "github_pat_"),
        ("Slack Token", "xoxb-1234567890-abcdefghij", "xoxb-"),
        ("JWT", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c", "eyJ"),
        ("Bearer Token (unquoted)", "Bearer abcdef123456", "Bearer"),
        ("Bearer Token (quoted)", "Bearer \"abcdef123456\"", "Bearer"),
        ("Private Key (RSA)", "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA... \n-----END RSA PRIVATE KEY-----", "BEGIN RSA PRIVATE KEY"),
        ("Bandit Hardcoded Password (Short)", "hardcoded_password: 'mysecret'", "hardcoded_password"),
        ("Windows Path", r"C:\Users\Admin\secret.txt", "<user>"),
        ("Linux Path", "/home/admin/secret.txt", "<user>"),
        ("macOS Path", "/Users/admin/secret.txt", "<user>"),
        ("Windows Documents & Settings", r"C:\Documents and Settings\Admin\secret.txt", "<user>"),
        ("UNC Path", r"\\server\share\secret.txt", "<UNC_PATH>"),
    ]
    
    for name, secret, marker in cases:
        redacted = redact_text(secret)
        if marker.startswith("<"):
            assert marker in redacted, f"FAIL {name}: expected '{marker}' in output. Output: {redacted}"
        else:
            assert marker not in redacted or "[REDACTED:" in redacted, f"FAIL {name}: marker '{marker}' not redacted. Output: {redacted}"
        print(f"PASS: {name}")

def test_unicode_bypass():
    # Fullwidth AWS Key (Homoglyph)
    fw_aws = "ＡＫＩＡ１２３４５６７８９０１２３４５６"
    assert "ＡＫＩＡ" not in redact_text(fw_aws), "FAIL: Fullwidth AWS not redacted"
    print("PASS: Fullwidth AWS Key (Homoglyph)")

    # Devanagari digits in GitHub token
    dev_gh = "ghp_१२३४५६७८९०१२३४५६७८९०१२३४५६७८९०१२३४५६७८९"
    assert "ghp_१२३" not in redact_text(dev_gh), "FAIL: Devanagari GitHub not redacted"
    print("PASS: Devanagari digits in GitHub token")

def test_leaks_fixed():
    leaks = [
        ("Leak1a: Private Key (no algorithm)", "-----BEGIN PRIVATE KEY-----\nMIIE...\n-----END PRIVATE KEY-----", "PRIVATE KEY"),
        ("Leak1b: Private Key (incomplete, no END)", "-----BEGIN RSA PRIVATE KEY-----\nMIIE...", "BEGIN RSA PRIVATE KEY"),
        ("Leak2: Quoted password with spaces", 'password = "my secret 123"', "my secret 123"),
        ("Leak3c: aws_secret_access_key", "aws_secret_access_key = 'abc123def456'", "abc123def456"),
    ]
    for name, text, secret in leaks:
        redacted = redact_text(text)
        assert secret not in redacted, f"FAIL {name}: secret not redacted. Output: {redacted}"
        print(f"PASS: {name}")

def test_false_positive():
    normal = "MD5 hash: d41d8cd98f00b204e9800998ecf8427e"
    assert redact_text(normal) == normal, "FAIL: False positive (normal MD5 redacted)"
    print("PASS: False-positive (normal MD5 unchanged)")

def test_allowlist():
    issue = {"file": "test.py", "rule_id": "R1", "line": 1, "message": "password = 'password123'", "code": "secret code"}
    r = redact_issue(issue)
    assert "code" not in r, "FAIL: 'code' field not dropped"
    assert "password123" not in r["message"], "FAIL: Password inside message not redacted"
    print("PASS: Allowlist check")

if __name__ == "__main__":
    print("--- Testing secrets (existing) ---")
    test_secrets()
    print("\n--- Testing Unicode & Paths (NEW) ---")
    test_unicode_bypass()
    print("\n--- Testing Leaks (existing) ---")
    test_leaks_fixed()
    print("\n--- Testing False Positives ---")
    test_false_positive()
    print("\n--- Testing Allowlist ---")
    test_allowlist()
    print("\nTotal: All tests passed!")