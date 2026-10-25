# FILE: backend\input_handler\uploads.py
import io
import re
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import Iterable

from fastapi import UploadFile

from backend.core.config import (
    MAX_FILES,
    MAX_PATH_DEPTH,
    MAX_UNCOMPRESSED_BYTES,
    MAX_UPLOAD_BYTES,
    WORKSPACE_DIR,
)

_WIN_RESERVED = {
    "con", "prn", "aux", "nul",
    *[f"com{i}" for i in range(1, 10)],
    *[f"lpt{i}" for i in range(1, 10)],
}
_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_FORBIDDEN_CHARS = set('<>:"|?*')


class UploadError(Exception):
    pass


def new_scan_id() -> str:
    return uuid.uuid4().hex


def scan_dir(scan_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}", scan_id):
        raise UploadError("Invalid scan id.")
    p = WORKSPACE_DIR / scan_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def _safe_relative_path(name: str) -> Path:
    if not name or name in (".", ".."):
        raise UploadError(f"Unsafe path: {name!r}")
    if name.startswith(("/", "\\")) or _DRIVE_RE.match(name):
        raise UploadError(f"Absolute path not allowed: {name!r}")

    rel = Path(name.replace("\\", "/"))
    parts = [p for p in rel.parts if p not in ("", ".")]
    if not parts:
        raise UploadError(f"Empty path: {name!r}")
    if any(p == ".." for p in parts):
        raise UploadError(f"Path traversal blocked: {name!r}")
    if len(parts) > MAX_PATH_DEPTH:
        raise UploadError(f"Path too deep ({len(parts)}): {name!r}")
    for p in parts:
        if any(c in _FORBIDDEN_CHARS for c in p):
            raise UploadError(f"Invalid character in filename: {p!r}")
        if p.lower().split(".")[0] in _WIN_RESERVED:
            raise UploadError(f"Windows reserved name: {p!r}")
    return Path(*parts)


def _ensure_inside(base: Path, target: Path) -> None:
    base_r = base.resolve()
    target_r = target.resolve()
    if base_r != target_r and base_r not in target_r.parents:
        raise UploadError("Path escapes workspace.")


def extract_zip_to_workspace(scan_id: str, file_bytes: bytes) -> dict:
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise UploadError(f"Zip exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.")

    try:
        zf = zipfile.ZipFile(io.BytesIO(file_bytes))
    except zipfile.BadZipFile:
        raise UploadError("Not a valid .zip file.")

    infolist = zf.infolist()

    # 1. Total Files Limit (Max 500)
    if len(infolist) > 500:
        zf.close()
        raise UploadError(f"Too many files: {len(infolist)} (max 500)")

    dest = scan_dir(scan_id)
    total_uncompressed = 0
    extracted = 0
    file_list: list[dict] = []

    try:
        for info in infolist:
            # 2. Path Length Limit (Max 150 chars)
            if len(info.filename) > 150:
                raise UploadError(f"Path too long: {info.filename[:30]}... (max 150 chars)")

            mode = info.external_attr >> 16
            if (mode & 0o170000) == 0o120000:
                raise UploadError(f"Symlink not allowed: {info.filename!r}")

            rel = _safe_relative_path(info.filename)
            if info.is_dir():
                (dest / rel).mkdir(parents=True, exist_ok=True)
                continue

            total_uncompressed += info.file_size
            # 3. Total Uncompressed Size Limit (Max 50MB)
            if total_uncompressed > 50 * 1024 * 1024:
                raise UploadError("Uncompressed size exceeds 50MB limit")

            if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                raise UploadError(
                    f"Uncompressed size exceeds {MAX_UNCOMPRESSED_BYTES // (1024 * 1024)} MB limit."
                )

            extracted += 1
            if extracted > MAX_FILES:
                raise UploadError(f"Too many files (>{MAX_FILES}).")

            target = dest / rel
            _ensure_inside(dest, target)
            target.parent.mkdir(parents=True, exist_ok=True)

            with zf.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)

            file_list.append({"path": str(rel).replace("\\", "/"), "size": info.file_size})

        if extracted == 0:
            raise UploadError("Zip contained no files.")
    except Exception:
        shutil.rmtree(dest, ignore_errors=True)
        raise
    finally:
        zf.close()

    return {
        "scan_id": scan_id,
        "dir": str(dest),
        "files": file_list,
        "file_count": extracted,
    }


async def save_folder_upload(
    scan_id: str, files: Iterable[UploadFile], paths: Iterable[str]
) -> dict:
    dest = scan_dir(scan_id)
    file_list: list[dict] = []
    total_bytes = 0
    count = 0

    try:
        for f, raw_path in zip(files, paths):
            if len(raw_path) > 150:
                raise UploadError(f"Path too long: {raw_path[:30]}... (max 150 chars)")
            rel = _safe_relative_path(raw_path)
            data = await f.read()
            total_bytes += len(data)
            if total_bytes > MAX_UNCOMPRESSED_BYTES:
                raise UploadError(
                    f"Total size exceeds {MAX_UNCOMPRESSED_BYTES // (1024 * 1024)} MB limit."
                )
            count += 1
            if count > MAX_FILES:
                raise UploadError(f"Too many files (>{MAX_FILES}).")

            target = dest / rel
            _ensure_inside(dest, target)
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "wb") as out:
                out.write(data)
            file_list.append({"path": str(rel).replace("\\", "/"), "size": len(data)})

        if count == 0:
            raise UploadError("No files received.")
    except Exception:
        shutil.rmtree(dest, ignore_errors=True)
        raise

    return {
        "scan_id": scan_id,
        "dir": str(dest),
        "files": file_list,
        "file_count": count,
    }