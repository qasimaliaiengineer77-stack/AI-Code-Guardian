"""Secret redaction for AI error-summaries (Fixed Rule 3).

Only error-summaries go to AI. This module strips secrets from strings
BEFORE anything is sent. Pure regex, no external deps, no code execution.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

# (compiled_pattern, replacement) — order matters, most specific first.
_PATTERNS: List[tuple] = [
    # Bandit specific hardcoded password/pass format (MUST be first)
    (
        re.compile(r"(?i)(hardcoded[^:'\"]{0,40}:\s*)(['\"])[^'\"]*\2"),
        r"\1[REDACTED:SECRET]",
    ),
    # Private key blocks (multi-line) — MUST be before generic token rules.
    # Covers: plain "PRIVATE KEY", RSA/EC/DSA/OPENSSH variants, and
    # incomplete blocks (missing END — redacted through end of input).
    (
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
            r"[\s\S]*?"
            r"(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)"
        ),
        "[REDACTED:PRIVATE_KEY]",
    ),
    (re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b"), "[REDACTED:GROQ_KEY]"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "[REDACTED:GOOGLE_KEY]"),
    # AWS access key IDs: AKIA (long-term) + ASIA (STS temporary)
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "[REDACTED:AWS_KEY]"),
    # GitHub tokens: classic (ghp_/gho_/ghu_/ghs_/ghr_) + fine-grained (github_pat_)
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"), "[REDACTED:GITHUB_TOKEN]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "[REDACTED:GITHUB_TOKEN]"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "[REDACTED:SLACK_TOKEN]"),
    (
        re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
        "[REDACTED:JWT]",
    ),
    # Bearer token — optionally quoted
    (
        re.compile(r"(?i)\bbearer\s+['\"]?[A-Za-z0-9\-._~+/]+=*['\"]?"),
        "Bearer [REDACTED:BEARER]",
    ),
    # Generic key=value / key: value.
    # Quoted values (may contain spaces) are consumed fully;
    # unquoted values stop at whitespace. Includes aws_secret_access_key.
    (
        re.compile(
            r"(?i)\b("
            r"aws[_-]?secret[_-]?access[_-]?key|"
            r"secret[_-]?key|"
            r"access[_-]?token|"
            r"refresh[_-]?token|"
            r"api[_-]?key|"
            r"apikey|"
            r"authorization|"
            r"private[_-]?key|"
            r"password|"
            r"passwd|"
            r"secret|"
            r"token|"
            r"pwd|"
            r"auth"
            r")"
            r"(\s*[:=]\s*)"
            r"(?:['\"]([^'\"]*)['\"]|([^'\"\s]{1,}))"
        ),
        r"\1\2[REDACTED:SECRET]",
    ),
    (re.compile(r"(?i)([A-Z]:\\Users\\)([^\\]+)(\\|$)"), r"\1<user>\3"),
    (re.compile(r"(?i)(/home/)([^/\s]+)(/|$)"), r"\1<user>\3"),
]

# Fields we send to AI. Everything else (e.g. 'code', 'snippet') is dropped.
_ALLOWED_ISSUE_FIELDS = (
    "scanner",
    "rule_id",
    "rule_name",
    "severity",
    "confidence",
    "line",
    "column",
    "file",
    "message",
    "cwe_id",
    "more_info",
)


def redact_text(text: Any) -> str:
    """Return text with known secret patterns replaced by [REDACTED:...]."""
    if text is None:
        return ""
    s = str(text)
    for pattern, replacement in _PATTERNS:
        s = pattern.sub(replacement, s)
    return s


def redact_issue(issue: Dict[str, Any]) -> Dict[str, Any]:
    """Return a minimal, redacted issue dict safe to send to AI (Fixed Rule 3)."""
    if not isinstance(issue, dict):
        return {}
    out: Dict[str, Any] = {}
    for key in _ALLOWED_ISSUE_FIELDS:
        if key in issue and issue[key] is not None:
            out[key] = redact_text(issue[key])
    return out


def redact_issues(issues: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Redact a list of issues."""
    return [redact_issue(i) for i in issues if isinstance(i, dict)]


def redact_scan_result(scan_result: Dict[str, Any]) -> Dict[str, Any]:
    """Redact a scanner result dict — only safe summary fields kept for AI."""
    if not isinstance(scan_result, dict):
        return {"total_issues": 0, "issues": []}
    safe_issues = redact_issues(scan_result.get("issues") or [])
    return {
        "scanner": redact_text(scan_result.get("scanner", "")),
        "total_issues": len(safe_issues),
        "issues": safe_issues,
    }