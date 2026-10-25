# FILE: backend\main.py
from typing import List

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.api.scans import router as scans_router
from backend.api.chat import router as chat_router
from backend.core.config import FRONTEND_DIR, HOST, MAX_UPLOAD_BYTES, PORT
from backend.input_handler.github import validate_github_url
from backend.api.github_scans import router as github_scans_router
from backend.input_handler.uploads import (
    UploadError,
    extract_zip_to_workspace,
    new_scan_id,
    save_folder_upload,
)

app = FastAPI(title="AI Code Guardian", version="1.0.0")
app.include_router(scans_router)
app.include_router(github_scans_router)
app.include_router(chat_router)


@app.get("/health")
def health():
    return {"status": "ok", "app": "AI Code Guardian", "version": "1.0.0"}


@app.get("/")
def root():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "AI Code Guardian API running. frontend/index.html not found."}


class GithubUrlIn(BaseModel):
    url: str


@app.post("/api/input/github/validate")
def validate_github(payload: GithubUrlIn):
    return validate_github_url(payload.url)


@app.post("/api/input/upload/zip")
async def upload_zip(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip allowed (Rule 10: .rar not permitted).")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large.")

    scan_id = new_scan_id()
    try:
        result = extract_zip_to_workspace(scan_id, data)
    except UploadError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "scan_id": result["scan_id"],
        "file_count": result["file_count"],
        "files": result["files"],
    }


@app.post("/api/input/upload/folder")
async def upload_folder(
    files: List[UploadFile] = File(...),
    paths: List[str] = Form(...),
):
    if len(files) != len(paths):
        raise HTTPException(status_code=400, detail="files and paths count mismatch.")
    if not files:
        raise HTTPException(status_code=400, detail="No files received.")

    scan_id = new_scan_id()
    try:
        result = await save_folder_upload(scan_id, files, paths)
    except UploadError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "scan_id": result["scan_id"],
        "file_count": result["file_count"],
        "files": result["files"],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=True)