# AI Code Guardian — Portable USB Guide

Local-only, single-user Windows tool. Runs on 127.0.0.1 only. No data leaves the machine except optional AI explanation requests (existing behavior, unchanged).

## Prerequisites

- Windows 10/11 (64-bit)
- Python 3.12 on PATH (`python --version` must show 3.12.x)
- Internet access on first run (for pip install)
- ~800 MB free disk (two venvs + scanners)

## Quick start

1. Copy the entire project folder to your USB drive (e.g. `E:\AI-Code-Guardian`).
2. Double-click `start_guardian.bat`.
3. Browser opens automatically at `http://127.0.0.1:8000`.
4. To stop: double-click `stop_guardian.bat` or press Ctrl+C in the launcher window.

## First-run setup

The first time you run `start_guardian.bat` on a new machine (or a new drive letter), it will:

1. Detect that `venv\` and `venv-semgrep\` are missing.
2. Ask for confirmation (`y/N` prompt).
3. Create main venv + install `requirements.txt` (~2–3 min).
4. Create semgrep venv + install `requirements-semgrep.txt` (~4–6 min).
5. Verify scanner binaries against `PINNED_SHA256.txt` (warn-only).
6. Start the server.

After first run, subsequent launches on the same machine are instant.

**Why first-run is needed:** Python virtual environments embed absolute paths. Copying a venv between drives/machines does not work reliably. The launcher rebuilds them from scratch instead.

## Windows Defender — narrow exclusion (only if blocked)

**Do NOT exclude your entire USB drive or the whole project folder.** Only exclude the two pinned scanner binaries if Defender quarantines them:

1. Open Windows Security → Virus & threat protection → Manage settings.
2. Scroll to Exclusions → Add or remove exclusions → Add an exclusion → File.
3. Add **only** these two files:
   - `<project>\backend\scanners\bin\gitleaks.exe`
   - `<project>\backend\scanners\bin\osv-scanner.exe`
4. Verify these files against `backend\scanners\PINNED_SHA256.txt` (see below) before whitelisting.

If Defender flags anything else, stop and verify the file hash first. Do not blanket-exclude.

## SmartScreen — "Run anyway"

Windows may show "Windows protected your PC" for `start_guardian.bat` or the scanner .exe files. This is expected for unsigned executables from downloaded sources.

- Click **More info** → **Run anyway**.
- Before doing so, verify the binaries with the SHA256 check below.

## Verify scanner binaries (SHA256)

Run in PowerShell from the project folder:

```powershell
Get-FileHash backend\scanners\bin\gitleaks.exe -Algorithm SHA256 | Select-Object Hash
Get-FileHash backend\scanners\bin\osv-scanner.exe -Algorithm SHA256 | Select-Object Hash