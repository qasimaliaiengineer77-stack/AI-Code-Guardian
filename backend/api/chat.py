import re
import time
import json
from collections import defaultdict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.ai.explainer import AIExplainer, AIExplainerError
from backend.ai.redaction import redact_text, redact_scan_result
from backend.storage.scans import get_scan
from backend.storage.persistent import compute_project_key
from backend.orchestrator.runner import _filter_ignored, _ai_circuit_snapshot, _mark_ai_failed, _reset_ai_circuit

router = APIRouter(prefix="/api/chat", tags=["chat"])

_FENCED_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_BACKTICK_RE = re.compile(r"`{1,2}[^`\n]+?`{1,2}")


def _strip_fenced_blocks(text: str) -> str:
    """Rule 4 enforcement: remove any fenced code the model still emits."""
    if not text:
        return text
    return _FENCED_RE.sub(
        "[code removed - this assistant only explains, it does not provide code]",
        text,
    ).strip()


def _strip_inline_code(text: str) -> str:
    """Rule 4 enforcement: remove inline/backtick code spans (single or double backticks)."""
    if not text:
        return text
    out = _INLINE_BACKTICK_RE.sub(
        "[code removed - this assistant only explains, it does not provide code]",
        text,
    )
    return out.replace("`", "")


class ChatBody(BaseModel):
    scan_id: str
    message: str
    language: str = "en"
    ai_enabled: bool = True

_CHAT_RATE_LIMIT = defaultdict(list)
MAX_CHAT_LEN = 1000
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX = 5

@router.post("")
def chat(body: ChatBody):
    # 1. Rate Limit (5 requests per 60s)
    now = time.time()
    ip = "local"
    _CHAT_RATE_LIMIT[ip] = [t for t in _CHAT_RATE_LIMIT[ip] if now - t < RATE_LIMIT_WINDOW]
    if len(_CHAT_RATE_LIMIT[ip]) >= RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Too many chat requests. Please wait a minute.")
    _CHAT_RATE_LIMIT[ip].append(now)

    if not body.ai_enabled:
        raise HTTPException(status_code=400, detail="AI Assistant is disabled in Settings.")

    # 2. Redact & Truncate user message
    safe_msg = redact_text(body.message)[:MAX_CHAT_LEN]
    if not safe_msg.strip():
        raise HTTPException(status_code=400, detail="Message is empty or invalid.")

    # 3. Fetch scan & filter ignored
    row = get_scan(body.scan_id)
    if not row:
        raise HTTPException(status_code=404, detail="Scan not found.")

    result = row.get("result")
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except Exception:
            result = {}

    safe_result = redact_scan_result(result) if isinstance(result, dict) else {}
    project_key = compute_project_key(body.scan_id)
    issues = safe_result.get("issues", [])
    filtered_issues = _filter_ignored(issues, project_key)

    scan_summary = {
        "total_issues": len(filtered_issues),
        "issues": filtered_issues
    }

    # 4. AI Circuit Breaker
    available, remaining = _ai_circuit_snapshot()
    if not available:
        return {"response": f"AI temporarily unavailable (retry in {remaining}s).", "available": False}

    explainer = AIExplainer()
    if not explainer.available:
        return {"response": "AI is disabled or missing API key. Please configure it in .env.", "available": False}

    # 5. Call AI (No raw errors leaked)
    try:
        reply = explainer.chat(scan_summary, safe_msg, body.language)
        reply = _strip_fenced_blocks(reply)
        reply = _strip_inline_code(reply)
        _reset_ai_circuit()
        return {"response": reply, "available": True}
    except AIExplainerError:
        _mark_ai_failed(Exception("AIExplainerError"))
        raise HTTPException(status_code=500, detail="AI chat failed. Please try again later.")
    except Exception:
        _mark_ai_failed(Exception("UnknownError"))
        raise HTTPException(status_code=500, detail="AI chat failed. Please try again later.")