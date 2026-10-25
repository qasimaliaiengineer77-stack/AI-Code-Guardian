import re
import unicodedata
from typing import List, Dict, Any

# (compiled_pattern, replacement) — order matters, most specific first.
_PATTERNS: List[tuple] = [
    # Bandit specific hardcoded password/pass format (MUST be first)
    (
        re.compile(r"(?i)(hardcoded[^:'\"]{0,40}:\s*)(['\"])[^'\"]*\2"),
        r"\1[REDACTED:SECRET]",
    ),
    # Private key (plain + incomplete block)
    (
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
            r"[\s\S]*?"
            r"(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)"
        ),
        "[REDACTED:PRIVATE_KEY]",
    ),
    (re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b"), "[REDACTED:GROQ_KEY]"),
    (re.compile(r"\bAIza[\dA-Za-z_\-]{35}\b"), "[REDACTED:GOOGLE_KEY]"),
    # AWS access key IDs: AKIA (long-term) + ASIA (STS temporary)
    (re.compile(r"\b(?:AKIA|ASIA)[\dA-Z]{16}\b"), "[REDACTED:AWS_KEY]"),
    # GitHub tokens: classic (ghp_/gho_/ghu_/ghs_/ghr_) + fine-grained (github_pat_)
    (re.compile(r"\bgh[pousr]_[A-Za-z\d]{36,}\b"), "[REDACTED:GITHUB_TOKEN]"),
    (re.compile(r"\bgithub_pat_[A-Za-z\d_]{20,}\b"), "[REDACTED:GITHUB_TOKEN]"),
    (re.compile(r"\bxox[baprs]-[A-Za-z\d-]{10,}\b"), "[REDACTED:SLACK_TOKEN]"),
    (
        re.compile(r"\beyJ[A-Za-z\d_-]+\.[A-Za-z\d_-]+\.[A-Za-z\d_-]+\b"),
        "[REDACTED:JWT]",
    ),
    (
        re.compile(r"(?i)\bbearer\s+['\"]?[A-Za-z\d\-._~+/]+=*['\"]?"),
        "Bearer [REDACTED:BEARER]",
    ),
    (
        re.compile(
            r"(?i)\b("
            r"aws[_-]?secret[_-]?access[_-]?key|"
            r"aws[_-]?access[_-]?key[_-]?id|"
            r"api[_-]?key|"
            r"secret[_-]?key|"
            r"access[_-]?token|"
            r"auth[_-]?token|"
            r"client[_-]?secret|"
            r"private[_-]?key|"
            r"password|passwd|pwd|"
            r"token"
            r")\s*[:=]\s*(['\"])([^'\"]*)\2"
        ),
        r"\1 = \2[REDACTED:SECRET]\2",
    ),
    (
        re.compile(
            r"(?i)\b("
            r"aws[_-]?secret[_-]?access[_-]?key|"
            r"aws[_-]?access[_-]?key[_-]?id|"
            r"api[_-]?key|"
            r"secret[_-]?key|"
            r"access[_-]?token|"
            r"auth[_-]?token|"
            r"client[_-]?secret|"
            r"private[_-]?key|"
            r"password|passwd|pwd|"
            r"token"
            r")\s*[:=]\s*([^'\"\s]{1,})"
        ),
        r"\1 = [REDACTED:SECRET]",
    ),
    # Paths
    (re.compile(r"(?i)([A-Z]:\\Users\\)([^\\]+)(\\|$)"), r"\1<user>\3"),
    (re.compile(r"(?i)([A-Z]:\\Documents and Settings\\)([^\\]+)(\\|$)"), r"\1<user>\3"),
    (re.compile(r"(?i)(/Users/)([^/\s]+)(/|$)"), r"\1<user>\3"),
    (re.compile(r"(?i)(/home/)([^/\s]+)(/|$)"), r"\1<user>\3"),
    (re.compile(r"(?i)(\\\\[A-Za-z0-9\-\._]+\\[^\\\s]+)(\\|$)"), r"<UNC_PATH>\2"),
]

_ALLOWED_ISSUE_FIELDS = {
    "file", "rule_id", "line", "message", "severity",
    "scanner", "rule_name", "explanation", "package", "cwe_id"
}


def redact_text(text: str) -> str:
    if not text:
        return ""
    s = str(text)
    # Normalize unicode to catch homoglyphs and fullwidth characters (e.g. ＡＷＳ -> AWS)
    s = unicodedata.normalize("NFKC", s)
    for pattern, replacement in _PATTERNS:
        s = pattern.sub(replacement, s)
    return s


def redact_issue(issue: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in issue.items():
        if k not in _ALLOWED_ISSUE_FIELDS:
            continue
        if isinstance(v, str):
            out[k] = redact_text(v)
        else:
            out[k] = v
    return out


def redact_issues(issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [redact_issue(i) for i in issues]


def redact_scan_result(result: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(result)
    if "issues" in out and isinstance(out["issues"], list):
        out["issues"] = redact_issues(out["issues"])
    return out