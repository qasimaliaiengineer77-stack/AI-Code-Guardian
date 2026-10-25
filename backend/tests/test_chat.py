import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.ai.explainer import AIExplainer, _CHAT_SYSTEM_PROMPT
from backend.ai.redaction import redact_text

def test_user_message_sanitization():
    secret_msg = "My password = 'secret123'"
    redacted = redact_text(secret_msg)
    assert "secret123" not in redacted, f"FAIL: {redacted}"
    print("PASS: user_message redaction")

def test_prompt_injection_defense():
    assert "Do NOT write code" in _CHAT_SYSTEM_PROMPT
    assert "refuse politely" in _CHAT_SYSTEM_PROMPT
    print("PASS: prompt injection defense in system prompt")

def test_chat_fallback_no_api_key():
    e = AIExplainer(provider="none")
    resp = e.chat({"total_issues": 0, "issues": []}, "hello", "en")
    assert "AI Assistant is currently disabled" in resp or "AI Assistant filhaal disabled" in resp, f"FAIL: {resp}"
    print("PASS: fallback on no API key")

if __name__ == "__main__":
    test_user_message_sanitization()
    test_prompt_injection_defense()
    test_chat_fallback_no_api_key()
    print("\nTotal: All chat tests passed!")