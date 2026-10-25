import os
from backend.ai.explainer import AIExplainer, AIExplainerError

try:
    AIExplainer(provider="not-a-provider")
    raise SystemExit("FAIL: should have raised")
except AIExplainerError:
    pass

os.environ.pop("GROQ_API_KEY", None)
os.environ.pop("GEMINI_API_KEY", None)
e = AIExplainer(provider="groq")
assert e.available is False
res = e.explain_issue({"rule_id":"X","severity":"LOW","line":1,"message":"m"})
assert res["available"] is False
assert res["provider"] == "none"
print("TEST2 PASS")