import asyncio
import json
import logging
import os
import time
from typing import Optional

import httpx
from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import StreamingResponse

from app.utils import (
    estimate_input_tokens,
    get_model_info,
    should_trigger_warning,
)

logger = logging.getLogger("tokenguard.proxy")

router = APIRouter()

ANTHROPIC_API_URL = "https://api.anthropic.com"
TG_KEY_HEADER = "x-tokenguard-key"


async def _save_usage_async(usage: dict, session_id: Optional[str]):
    """Async fire-and-forget usage save to backend."""
    try:
        backend_url = os.getenv("BACKEND_URL", "http://backend:8000")
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{backend_url}/api/v1/usage",
                json={**usage, "session_id": session_id},
                headers={
                    "Content-Type": "application/json",
                    "x-tokenguard-key": os.getenv("PROXY_SECRET", ""),
                },
            )
    except Exception:
        logger.exception("Failed to save usage data")


async def _extract_and_save_usage(
    response_body: bytes,
    request_body: dict,
    model_info: dict,
    start_time: float,
):
    """Extract usage stats from response and save to backend."""
    try:
        usage = _parse_usage_from_response(response_body, model_info)
        if usage:
            usage["duration_ms"] = int((time.time() - start_time) * 1000)
            session_id = request_body.get("session_id")
            await _save_usage_async(usage, session_id)
    except Exception:
        logger.exception("Failed to extract usage from response")


def _parse_usage_from_response(
    response_body: bytes, model_info: dict
) -> Optional[dict]:
    """Parse usage stats from Anthropic response body."""
    try:
        data = json.loads(response_body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    usage = data.get("usage", {})
    if not usage:
        return None

    context_window = model_info["context_window"]
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cache_creation = usage.get("cache_creation_input_tokens", 0)
    cache_read = usage.get("cache_read_input_tokens", 0)

    total_input = input_tokens + cache_creation + cache_read
    pct = (total_input + output_tokens) / context_window if context_window else 0

    return {
        "model_name": model_info["model_name"],
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_creation_tokens": cache_creation,
        "cache_read_tokens": cache_read,
        "context_usage_pct": round(pct, 4),
        "context_warning": should_trigger_warning(pct),
    }


@router.post("/{path:path}")
async def proxy_request(request: Request, path: str):
    """Core transparent proxy handler — forwards to Anthropic API."""
    tg_key = request.headers.get(TG_KEY_HEADER)
    if not tg_key:
        raise HTTPException(status_code=401, detail="Missing x-tokenguard-key header")

    proxy_secret = os.getenv("PROXY_SECRET", "")
    if tg_key != proxy_secret:
        raise HTTPException(status_code=403, detail="Invalid proxy key")

    body_bytes = await request.body()
    try:
        body = json.loads(body_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    upstream_url = f"{ANTHROPIC_API_URL}/{path}"
    headers = dict(request.headers)
    headers.pop(TG_KEY_HEADER, None)
    headers.pop("host", None)

    model_name = body.get("model", "unknown")
    model_info = get_model_info(model_name)
    start_time = time.time()
    is_streaming = body.get("stream", False)

    async with httpx.AsyncClient(timeout=300.0) as client:
        async with client.stream(
            "POST",
            upstream_url,
            headers=headers,
            content=body_bytes,
        ) as response:
            response_headers = dict(response.headers)

            if is_streaming:
                chunks: list[bytes] = []
                usage_found = False

                async def chunk_generator():
                    nonlocal usage_found
                    async for chunk in response.aiter_bytes():
                        chunks.append(chunk)
                        yield chunk
                        if not usage_found and b'"usage"' in chunk:
                            usage_found = True

                async def save_after_stream():
                    full_body = b"".join(chunks)
                    if full_body:
                        await _extract_and_save_usage(
                            full_body, body, model_info, start_time
                        )

                asyncio.create_task(save_after_stream())

                return StreamingResponse(
                    chunk_generator(),
                    status_code=response.status_code,
                    headers=response_headers,
                    media_type=response.headers.get(
                        "content-type", "text/event-stream"
                    ),
                )
            else:
                response_body = await response.aread()

                asyncio.create_task(
                    _extract_and_save_usage(
                        response_body, body, model_info, start_time
                    )
                )

                return Response(
                    content=response_body.decode("utf-8"),
                    status_code=response.status_code,
                    headers=response_headers,
                )
