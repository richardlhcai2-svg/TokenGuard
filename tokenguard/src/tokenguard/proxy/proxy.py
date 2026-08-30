"""Provider-aware proxy dispatcher — routes requests to the correct handler."""

import asyncio
import json
import logging
import os
import time
from typing import Optional

import httpx
from fastapi import APIRouter, Request, Response, HTTPException

from .handlers.anthropic import handle as handle_anthropic
from .handlers.openai import handle as handle_openai
from .handlers.gemini import handle as handle_gemini

logger = logging.getLogger("tokenguard.proxy")

router = APIRouter()

TG_KEY_HEADER = "x-tokenguard-key"

_local_store = None


def _get_local_store():
    global _local_store
    if _local_store is None:
        try:
            from tokenguard.storage import UsageStore
            _local_store = UsageStore()
        except ImportError:
            try:
                from ..storage import UsageStore
                _local_store = UsageStore()
            except Exception:
                _local_store = None
    return _local_store


def _get_config():
    try:
        from tokenguard import config
        return config
    except Exception:
        try:
            from ... import config
            return config
        except Exception:
            return None


async def _save_usage_async(usage: dict, session_id: Optional[str]):
    """Async fire-and-forget usage save.
    Always saves instantly to local SQLite, and syncs to backend if configured."""
    payload = {**usage, "session_id": session_id}

    # 1. Always save instantly to local SQLite store
    local_store = _get_local_store()
    if local_store is not None:
        try:
            local_store.save_usage(payload)
        except Exception as e:
            logger.error("Failed to save to local SQLite: %s", e)

    # 2. If running with a remote backend, sync asynchronously
    backend_url = os.getenv("BACKEND_URL")
    if backend_url and "backend:8000" not in backend_url:
        proxy_secret = os.getenv("PROXY_SECRET", "")
        headers = {
            "Content-Type": "application/json",
            "x-tokenguard-key": proxy_secret,
        }
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                await client.post(f"{backend_url}/internal/usage", json=payload, headers=headers)
        except Exception:
            pass


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

    # Dispatch by the first path segment
    first_segment = path.split("/")[0] if path else ""

    if first_segment == "anthropic":
        return await handle_anthropic(request, path.removeprefix("anthropic/"), body_bytes, headers, start_time)

    elif first_segment == "openai":
        return await handle_openai(request, path.removeprefix("openai/"), body_bytes, headers, start_time, provider="openai")

    elif first_segment == "gemini":
        return await handle_gemini(request, path.removeprefix("gemini/"), body_bytes, headers, start_time)

    elif first_segment == "deepseek":
        return await handle_openai(request, path.removeprefix("deepseek/"), body_bytes, headers, start_time, provider="deepseek")

    else:
        # Legacy: no provider prefix → assume Anthropic
        return await handle_anthropic(request, path, body_bytes, headers, start_time)
