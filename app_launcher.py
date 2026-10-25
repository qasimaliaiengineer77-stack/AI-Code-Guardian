import subprocess, sys, time, webbrowser, urllib.request, psutil, os, traceback
from pathlib import Path

PORT = 8000
BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "app_error.txt"

def log_error(msg):
    with open(LOG_FILE, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {msg}\n")

try:
    # Port free karo
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            for conns in proc.connections(kind='inet'):
                if conns.laddr.port == PORT:
                    proc.kill()
                    time.sleep(1)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # Check .env
    if not (BASE_DIR / ".env").exists():
        log_error("WARNING: .env file missing! App might crash or AI features won't work.")

    python_exe = BASE_DIR / "venv" / "Scripts" / "python.exe"
    if not python_exe.exists():
        log_error(f"FATAL: python.exe not found at {python_exe}")
        sys.exit(1)

    # Server start karo
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    server_process = subprocess.Popen(
        [str(python_exe), "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=str(BASE_DIR),
        creationflags=flags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    # Wait & Open Browser
    success = False
    for _ in range(15):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=1)
            success = True
            break
        except:
            time.sleep(1)

    if success:
        webbrowser.open(f"http://127.0.0.1:{PORT}")
    else:
        log_error("FATAL: Server did not start within 15 seconds.")

except Exception as e:
    log_error(f"FATAL CRASH: {traceback.format_exc()}")
