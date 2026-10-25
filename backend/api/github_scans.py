"""GitHub-sourced scan endpoint — POST /api/scans/from-github.

Flow:
1. rate-limit check (per client host, sliding 60s window)
2. acquire download semaphore (caps concurrent downloads at 2)
3. save_scan(status='queued')
4. download_github_zip (stdlib; https+host+size+timeout capped — 9A)
5. extract_zip_to_workspace (path traversal + zip bomb guarded — STEP 2)
6. delete github.zip after successful extraction
7. return scan_id; frontend then calls POST /{id}/run + polls (STEP 8)

Any failure: drop DB row + rmtree workspace, release semaphore.

Concurrency: from_github is sync def -> FastAPI threadpool. Semaphore
prevents 5 concurrent 60s-long downloads from stacking up threads.
"""
from __future__ import annotations

import shutil
import threading
from collections import defaultdict, deque
from pathlib import Path
from time import monotonic
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..core.config import WORKSPACE_DIR
from ..input_handler.github_fetch import GithubFetchError, download_github_zip
from ..input_handler.uploads import (
    UploadError,
    extract_zip_to_workspace,
    new_scan_id,
)
from ..storage.scans import delete_scan, save_scan

router = APIRouter(prefix="/api/scans", tags=["scans"])

_RATE_LIMIT_WINDOW_SECONDS = 60
_RATE_LIMIT_MAX_REQUESTS = 5
_RATE_LIMIT_LOCK = threading.Lock()
_RATE_LIMIT_BUCKETS: dict = defaultdict(deque)

_DOWNLOAD_SEMAPHORE = threading.Semaphore(2)
_DOWNLOAD_ACQUIRE_TIMEOUT_SECONDS = 5.0


class GithubScanRequest(BaseModel):
    url: str


def _client_key(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _enforce_rate_limit(key: str) -> None:
    """Sliding-window rate limit; raises 429 with Retry-After if exceeded."""
    now = monotonic()
    cutoff = now - _RATE_LIMIT_WINDOW_SECONDS
    with _RATE_LIMIT_LOCK:
        bucket = _RATE_LIMIT_BUCKETS[key]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= _RATE_LIMIT_MAX_REQUESTS:
            retry = max(1, int(_RATE_LIMIT_WINDOW_SECONDS - (now - bucket[0])) + 1)
            raise HTTPException(
                status_code=429,
                detail=f"Too many GitHub scan requests. Retry in {retry}s.",
                headers={"Retry-After": str(retry)},
            )
        bucket.append(now)


def _source_ref(url: str) -> str:
    try:
        parts = [p for p in urlparse(url).path.split("/") if p]
        if len(parts) >= 2:
            repo = parts[1]
            if repo.endswith(".git"):
                repo = repo[:-4]
            return f"{parts[0]}/{repo}"
    except Exception:
        pass
    return url[:100]


def _rm_workspace(scan_id: str) -> None:
    try:
        d = Path(WORKSPACE_DIR) / scan_id
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
    except Exception:
        pass


def _drop_row(scan_id: str) -> None:
    try:
        delete_scan(scan_id)
    except Exception:
        pass


def _do_download_and_extract(body: GithubScanRequest) -> dict:
    """Runs under the download semaphore; every failure cleans up."""
    scan_id = new_scan_id()
    zip_path = Path(WORKSPACE_DIR) / scan_id / "github.zip"
    source_ref = _source_ref(body.url)

    try:
        save_scan(
            scan_id,
            source="github",
            source_ref=source_ref,
            status="queued",
        )
    except Exception:
        _rm_workspace(scan_id)
        raise HTTPException(status_code=500, detail="Failed to create scan record.")

    try:
        download_github_zip(body.url, zip_path)
    except GithubFetchError as e:
        _drop_row(scan_id)
        _rm_workspace(scan_id)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        _drop_row(scan_id)
        _rm_workspace(scan_id)
        raise HTTPException(status_code=500, detail="Download failed.")

    try:
        data = zip_path.read_bytes()
    except OSError:
        _drop_row(scan_id)
        _rm_workspace(scan_id)
        raise HTTPException(status_code=500, detail="Downloaded zip could not be read.")

    try:
        extracted = extract_zip_to_workspace(scan_id, data)
    except UploadError as e:
        _drop_row(scan_id)
        _rm_workspace(scan_id)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        _drop_row(scan_id)
        _rm_workspace(scan_id)
        raise HTTPException(status_code=500, detail="Extraction failed.")

    try:
        zip_path.unlink(missing_ok=True)
    except OSError:
        pass

    return {
        "scan_id": scan_id,
        "status": "queued",
        "source_ref": source_ref,
        "file_count": extracted.get("file_count", 0),
    }


@router.post("/from-github")
def from_github(body: GithubScanRequest, request: Request):
    _enforce_rate_limit(_client_key(request))

    acquired = _DOWNLOAD_SEMAPHORE.acquire(
        timeout=_DOWNLOAD_ACQUIRE_TIMEOUT_SECONDS
    )
    if not acquired:
        raise HTTPException(
            status_code=503,
            detail=(
                "Server busy: too many concurrent GitHub downloads. "
                "Try again shortly."
            ),
        )
    try:
        return _do_download_and_extract(body)
    finally:
        _DOWNLOAD_SEMAPHORE.release()