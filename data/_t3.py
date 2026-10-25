from backend.ai.redaction import redact_text, redact_issue

secrets = [
    "gsk_abcdefghijklmnopqrstuvwxyz0123456789",
    "AIza" + "A"*35,
    "AKIA" + "A"*16,
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.sig1234567890",
    "password = 'hunter2secret'",
    "-----BEGIN RSA PRIVATE KEY-----" + chr(10) + "MIIE..." + chr(10) + "-----END RSA PRIVATE KEY-----",
]
for s in secrets:
    out = redact_text(s)
    assert s not in out, "LEAK: " + repr(s) + " -> " + repr(out)

issue = {
    "rule_id":"B105","line":3,
    "message":"hardcoded password = 'hunter2secret'",
    "api_key":"gsk_abcdefghijklmnopqrstuvwxyz0123456789",
    "code":"password='x'",
    "file":"C:\\Users\\Qasim ali\\app.py",
}
safe = redact_issue(issue)
assert "hunter2secret" not in safe.get("message","")
assert "gsk_" not in safe.get("message","")
assert "code" not in safe
assert "Qasim ali" not in safe.get("file","")
print("TEST3 PASS")