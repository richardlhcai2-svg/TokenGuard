"""Provider-aware proxy dispatcher — routes requests to the correct handler."""

import asyncio
import json
import logging
import os
import time
from typing import Optional

import httpx
from fastapi import APIRouter, Request, Response, HTTPException

logger = logging.getLogger("tokenguard.proxy")

router = APIRouter()

TG_KEY_HEADER = "x-tokenguard-key"


try:
    from tokenguard.storage import UsageStore
    _local_store = UsageStore()
except ImportError:
    _local_store = None


async def _save_usage_async(usage: dict, session_id: Optional[str]):
    """Async fire-and-forget usage save to backend with retry.
    Falls back to local SQLite in standalone mode."""
    backend_url = os.getenv("BACKEND_URL", "http://backend:8000")
    proxy_secret = os.getenv("PROXY_SECRET", "")
    headers = {
        "Content-Type": "application/json",
        "x-tokenguard-key": proxy_secret,
    }
    payload = {**usage, "session_id": session_id}

    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(3):
            try:
                resp = await client.post(
                    f"{backend_url}/internal/usage",
                    json=payload,
                    headers=headers,
                )
                if resp.status_code == 200:
                    return
                logger.warning("Usage save returned %d on attempt %d", resp.status_code, attempt + 1)
            except httpx.TimeoutException:
                logger.warning("Usage save timeout on attempt %d", attempt + 1)
            except Exception:
                logger.warning("Usage save failed on attempt %d", attempt + 1)
            if attempt < 2:
                await asyncio.sleep(0.5 * (2 ** attempt))

    # Fallback to local SQLite when backend is unreachable
    if _local_store is not None:
        try:
            _local_store.save_usage(payload)
            logger.info("Saved usage to local SQLite (fallback)")
        except Exception as e:
            logger.error("Failed to save to local SQLite: %s", e)


def _validate_tokenguard_key(request: Request) -> dict:
    """Extract and validate the x-tokenguard-key header. Returns request headers dict."""
    tg_key = request.headers.get(TG_KEY_HEADER)
    if not tg_key:
        raise HTTPException(status_code=401, detail="Missing x-tokenguard-key header")

    proxy_secret = os.getenv("PROXY_SECRET", "")
    if tg_key != proxy_secret:
        raise HTTPException(status_code=403, detail="Invalid proxy key")

    # Build headers dict, strip the internal auth header
    headers = dict(request.headers)
    headers.pop(TG_KEY_HEADER, None)
    return headers


@router.post("/{path:path}")
async def proxy_request(request: Request, path: str):
    """Route requests to the correct provider handler based on URL path prefix.

    Provider prefixes:
      /anthropic/v1/messages  → Anthropic handler
      /openai/v1/chat/completions  → OpenAI handler
      /gemini/v1beta/models/...  → Gemini handler
      /deepseek/v1/chat/completions  → DeepSeek handler (OpenAI-compatible)

    Legacy: no prefix → defaults to Anthropic (backward compatible).
    """
    headers = _validate_tokenguard_key(request)
    body_bytes = await request.body()
    start_time = time.time()

    # Dispatch by the first path segment
    first_segment = path.split("/")[0] if path else ""

    if first_segment == "anthropic":
        from app.handlers.anthropic import handle
        return await handle(request, path.removeprefix("anthropic/"), body_bytes, headers, start_time)

    elif first_segment == "openai":
        from app.handlers.openai import handle
        return await handle(request, path.removeprefix("openai/"), body_bytes, headers, start_time, provider="openai")

    elif first_segment == "gemini":
        from app.handlers.gemini import handle
        return await handle(request, path.removeprefix("gemini/"), body_bytes, headers, start_time)

    elif first_segment == "deepseek":
        from app.handlers.openai import handle
        return await handle(request, path.removeprefix("deepseek/"), body_bytes, headers, start_time, provider="deepseek")

    else:
        # Legacy: no provider prefix → assume Anthropic
        from app.handlers.anthropic import handle
        return await handle(request, path, body_bytes, headers, start_time)
