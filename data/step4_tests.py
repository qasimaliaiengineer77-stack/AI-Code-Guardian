"""Step 4 semgrep scanner tests: T1, T2, T3a, T3b.

Run one at a time:
    python data/step4_tests.py t1
    python data/step4_tests.py t2
    python data/step4_tests.py t3a
    python data/step4_tests.py t3b
"""
import shutil
import sys
import tempfile
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.scanners.semgrep_scanner import scan_with_semgrep


def _mk_workspace() -> Path:
    return Path(tempfile.mkdtemp(prefix="guardian_step4_t_"))


def _cleanup(d: Path) -> None:
    if d and d.exists():
        shutil.rmtree(d, ignore_errors=True)


SIMPLE = '''"""Simple safe file."""
def add(a, b):
    return a + b

def mul(a, b):
    return a * b
'''

VULN = '''"""Vulnerable demo."""
import requests

def unsafe_eval(s):
    return eval(s)

def unsafe_get(url):
    return requests.get(url, verify=False)
'''


def t1():
    """Clean file -> 0 findings, ok=True."""
    d = _mk_workspace()
    try:
        (d / "simple.py").write_text(SIMPLE, encoding="utf-8")
        r = scan_with_semgrep(str(d))
        print(f"T1 ok={r['ok']} total={r['total_issues']} scanner={r['scanner']} errors={r['scan_errors']}")
        assert r["ok"] is True, f"expected ok=True, got {r['ok']}"
        assert r["scanner"] == "semgrep"
        assert r["total_issues"] == 0, f"expected 0, got {r['total_issues']}"
        print("T1 PASS")
    finally:
        _cleanup(d)


def t2():
    """Vulnerable code -> specific rule_ids, correct severity, no fix/metavars/lines."""
    d = _mk_workspace()
    try:
        (d / "vuln.py").write_text(VULN, encoding="utf-8")
        r = scan_with_semgrep(str(d))
        print(f"T2 ok={r['ok']} total={r['total_issues']} errors={r['scan_errors']}")
        rule_ids = sorted({i["rule_id"] for i in r["issues"]})
        print(f"T2 rule_ids={rule_ids}")
        for i in r["issues"]:
            print(f"  {i['rule_id']} line={i['line']} sev={i['severity']} file={i['file']}")
        assert r["ok"] is True
        assert "ai-code-guardian.eval-usage" in rule_ids, "eval-usage rule missing"
        assert "ai-code-guardian.requests-verify-false" in rule_ids, "requests-verify-false rule missing"
        # Rule 3: no source code leaked
        for i in r["issues"]:
            assert "fix" not in i, "fix field must be dropped"
            assert "metavars" not in i, "metavars field must be dropped"
            assert "lines" not in i, "lines field must be dropped"
            assert "\n" not in i["message"], "multi-line message (source leak)"
        # Severity mapping
        sev_by_rule = {i["rule_id"]: i["severity"] for i in r["issues"]}
        assert sev_by_rule.get("ai-code-guardian.eval-usage") == "MEDIUM"
        assert sev_by_rule.get("ai-code-guardian.requests-verify-false") == "HIGH"
        print("T2 PASS")
    finally:
        _cleanup(d)


def t3a():
    """Rule 2: repo .semgrepignore must NOT affect scan (sandbox copy)."""
    d = _mk_workspace()
    try:
        # ignore vuln.py via repo .semgrepignore
        (d / ".semgrepignore").write_text("vuln.py\n", encoding="utf-8")
        (d / "vuln.py").write_text(VULN, encoding="utf-8")
        r = scan_with_semgrep(str(d))
        print(f"T3a ok={r['ok']} total={r['total_issues']}")
        rule_ids = sorted({i["rule_id"] for i in r["issues"]})
        print(f"T3a rule_ids={rule_ids}")
        assert r["ok"] is True
        assert "ai-code-guardian.eval-usage" in rule_ids, (
            "sandbox copy did not defeat repo .semgrepignore — RULE 2 VIOLATION"
        )
        print("T3a PASS (sandbox bypasses repo .semgrepignore)")
    finally:
        _cleanup(d)


def t3b():
    """Graceful skip if semgrep binary missing: ok=True, 0 findings, error noted."""
    import backend.scanners.semgrep_scanner as mod
    original = mod._SEMGREP_EXE
    mod._SEMGREP_EXE = Path("C:/nonexistent/semgrep.exe")
    d = _mk_workspace()
    try:
        (d / "vuln.py").write_text(VULN, encoding="utf-8")
        r = scan_with_semgrep(str(d))
        print(f"T3b ok={r['ok']} total={r['total_issues']} errors={r['scan_errors']}")
        assert r["ok"] is True, "graceful skip should still be ok=True"
        assert r["total_issues"] == 0
        assert any("not installed" in e.lower() for e in r["scan_errors"]), (
            "expected 'not installed' in scan_errors"
        )
        print("T3b PASS (graceful skip when semgrep missing)")
    finally:
        mod._SEMGREP_EXE = original
        _cleanup(d)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "t1":
        t1()
    elif arg == "t2":
        t2()
    elif arg == "t3a":
        t3a()
    elif arg == "t3b":
        t3b()
    else:
        print("usage: python data/step4_tests.py t1|t2|t3a|t3b")
        sys.exit(1)