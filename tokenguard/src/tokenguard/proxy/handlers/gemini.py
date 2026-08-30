"""Google Gemini provider handler."""

import asyncio
import json
import os
import logging
from typing import Optional

import httpx
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse, Response

from ..pricing import get_model_cost, get_context_window
from ..utils import should_trigger_warning

logger = logging.getLogger("tokenguard.proxy.gemini")

GEMINI_API_URL = os.getenv("GEMINI_API_URL", "https://generativelanguage.googleapis.com")


def _resolve_api_key(headers: dict) -> Optional[str]:
    """Resolve Gemini API key from headers, config, or environment."""
    key = headers.pop("x-gemini-key", None)
    if key:
        return key

    key = headers.pop("x-goog-api-key", None)
    if key:
        return key

    # Read from tokenguard config (~/.tokenguard/config.json)
    try:
        from tokenguard import config
        cfg_keys = config.get_api_keys()
        if "gemini" in cfg_keys and cfg_keys["gemini"]:
            return cfg_keys["gemini"]
    except Exception:
        try:
            from ... import config
            cfg_keys = config.get_api_keys()
            if "gemini" in cfg_keys and cfg_keys["gemini"]:
                return cfg_keys["gemini"]
        except Exception:
            pass

    # Environment variable
    env_key = os.getenv("GEMINI_API_KEY")
    if env_key:
        return env_key

    return None


async def handle(
    request: Request,
    path: str,
    body_bytes: bytes,
    headers: dict,
    start_time: float,
) -> Response:
    """Handle a Google Gemini API request through the proxy."""
    try:
        body = json.loads(body_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    api_key = _resolve_api_key(headers)
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing Gemini API key. Provide via x-gemini-key, x-goog-api-key header, or 'tg config gemini_api_key <key>'",
        )

    # Gemini uses query param for API key: ?key=API_KEY
    if "?" in path:
        upstream_url = f"{GEMINI_API_URL}/{path}&key={api_key}"
    else:
        upstream_url = f"{GEMINI_API_URL}/{path}?key={api_key}"

    headers.pop("host", None)
    headers.pop("x-goog-api-key", None)

    # Extract model from body or path
    model_name = body.get("model", "")
    if not model_name and "/models/" in path:
        model_part = path.split("/models/")[-1].split(":")[0]
        model_name = model_name or model_part or "unknown"
    if not model_name:
        model_name = "gemini-2.5-pro"

    cost = get_model_cost(model_name, "gemini")
    context_window = get_context_window(model_name)

    is_streaming = body.get("stream", False) or ":streamGenerateContent" in path
    session_id = body.get("session_id")

    client_timeout = httpx.Timeout(60.0, connect=10.0, read=300.0, pool=5.0)
    client = httpx.AsyncClient(timeout=client_timeout)

    try:
        if is_streaming:
            req = client.build_request("POST", upstream_url, headers=headers, content=body_bytes)
            response = await client.send(req, stream=True)
            response_headers = dict(response.headers)
            response_headers.pop("content-length", None)
            return _handle_streaming(
                client, response, model_name, cost, context_window,
                start_time, session_id, response_headers,
            )
        else:
            async with client:
                response = await client.post(upstream_url, headers=headers, content=body_bytes)
                response_headers = dict(response.headers)
                response_body = response.content
                if response.status_code < 300:
                    _extract_and_save_json(response_body, model_name, cost, context_window, start_time, session_id)
                return Response(
                    content=response_body,
                    status_code=response.status_code,
                    headers=response_headers,
                )
    except httpx.RequestError as exc:
        await client.aclose()
        logger.error("Gemini upstream request failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream provider error: {exc}")


def _handle_streaming(
    client: httpx.AsyncClient,
    response: httpx.Response,
    model_name: str,
    cost: dict,
    context_window: int,
    start_time: float,
    session_id: Optional[str],
    response_headers: dict,
) -> StreamingResponse:
    """Handle streaming response for Gemini."""
    accumulated_chunks: list[bytes] = []

    async def chunk_generator():
        try:
            async for chunk in response.aiter_bytes():
                accumulated_chunks.append(chunk)
                yield chunk
        finally:
            await response.aclose()
            await client.aclose()
            full_body = b"".join(accumulated_chunks)
            if response.status_code < 300 and full_body:
                _extract_and_save_stream(
                    full_body, model_name, cost, context_window, start_time, session_id
                )

    return StreamingResponse(
        chunk_generator(),
        status_code=response.status_code,
        headers=response_headers,
        media_type=response.headers.get("content-type", "text/event-stream"),
    )


