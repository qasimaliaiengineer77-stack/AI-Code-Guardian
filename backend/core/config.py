# FILE: backend\core\config.py
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
WORKSPACE_DIR = DATA_DIR / "workspace"

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

# STEP 2 input limits
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_FILES = 500
MAX_PATH_DEPTH = 15
MAX_PATH_LENGTH = 240

# Fixed Rule 6: sirf localhost par bind.
if HOST != "127.0.0.1":
    raise RuntimeError("HOST must be 127.0.0.1 (Fixed Rule 6).")

for _d in (DATA_DIR, UPLOADS_DIR, WORKSPACE_DIR):
    _d.mkdir(parents=True, exist_ok=True)