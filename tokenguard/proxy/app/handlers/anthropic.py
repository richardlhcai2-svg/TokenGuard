"""Anthropic/Claude provider handler."""

import asyncio
import json
import os
import logging
from typing import Optional

import httpx
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse, Response

from ..pricing import get_model_cost, get_context_window
from ..utils import should_trigger_warning, extract_project_name

logger = logging.getLogger("tokenguard.proxy.anthropic")

def _resolve_upstream_url() -> str:
    """Resolve Anthropic upstream API URL from config or environment."""
    try:
        from tokenguard import config
        url = config.get("anthropic_api_url")
        if url:
            return url.rstrip("/")
    except Exception:
        try:
            from ... import config
            url = config.get("anthropic_api_url")
            if url:
                return url.rstrip("/")
        except Exception:
            pass

    return os.getenv("ANTHROPIC_API_URL", "https://api.anthropic.com").rstrip("/")


def _resolve_api_key(headers: dict) -> Optional[str]:
    """Resolve Anthropic API key from headers, config, or environment."""
    # 1. Custom x-anthropic-key header
    key = headers.pop("x-anthropic-key", None)
    if key:
        return key

    # 2. Standard x-api-key header
    key = headers.pop("x-api-key", None)
    if key:
        return key

    # 3. Authorization Bearer header (e.g. ccnim)
    auth = headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()

    # 4. Read from tokenguard config (~/.tokenguard/config.json)
    try:
        from tokenguard import config
        cfg_keys = config.get_api_keys()
        if "anthropic" in cfg_keys and cfg_keys["anthropic"]:
            return cfg_keys["anthropic"]
    except Exception:
        try:
            from ... import config
            cfg_keys = config.get_api_keys()
            if "anthropic" in cfg_keys and cfg_keys["anthropic"]:
                return cfg_keys["anthropic"]
        except Exception:
            pass

    # 5. Environment variables
    env_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")
    if env_key:
        return env_key

    # 6. If custom upstream is configured (e.g. local relay / fcc-server), default to passthrough
    upstream = _resolve_upstream_url()
    if "api.anthropic.com" not in upstream:
        return "ccnim"

    return None


async def handle(
    request: Request,
    path: str,
    body_bytes: bytes,
    headers: dict,
    start_time: float,
) -> Response:
    """Handle an Anthropic API request through the proxy."""
    try:
        body = json.loads(body_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    incoming_auth = headers.get("authorization")
    api_key = _resolve_api_key(headers)
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing Anthropic API key. Provide via x-anthropic-key, x-api-key header, or 'tg config anthropic_api_key <key>'",
        )

    upstream_base = _resolve_upstream_url()
    upstream_url = f"{upstream_base}/{path}"
    headers["x-api-key"] = api_key
    if incoming_auth:
        headers["authorization"] = incoming_auth
    elif "api.anthropic.com" not in upstream_base:
        headers["authorization"] = f"Bearer {api_key}"
    headers["anthropic-version"] = headers.get("anthropic-version", "2023-06-01")
    headers.pop("host", None)
    headers.pop("content-length", None)

    model_name = body.get("model", "unknown")
    cost = get_model_cost(model_name, "anthropic")
    context_window = get_context_window(model_name)
    is_streaming = body.get("stream", False)
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
                start_time, session_id, response_headers, body_bytes,
            )
        else:
            async with client:
                response = await client.post(upstream_url, headers=headers, content=body_bytes)
                response_headers = dict(response.headers)
                response_body = response.content
                if response.status_code < 300:
                    _extract_and_save_json(response_body, model_name, cost, context_window, start_time, session_id, prompt_bytes=body_bytes)
                return Response(
                    content=response_body,
                    status_code=response.status_code,
                    headers=response_headers,
                )
    except httpx.RequestError as exc:
        await client.aclose()
        logger.error("Anthropic upstream request failed: %s", exc)
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
    prompt_bytes: Optional[bytes] = None,
) -> StreamingResponse:
    """Handle streaming response — collect chunks and parse SSE usage on stream completion."""
    accumulated_chunks: list[bytes] = []

    async def chunk_generator():
        try:
            async for chunk in response.aiter_bytes():
                accumulated_chunks.append(chunk)
                yield chunk
        finally:
            await response.aclose()
            await client.aclose()
            # Stream completed: extract usage from full SSE stream
            full_body = b"".join(accumulated_chunks)
            if response.status_code < 300 and full_body:
                _extract_and_save_sse(full_body, model_name, cost, context_window, start_time, session_id, prompt_bytes=prompt_bytes)

    return StreamingResponse(
        chunk_generator(),
        status_code=response.status_code,
        headers=response_headers,
        media_type=response.headers.get("content-type", "text/event-stream"),
    )


