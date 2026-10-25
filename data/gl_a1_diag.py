"""A1 + Step 2 fixture diagnostic. Run: python data\\gl_a1_diag.py"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.core.config import WORKSPACE_DIR  # noqa: E402
from backend.orchestrator.runner import run_scan  # noqa: E402

EXE = ROOT / "backend" / "scanners" / "bin" / "gitleaks.exe"
CFG = ROOT / "backend" / "scanners" / "gitleaks.toml"

STEP2 = 'GITHUB_TOKEN = "ghp_aB3xK9mN2pQ7rT5vW8yZ1cF4hJ6kL0sD3gH"\n'
RANDOM = 'api_key = "Zx9Kp2Lm7Nq4Rt8Vw3Yb6Hc1Jd5Fg0Ss"\n'
SID = "abcdef0123456789abcdef0123456789"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def direct(target: Path, mode: str):
    fd, rep = tempfile.mkstemp(prefix="gl_diag_", suffix=".json")
    os.close(fd)
    if mode == "dir":
        cmd = [str(EXE), "dir", str(target)]
    else:
        cmd = [str(EXE), "detect", "--no-git", "--source", str(target)]
    cmd += [
        "--config", str(CFG),
        "--report-format", "json",
        "--report-path", rep,
        "--redact",
        "--no-banner",
        "--log-level", "error",
    ]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    raw = Path(rep).read_text(encoding="utf-8", errors="replace").strip()
    Path(rep).unlink(missing_ok=True)
    try:
        data = json.loads(raw) if raw else []
    except Exception:
        data = []
    return p.returncode, data


def show(label, rc, data):
    rules = [str(x.get("RuleID", "")) for x in data if isinstance(x, dict)]
    files = [str(x.get("File", "")) for x in data if isinstance(x, dict)]
    print(f"  {label}: exit={rc} findings={len(data)} rules={rules} files={files}")


def fresh_dir(name, content):
    d = ROOT / "data" / name
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True, exist_ok=True)
    (d / "leaked.py").write_text(content, encoding="utf-8")
    return d


def workspace_dir(content):
    d = Path(WORKSPACE_DIR) / SID
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True, exist_ok=True)
    (d / "leaked.py").write_text(content, encoding="utf-8")
    return d


def via_run_scan():
    r = run_scan(SID, explain=False, dependencies=False, retention_days=1)
    gl = (r.get("scanners") or {}).get("gitleaks") or {}
    hits = [
        i for i in (r.get("issues") or [])
        if (i.get("scanner") or "") == "gitleaks"
    ]
    inc = r.get("incremental") or {}
    print(
        f"  run_scan: gitleaks.ok={gl.get('ok')} findings={len(hits)} "
        f"incremental={inc.get('enabled')} skipped={r.get('skipped_scanners')}"
    )
    for h in hits[:5]:
        print(f"    {h.get('rule_id')} | {h.get('file')}:{h.get('line')}")
    return gl, hits


def main():
    print("=== A1 / Step2 fixture diagnostic ===")
    print(f"  binary: {EXE}")
    print(f"  sha256(exe): {sha256_file(EXE)}")
    print(f"  sha256(cfg): {sha256_file(CFG)}")

    print("-- (a) fresh folder OUTSIDE data/workspace --")
    a = fresh_dir("_gl_fresh", STEP2)
    show("direct dir", *direct(a, "dir"))
    show("direct detect", *direct(a, "detect"))

    print("-- (b) data/workspace/<scan_id> --")
    b = workspace_dir(STEP2)
    show("direct dir", *direct(b, "dir"))
    show("direct detect", *direct(b, "detect"))

    print("-- (b2) via run_scan --")
    via_run_scan()
    print(f"  workspace files after run_scan: {sorted(p.name for p in b.iterdir())}")

    print("-- (c) A1 random secret, fresh folder --")
    c = fresh_dir("_gl_random", RANDOM)
    show("direct dir", *direct(c, "dir"))

    for d in (a, c):
        if d.exists():
            shutil.rmtree(d)
    print("=== done ===")


if __name__ == "__main__":
    main()