def _extract_and_save_stream(
    stream_body: bytes,
    model_name: str,
    cost: dict,
    context_window: int,
    start_time: float,
    session_id: Optional[str] = None,
):
    """Parse usage from Gemini stream (SSE or chunk array)."""
    from ..proxy import _save_usage_async

    try:
        text = stream_body.decode("utf-8", errors="replace")
        prompt_tokens = 0
        candidates_tokens = 0
        found_usage = False

        # Try parsing as JSON array first (standard Gemini chunk array)
        try:
            arr = json.loads(text)
            if isinstance(arr, list):
                for item in reversed(arr):
                    meta = item.get("usageMetadata", {})
                    if meta:
                        prompt_tokens = meta.get("promptTokenCount", 0) or 0
                        candidates_tokens = meta.get("candidatesTokenCount", 0) or 0
                        found_usage = True
                        break
        except Exception:
            pass

        # If not parsed as JSON array, parse line by line (SSE stream)
        if not found_usage:
            for line in text.split("\n"):
                line = line.strip()
                if line.startswith("data:"):
                    line = line[5:].strip()
                if not line or line == "[DONE]":
                    continue
                try:
                    obj = json.loads(line)
                    meta = obj.get("usageMetadata", {})
                    if meta:
                        prompt_tokens = meta.get("promptTokenCount", 0) or 0
                        candidates_tokens = meta.get("candidatesTokenCount", 0) or 0
                        found_usage = True
                except Exception:
                    continue

        if not found_usage:
            prompt_tokens = 100
            candidates_tokens = 50

        total_tokens = prompt_tokens + candidates_tokens
        pct = total_tokens / context_window if context_window else 0

        rate = get_model_cost(model_name, "gemini")
        in_rate = rate.get("input_per_k", 0.00010)
        out_rate = rate.get("output_per_k", 0.00040)
        read_rate = rate.get("cache_read_per_k", in_rate * 0.25)

        input_cost = (prompt_tokens / 1000) * in_rate
        output_cost = (candidates_tokens / 1000) * out_rate
        total_cost = round(input_cost + output_cost, 6)

        usage_payload = {
            "model_name": model_name,
            "input_tokens": prompt_tokens,
            "output_tokens": candidates_tokens,
            "cache_creation_tokens": 0,
            "cache_read_tokens": 0,
            "cost_usd": total_cost,
            "context_usage_pct": round(pct, 4),
            "context_warning": should_trigger_warning(pct),
            "provider": "gemini",
        }

        asyncio.create_task(_save_usage_async(usage_payload, session_id))
    except Exception:
        logger.exception("Failed to extract Gemini stream usage")


def _extract_and_save_json(
    response_body: bytes,
    model_name: str,
    cost: dict,
    context_window: int,
    start_time: float,
    session_id: Optional[str] = None,
):
    """Parse usage from Gemini non-streaming JSON response."""
    from ..proxy import _save_usage_async

    try:
        data = json.loads(response_body.decode("utf-8"))
        usage_meta = data.get("usageMetadata", {})
        if not usage_meta:
            logger.debug("No usageMetadata in Gemini response for %s", model_name)
            return

        prompt_tokens = usage_meta.get("promptTokenCount", 0) or 0
        candidates_tokens = usage_meta.get("candidatesTokenCount", 0) or 0
        cached_tokens = usage_meta.get("cachedContentTokenCount", 0) or 0
        total_tokens = prompt_tokens + candidates_tokens
        pct = total_tokens / context_window if context_window else 0

        rate = get_model_cost(model_name, "gemini")
        in_rate = rate.get("input_per_k", 0.00010)
        out_rate = rate.get("output_per_k", 0.00040)
        read_rate = rate.get("cache_read_per_k", in_rate * 0.25)

        uncached_tokens = max(0, prompt_tokens - cached_tokens)
        input_cost = (uncached_tokens / 1000) * in_rate + (cached_tokens / 1000) * read_rate
        output_cost = (candidates_tokens / 1000) * out_rate
        total_cost = round(input_cost + output_cost, 6)

        usage_payload = {
            "model_name": model_name,
            "input_tokens": prompt_tokens,
            "output_tokens": candidates_tokens,
            "cache_creation_tokens": 0,
            "cache_read_tokens": cached_tokens,
            "cost_usd": total_cost,
            "context_usage_pct": round(pct, 4),
            "context_warning": should_trigger_warning(pct),
            "provider": "gemini",
        }

        asyncio.create_task(_save_usage_async(usage_payload, session_id))
    except Exception:
        logger.exception("Failed to extract Gemini JSON usage")