def _extract_and_save_sse(
    sse_body: bytes,
    model_name: str,
    cost: dict,
    context_window: int,
    start_time: float,
    session_id: Optional[str] = None,
    prompt_bytes: Optional[bytes] = None,
):
    """Parse usage from Anthropic Server-Sent Events stream, with OpenAI-relay fallback."""
    from ..proxy import _save_usage_async

    if not sse_body or not sse_body.strip():
        return

    try:
        text = sse_body.decode("utf-8", errors="replace")
        input_tokens = 0
        output_tokens = 0
        cache_creation = 0
        cache_read = 0
        actual_model = model_name
        delta_chars = 0

        for line in text.split("\n"):
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if not data_str or data_str == "[DONE]":
                continue
            try:
                event = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            # Standard Anthropic event format
            event_type = event.get("type")
            if event_type == "message_start":
                msg = event.get("message", {})
                if "model" in msg:
                    actual_model = msg["model"]
                usage = msg.get("usage", {})
                input_tokens += usage.get("input_tokens", 0)
                cache_creation += usage.get("cache_creation_input_tokens", 0)
                cache_read += usage.get("cache_read_input_tokens", 0)
            elif event_type == "content_block_delta":
                delta = event.get("delta", {})
                text_piece = delta.get("text", "")
                delta_chars += len(text_piece)
            elif event_type == "message_delta":
                usage = event.get("usage", {})
                output_tokens += usage.get("output_tokens", 0)
                if usage.get("input_tokens") and input_tokens == 0:
                    input_tokens = usage.get("input_tokens", 0)

            # OpenAI/Third-party relay format fallback
            if "choices" in event and event["choices"]:
                choice = event["choices"][0]
                delta = choice.get("delta", {})
                delta_chars += len(delta.get("content", "") or "")
                if "usage" in event and event["usage"]:
                    usage = event["usage"]
                    input_tokens = usage.get("prompt_tokens", input_tokens)
                    output_tokens = usage.get("completion_tokens", output_tokens)

        # Fallback estimations if relay did not emit explicit token counts
        if output_tokens == 0 and delta_chars > 0:
            output_tokens = max(1, delta_chars // 4)
        if input_tokens == 0 and prompt_bytes:
            input_tokens = max(10, len(prompt_bytes) // 4)

        if input_tokens == 0 and output_tokens == 0:
            return

        total_input = input_tokens + cache_creation + cache_read
        pct = (total_input + output_tokens) / context_window if context_window else 0

        rate = get_model_cost(actual_model, "anthropic")
        in_rate = rate.get("input_per_k", 0.0030)
        out_rate = rate.get("output_per_k", 0.0150)
        read_rate = rate.get("cache_read_per_k", in_rate * 0.1)
        write_rate = in_rate * 1.25

        input_cost = (input_tokens / 1000) * in_rate
        cache_read_cost = (cache_read / 1000) * read_rate
        cache_write_cost = (cache_creation / 1000) * write_rate
        output_cost = (output_tokens / 1000) * out_rate
        total_cost = round(input_cost + cache_read_cost + cache_write_cost + output_cost, 6)

        project_name = "General"
        if prompt_bytes:
            try:
                p_data = json.loads(prompt_bytes.decode("utf-8", errors="ignore"))
                project_name = extract_project_name(p_data.get("messages"), p_data.get("system"))
            except Exception:
                pass

        usage_payload = {
            "model_name": actual_model,
            "project_name": project_name,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_creation_tokens": cache_creation,
            "cache_read_tokens": cache_read,
            "cost_usd": total_cost,
            "context_usage_pct": round(pct, 4),
            "context_warning": should_trigger_warning(pct),
            "provider": "anthropic",
        }

        asyncio.create_task(_save_usage_async(usage_payload, session_id))
    except Exception:
        logger.exception("Failed to parse Anthropic SSE stream usage")


def _extract_and_save_json(
    response_body: bytes,
    model_name: str,
    cost: dict,
    context_window: int,
    start_time: float,
    session_id: Optional[str] = None,
    prompt_bytes: Optional[bytes] = None,
):
    """Parse usage from Anthropic non-streaming JSON response."""
    from ..proxy import _save_usage_async

    if not response_body or not response_body.strip():
        return

    try:
        try:
            data = json.loads(response_body.decode("utf-8"))
        except Exception:
            # If response is actually SSE formatted or chunked
            _extract_and_save_sse(response_body, model_name, cost, context_window, start_time, session_id, prompt_bytes)
            return

        usage = data.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cache_creation = usage.get("cache_creation_input_tokens", 0)
        cache_read = usage.get("cache_read_input_tokens", 0)
        actual_model = data.get("model", model_name)

        if not usage and "choices" in data:
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

        if input_tokens == 0 and output_tokens == 0:
            if prompt_bytes:
                input_tokens = max(10, len(prompt_bytes) // 4)
            output_tokens = max(1, len(response_body) // 4)

        total_input = input_tokens + cache_creation + cache_read
        pct = (total_input + output_tokens) / context_window if context_window else 0

        rate = get_model_cost(actual_model, "anthropic")
        in_rate = rate.get("input_per_k", 0.0030)
        out_rate = rate.get("output_per_k", 0.0150)
        read_rate = rate.get("cache_read_per_k", in_rate * 0.1)
        write_rate = in_rate * 1.25

        input_cost = (input_tokens / 1000) * in_rate
        cache_read_cost = (cache_read / 1000) * read_rate
        cache_write_cost = (cache_creation / 1000) * write_rate
        output_cost = (output_tokens / 1000) * out_rate
        total_cost = round(input_cost + cache_read_cost + cache_write_cost + output_cost, 6)

        project_name = "General"
        if prompt_bytes:
            try:
                p_data = json.loads(prompt_bytes.decode("utf-8", errors="ignore"))
                project_name = extract_project_name(p_data.get("messages"), p_data.get("system"))
            except Exception:
                pass

        usage_payload = {
            "model_name": actual_model,
            "project_name": project_name,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_creation_tokens": cache_creation,
            "cache_read_tokens": cache_read,
            "cost_usd": total_cost,
            "context_usage_pct": round(pct, 4),
            "context_warning": should_trigger_warning(pct),
            "provider": "anthropic",
        }

        asyncio.create_task(_save_usage_async(usage_payload, session_id))
    except Exception:
        logger.exception("Failed to extract Anthropic JSON usage")

