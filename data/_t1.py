from backend.ai.redaction import redact_text
from backend.ai.explainer import AIExplainer

raw = "error near api_key='supersecret1234' path C:\\Users\\Qasim ali\\x.py"
out = redact_text(raw)
assert "supersecret1234" not in out, out
assert "Qasim ali" not in out, out
assert "[REDACTED:SECRET]" in out, out
assert "<user>" in out, out

e = AIExplainer(provider="none")
issue = {"scanner":"bandit","rule_id":"B105","rule_name":"hardcoded_password_string",
         "severity":"MEDIUM","line":10,"message":"Possible hardcoded password",
         "code":"password = 'abc'"}
res = e.explain_issue(issue)
assert res["available"] is False
assert res["provider"] == "none"
assert "code" not in res["issue"]
assert "Line 10" in res["explanation"]
print("TEST1 PASS")