"""AI Explainer — explains static-analysis issues in simple words.

Fixed Rules enforced here:
  Rule 3: Only error-summaries go to AI; never full file.
          Everything passed through backend.ai.redaction first.
  Rule 4: System prompt forbids inventing. If info insufficient, AI must say so.
  Rule 5: API keys read from environment (.env); never logged or returned.

Design:
  - Provider: AI_PROVIDER env (groq|gemini|none). Default: auto from keys.
  - If no key configured -> deterministic fallback (no network).
  - SDKs are lazy-imported; the tool works without them in fallback mode.
  - Gemini SDK: google-genai (>=2.0). Legacy google-generativeai is REMOVED.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from backend.ai.redaction import redact_issue, redact_issues


class AIExplainerError(Exception):
    """Raised when the explainer is misconfigured or the provider call fails."""


_SYSTEM_PROMPT = (
    "You are a static-analysis explainer for a security and code-quality scanner. "
    "You will receive ONLY a compact error summary: scanner name, rule id, rule name, "
    "severity, line number, and a short message. The summary is ALREADY redacted. "
    "Rules you MUST follow:\n"
    "1. Explain what the issue means in simple, plain language and why it matters.\n"
    "2. Do NOT invent code, file contents, or context that was not given to you.\n"
    "3. Do NOT produce patches, rewrites, or exact code fixes.\n"
    "4. Do NOT ask for more source code.\n"
    "5. Do NOT execute or suggest executing the scanned code.\n"
    "6. If the summary is insufficient, say what specific detail would help - do not guess.\n"
    "Keep each explanation to a few short sentences."
)


def _read_env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _pick_provider() -> str:
    explicit = _read_env("AI_PROVIDER").lower()
    if explicit in ("groq", "gemini", "none"):
        return explicit
    if _read_env("GROQ_API_KEY"):
        return "groq"
    if _read_env("GEMINI_API_KEY"):
        return "gemini"
    return "none"


def _fallback_explanation(issue: Dict[str, Any], language: str) -> str:
    """Deterministic, no-invention explanation when no AI provider is configured."""
    rule = issue.get("rule_id") or issue.get("rule_name") or "this rule"
    msg = issue.get("message") or "no message provided"
    sev = issue.get("severity") or "unknown"
    line = issue.get("line", "?")
    if language.lower() in ("roman_urdu", "ur", "urdu"):
        return (
            f"Line {line} par {sev} severity ka issue mila ({rule}). "
            f"Scanner ne kaha: \"{msg}\". AI provider configured nahi hai, "
            f"is liye ye summary dikhayi ja rahi hai. Detailed explanation ke liye "
            f"AI_PROVIDER aur API key .env mein set karein."
        )
    return (
        f"Line {line}: {sev} severity issue ({rule}). "
        f"Scanner message: \"{msg}\". "
        f"No AI provider is configured, so this is the raw summary. "
        f"Set AI_PROVIDER and the matching API key in .env for a detailed explanation."
    )


class AIExplainer:
    """Tiny wrapper around Groq/Gemini with strict Rule 3/4/5 behavior."""

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ) -> None:
        self.provider = (provider or _pick_provider()).lower()
        if self.provider not in ("groq", "gemini", "none"):
            raise AIExplainerError(
                f"Unknown AI provider '{self.provider}'. Use groq, gemini, or none."
            )
        self.timeout_seconds = timeout_seconds or int(
            _read_env("AI_TIMEOUT_SECONDS", "30") or "30"
        )
        if self.provider == "groq":
            self.model = model or _read_env("AI_MODEL", "llama-3.1-8b-instant")
        elif self.provider == "gemini":
            self.model = model or _read_env("AI_MODEL", "gemini-1.5-flash")
        else:
            self.model = "none"

    @property
    def available(self) -> bool:
        if self.provider == "none":
            return False
        if self.provider == "groq":
            return bool(_read_env("GROQ_API_KEY"))
        if self.provider == "gemini":
            return bool(_read_env("GEMINI_API_KEY"))
        return False

    def explain_issue(
        self, issue: Dict[str, Any], language: str = "en"
    ) -> Dict[str, Any]:
        """Explain one issue. Issue is redacted before leaving this function."""
        safe = redact_issue(issue)
        if not self.available:
            return {
                "issue": safe,
                "provider": "none",
                "available": False,
                "explanation": _fallback_explanation(safe, language),
            }
        try:
            text = self._call_provider(safe, language)
            return {
                "issue": safe,
                "provider": self.provider,
                "available": True,
                "explanation": text,
            }
        except AIExplainerError:
            raise
        except Exception as exc:  # never leak keys in the message
            raise AIExplainerError(
                f"AI provider call failed ({self.provider}): {type(exc).__name__}"
            ) from None

    def explain_issues(
        self, issues: List[Dict[str, Any]], language: str = "en"
    ) -> List[Dict[str, Any]]:
        safe_issues = redact_issues(issues)
        return [self.explain_issue(i, language=language) for i in safe_issues]

    # ---- provider internals ----

    def _user_prompt(self, safe_issue: Dict[str, Any], language: str) -> str:
        return (
            "Explain the following static-analysis finding. "
            f"Reply in language code: {language}.\n\n"
            "ERROR_SUMMARY_JSON:\n"
            + json.dumps(safe_issue, ensure_ascii=False, indent=2)
        )

    def _call_provider(self, safe_issue: Dict[str, Any], language: str) -> str:
        if self.provider == "groq":
            return self._call_groq(safe_issue, language)
        if self.provider == "gemini":
            return self._call_gemini(safe_issue, language)
        raise AIExplainerError("No provider selected.")

    def _call_groq(self, safe_issue: Dict[str, Any], language: str) -> str:
        api_key = _read_env("GROQ_API_KEY")
        if not api_key:
            raise AIExplainerError("GROQ_API_KEY is not set.")
        try:
            from groq import Groq  # lazy import
        except Exception:
            raise AIExplainerError(
                "groq SDK not installed. Run: pip install groq"
            ) from None
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": self._user_prompt(safe_issue, language)},
            ],
            temperature=0.2,
        )
        try:
            return resp.choices[0].message.content or ""
        except Exception:
            raise AIExplainerError(
                "Groq returned an unexpected response shape."
            ) from None

    def _call_gemini(self, safe_issue: Dict[str, Any], language: str) -> str:
        """Gemini via google-genai (new SDK). Legacy google-generativeai removed."""
        api_key = _read_env("GEMINI_API_KEY")
        if not api_key:
            raise AIExplainerError("GEMINI_API_KEY is not set.")
        try:
            from google import genai  # lazy import (new SDK)
            from google.genai import types
        except Exception:
            raise AIExplainerError(
                "google-genai SDK not installed. Run: pip install google-genai"
            ) from None

        client = genai.Client(api_key=api_key)
        try:
            resp = client.models.generate_content(
                model=self.model,
                contents=self._user_prompt(safe_issue, language),
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    temperature=0.2,
                ),
            )
        except Exception as exc:
            raise AIExplainerError(
                f"Gemini provider call failed ({type(exc).__name__})"
            ) from None
        finally:
            try:
                client.close()
            except Exception:
                pass

        text = getattr(resp, "text", None)
        if not text:
            try:
                text = resp.candidates[0].content.parts[0].text
            except Exception:
                text = ""
        if not text:
            raise AIExplainerError(
                "Gemini returned an unexpected response shape."
            )
        return text