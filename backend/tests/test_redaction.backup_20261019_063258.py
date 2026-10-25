import sys
from pathlib import Path

# Ensure we can import backend
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.ai.redaction import redact_text, redact_issue


def run_tests():
    passed = 0
    failed = 0

    def check(name, text, expected_not_in, expected_in):
        nonlocal passed, failed
        out = redact_text(text)
        # Security assertion: raw secret MUST be gone, redaction marker MUST be present.
        if expected_not_in not in out and expected_in in out:
            print(f"PASS: {name}")
            passed += 1
        else:
            print(f"FAIL: {name}")
            print(f"  Input:    {text!r}")
            print(f"  Output:   {out!r}")
            print(f"  Expected to be removed: {expected_not_in!r}")
            print(f"  Expected to contain: {expected_in!r}")
            failed += 1

    print("--- Testing redact_text (existing) ---")
    check("Groq Key", "gsk_1234567890abcdefghijklmn", "gsk_1234567890abcdefghijklmn", "[REDACTED:GROQ_KEY]")
    check("Google Key", "AIzaSyD-1234567890abcdefghijklmnopqrstu", "AIzaSyD-1234567890abcdefghijklmnopqrstu", "[REDACTED:GOOGLE_KEY]")
    check("AWS Key (AKIA)", "AKIAIOSFODNN7EXAMPLE", "AKIAIOSFODNN7EXAMPLE", "[REDACTED:AWS_KEY]")
    check("GitHub Token (classic)", "ghp_1234567890abcdefghijklmnopqrstuvwxyz", "ghp_1234567890abcdefghijklmnopqrstuvwxyz", "[REDACTED:GITHUB_TOKEN]")
    check("Slack Token", "xoxb-1234567890-abcdefghij", "xoxb-1234567890-abcdefghij", "[REDACTED:SLACK_TOKEN]")
    check("JWT", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", "[REDACTED:JWT]")
    check("Bearer Token (unquoted)", "Bearer abcdef123456", "abcdef123456", "Bearer [REDACTED:BEARER]")
    check("Private Key (RSA)", "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----", "MIIEpAIBAAKCAQEA", "[REDACTED:PRIVATE_KEY]")
    check("Bandit Hardcoded Password (Short)", "Possible hardcoded password: 'hunter2'", "hunter2", "[REDACTED:SECRET]")
    check("Windows Path", "C:\\Users\\Qasim\\secret.txt", "Qasim", "<user>")
    check("Linux Path", "/home/qasim/project/app.py", "qasim", "<user>")

    print("\n--- NEW: 4 leak fixes (secret must be absent from output) ---")

    # Leak 1a: Private key WITHOUT RSA/EC/OPENSSH prefix
    pk_plain = "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASC\n-----END PRIVATE KEY-----"
    check(
        "Leak1a: Private Key (no algorithm)",
        pk_plain,
        "MIIEvQIBADANBgkqhkiG9w0BAQEFAASC",
        "[REDACTED:PRIVATE_KEY]",
    )

    # Leak 1b: Incomplete private key block (no END)
    pk_incomplete = "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASC\nabcdef"
    check(
        "Leak1b: Private Key (incomplete, no END)",
        pk_incomplete,
        "MIIEvQIBADANBgkqhkiG9w0BAQEFAASC",
        "[REDACTED:PRIVATE_KEY]",
    )

    # Leak 2: Quoted password with spaces — full value must go
    check(
        "Leak2: Quoted password with spaces",
        'password="my secret 123"',
        "my secret 123",
        "[REDACTED:SECRET]",
    )

    # Leak 3a: ASIA (STS temporary) AWS access key
    check(
        "Leak3a: ASIA AWS key",
        "ASIAIOSFODNN7EXAMPLE",
        "ASIAIOSFODNN7EXAMPLE",
        "[REDACTED:AWS_KEY]",
    )

    # Leak 3b: github_pat_ fine-grained token
    pat = "github_pat_11ABCDEFG0123456789_abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOP"
    check("Leak3b: github_pat_ token", pat, pat, "[REDACTED:GITHUB_TOKEN]")

    # Leak 3c: aws_secret_access_key=... (underscore style)
    check(
        "Leak3c: aws_secret_access_key",
        "aws_secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "[REDACTED:SECRET]",
    )

    # Leak 4: Bearer with quoted token
    check(
        "Leak4: Bearer quoted token",
        'Bearer "abcDEF123456"',
        "abcDEF123456",
        "Bearer [REDACTED:BEARER]",
    )

    # False positive: normal message must remain unchanged
    normal_msg = "Use of weak MD5 hash for security. Consider usedforsecurity=False"
    out_normal = redact_text(normal_msg)
    if out_normal == normal_msg:
        print("PASS: False-positive: normal MD5 message unchanged")
        passed += 1
    else:
        print(f"FAIL: False-positive: normal message was altered!\n  Output: {out_normal!r}")
        failed += 1

    print("\n--- Testing redact_issue (Allowlist check) ---")
    issue = {
        "rule_id": "B105",
        "message": "Possible hardcoded password: 'hunter2'",
        "code": "password = 'hunter2'",  # This should be dropped
        "line": 10,
    }
    safe_issue = redact_issue(issue)

    if "code" not in safe_issue:
        print("PASS: 'code' field dropped")
        passed += 1
    else:
        print("FAIL: 'code' field is still present!")
        failed += 1

    if "hunter2" not in safe_issue.get("message", "") and "[REDACTED:SECRET]" in safe_issue.get("message", ""):
        print("PASS: Password inside message was redacted")
        passed += 1
    else:
        print("FAIL: Password inside message was NOT redacted correctly")
        failed += 1

    print(f"\nTotal: {passed} passed, {failed} failed.")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_tests()