"""Tests for google-generativeai -> google-genai migration (explainer._call_gemini)."""
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.ai.explainer import AIExplainer, AIExplainerError


def _make_explainer():
    os.environ["AI_PROVIDER"] = "gemini"
    os.environ["GEMINI_API_KEY"] = "test-key-not-real"
    return AIExplainer(provider="gemini", model="gemini-2.5-flash")


# TEST 1 (normal): mocked Gemini call flows through explain_issue correctly.
def test_mocked_gemini_call():
    ex = _make_explainer()
    with patch.object(ex, "_call_gemini", return_value="mocked explanation") as m:
        res = ex.explain_issue(
            {"rule_id": "B101", "message": "assert_used", "severity": "LOW", "line": 10}
        )
    assert m.call_count == 1, "provider should be called exactly once"
    assert res["available"] is True
    assert res["provider"] == "gemini"
    assert res["explanation"] == "mocked explanation"
    print("PASS test1: mocked gemini call")


# TEST 2 (error): missing API key -> AIExplainerError, no network attempted.
def test_missing_key_raises():
    os.environ.pop("GEMINI_API_KEY", None)
    ex = AIExplainer(provider="gemini", model="gemini-2.5-flash")
    try:
        ex._call_gemini({"rule_id": "X"}, "en")
        raise AssertionError("expected AIExplainerError for missing key")
    except AIExplainerError as exc:
        assert "GEMINI_API_KEY" in str(exc)
    print("PASS test2: missing key raises AIExplainerError")


# TEST 3 (security): provider receives REDACTED copy, never the raw issue.
def test_gemini_gets_redacted_copy():
    ex = _make_explainer()
    redacted = {"rule_id": "X", "message": "[REDACTED]", "severity": "HIGH", "line": 1}
    with patch("backend.ai.explainer.redact_issue", return_value=redacted) as mock_redact:
        with patch.object(ex, "_call_gemini", return_value="ok") as mock_gemini:
            ex.explain_issue(
                {"rule_id": "X", "message": "password=secret123", "severity": "HIGH", "line": 1}
            )
    mock_redact.assert_called_once()
    sent_to_provider = mock_gemini.call_args[0][0]
    assert sent_to_provider["message"] == "[REDACTED]", "provider got raw secret!"
    print("PASS test3: provider got redacted copy only")


if __name__ == "__main__":
    test_mocked_gemini_call()
    test_missing_key_raises()
    test_gemini_gets_redacted_copy()
    print("PASS: all gemini migration tests")