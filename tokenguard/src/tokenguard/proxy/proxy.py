"""Provider-aware proxy dispatcher with Persistent Connection Pool & Zero-Blocking Queue."""

import asyncio
import logging
import os
import time
from typing import Optional

import httpx
from fastapi import APIRouter, Request, HTTPException

from .handlers.anthropic import handle as handle_anthropic
from .handlers.openai import handle as handle_openai
from .handlers.gemini import handle as handle_gemini
from .queue import enqueue_usage

logger = logging.getLogger("tokenguard.proxy")

router = APIRouter()

TG_KEY_HEADER = "x-tokenguard-key"

_shared_client: Optional[httpx.AsyncClient] = None
_client_loop: Optional[asyncio.AbstractEventLoop] = None


def get_shared_client() -> httpx.AsyncClient:
    """Get or initialize a thread/loop-safe shared httpx connection pool."""
    global _shared_client, _client_loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    needs_new_client = (
        _shared_client is None
        or _shared_client.is_closed
        or (_client_loop is not None and _client_loop is not current_loop)
        or (_client_loop is not None and _client_loop.is_closed())
    )

    if needs_new_client:
        client_timeout = httpx.Timeout(60.0, connect=10.0, read=300.0, pool=10.0)
        limits = httpx.Limits(max_connections=200, max_keepalive_connections=50, keepalive_expiry=30.0)
        _shared_client = httpx.AsyncClient(timeout=client_timeout, limits=limits)
        _client_loop = current_loop

    return _shared_client


async def close_shared_client():
    """Gracefully close the global connection pool on shutdown."""
    global _shared_client, _client_loop
    if _shared_client is not None and not _shared_client.is_closed:
        try:
            await _shared_client.aclose()
        except Exception:
            pass
        _shared_client = None
        _client_loop = None


async def _save_usage_async(usage: dict, session_id: Optional[str] = None):
    """Compatibility wrapper: enqueue to non-blocking memory queue."""
    enqueue_usage(usage, session_id)


def _validate_tokenguard_key(request: Request) -> dict:
    """Extract and validate proxy authentication.
    
    Provides seamless transparent proxying for local AI coding tools (fcc-claude, Claude Code CLI, Cursor, etc.)
    while securely enforcing proxy keys in remote / multi-tenant environments.
    """
    tg_key = request.headers.get(TG_KEY_HEADER)
    proxy_secret = os.getenv("PROXY_SECRET", "")

    auth = request.headers.get("authorization", "")
    has_bearer_token = False

    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if proxy_secret and token == proxy_secret:
            tg_key = token
        elif token:
            has_bearer_token = True

    has_provider_key = (
        bool(request.headers.get("x-api-key"))
        or bool(request.headers.get("x-anthropic-key"))
        or bool(request.headers.get("x-openai-key"))
        or bool(request.headers.get("x-goog-api-key"))
        or bool(request.headers.get("x-deepseek-key"))
        or has_bearer_token
    )

    if tg_key:
        if proxy_secret and tg_key != proxy_secret:
            raise HTTPException(status_code=403, detail="Invalid proxy key")
    elif not has_provider_key:
        if proxy_secret:
            raise HTTPException(status_code=401, detail="Missing proxy key")

    # Build headers dict, strip the internal proxy auth header
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
    client = get_shared_client()

    # Dispatch by the first path segment
    first_segment = path.split("/")[0] if path else ""

    if first_segment == "anthropic":
        return await handle_anthropic(request, path.removeprefix("anthropic/"), body_bytes, headers, start_time, client=client)

    elif first_segment == "openai":
        return await handle_openai(request, path.removeprefix("openai/"), body_bytes, headers, start_time, provider="openai", client=client)

    elif first_segment == "gemini":
        return await handle_gemini(request, path.removeprefix("gemini/"), body_bytes, headers, start_time, client=client)

    elif first_segment == "deepseek":
        return await handle_openai(request, path.removeprefix("deepseek/"), body_bytes, headers, start_time, provider="deepseek", client=client)

    else:
        # Legacy: no provider prefix → assume Anthropic
        return await handle_anthropic(request, path, body_bytes, headers, start_time, client=client)
