"""OpenAI-compatible provider handler (OpenAI, DeepSeek)."""

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

logger = logging.getLogger("tokenguard.proxy.openai")

UPSTREAM_URLS = {
    "openai": os.getenv("OPENAI_API_URL", "https://api.openai.com"),
    "deepseek": os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com"),
}

KEY_HEADERS = {
    "openai": "x-openai-key",
    "deepseek": "x-deepseek-key",
}


def _resolve_api_key(headers: dict, provider: str) -> Optional[str]:
    """Resolve API key from headers, config, or environment."""
    key_header = KEY_HEADERS.get(provider, f"x-{provider}-key")
    key = headers.pop(key_header, None)
    if key:
        return key

    # Check standard Authorization header
    auth = headers.pop("authorization", None) or headers.pop("Authorization", None)
    if auth and auth.startswith("Bearer "):
        bearer_key = auth.removeprefix("Bearer ").strip()
        if bearer_key and not bearer_key.startswith("tg_"):  # ensure not a local proxy key
            return bearer_key

    # Read from tokenguard config (~/.tokenguard/config.json)
    try:
        from tokenguard import config
        cfg_keys = config.get_api_keys()
        if provider in cfg_keys and cfg_keys[provider]:
            return cfg_keys[provider]
    except Exception:
        try:
            from ... import config
            cfg_keys = config.get_api_keys()
            if provider in cfg_keys and cfg_keys[provider]:
                return cfg_keys[provider]
        except Exception:
            pass

    # Environment variable
    env_vars = {
        "openai": "OPENAI_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
    }
    env_var = env_vars.get(provider)
    if env_var and os.getenv(env_var):
        return os.getenv(env_var)

    return None


async def handle(
    request: Request,
    path: str,
    body_bytes: bytes,
    headers: dict,
    start_time: float,
    provider: str = "openai",
) -> Response:
    """Handle an OpenAI-compatible API request (OpenAI, DeepSeek, etc.)."""
    try:
        body = json.loads(body_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    api_key = _resolve_api_key(headers, provider)
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail=f"Missing {provider} API key. Provide via {KEY_HEADERS.get(provider, 'x-api-key')} header, Authorization header, or 'tg config {provider}_api_key <key>'",
        )

    upstream_url = f"{UPSTREAM_URLS[provider]}/{path}"
    headers["Authorization"] = f"Bearer {api_key}"
    headers.pop("host", None)

    model_name = body.get("model", "unknown")
    cost = get_model_cost(model_name, provider)
    context_window = get_context_window(model_name)
    is_streaming = body.get("stream", False)
    session_id = body.get("session_id")

    # If streaming and stream_options not set, request usage in stream if supported
    if is_streaming and isinstance(body, dict) and "stream_options" not in body and provider == "openai":
        try:
            body["stream_options"] = {"include_usage": True}
            body_bytes = json.dumps(body).encode("utf-8")
        except Exception:
            pass

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
                start_time, session_id, provider, response_headers, body,
            )
        else:
            async with client:
                response = await client.post(upstream_url, headers=headers, content=body_bytes)
                response_headers = dict(response.headers)
                response_body = response.content
                if response.status_code < 300:
                    _extract_and_save_json(
                        response_body, model_name, cost, context_window,
                        start_time, session_id, provider,
                    )
                return Response(
                    content=response_body,
                    status_code=response.status_code,
                    headers=response_headers,
                )
    except httpx.RequestError as exc:
        await client.aclose()
        logger.error("%s upstream request failed: %s", provider, exc)
        raise HTTPException(status_code=502, detail=f"Upstream provider error: {exc}")


def _handle_streaming(
    client: httpx.AsyncClient,
    response: httpx.Response,
    model_name: str,
    cost: dict,
    context_window: int,
    start_time: float,
    session_id: Optional[str],
    provider: str,
    response_headers: dict,
    req_body: dict,
) -> StreamingResponse:
    """Handle streaming response for OpenAI/DeepSeek — collect chunks and parse SSE usage on stream completion."""
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
                _extract_and_save_sse(
                    full_body, model_name, cost, context_window, start_time, session_id, provider, req_body
                )

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
    provider: str = "openai",
    req_body: Optional[dict] = None,
):
    """Parse usage from OpenAI/DeepSeek Server-Sent Events stream."""
    from ..proxy import _save_usage_async

    try:
        text = sse_body.decode("utf-8", errors="replace")
        prompt_tokens = 0
        completion_tokens = 0
        actual_model = model_name
        has_explicit_usage = False
        accumulated_text = []

        for line in text.split("\n"):
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if not data_str or data_str == "[DONE]":
                continue
            try:
                chunk_obj = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            if "model" in chunk_obj:
                actual_model = chunk_obj["model"]

            # Check for usage in chunk
            usage = chunk_obj.get("usage")
            if usage:
                prompt_tokens = usage.get("prompt_tokens", 0) or 0
                completion_tokens = usage.get("completion_tokens", 0) or 0
                has_explicit_usage = True

            # Also accumulate delta content for fallback estimation if no usage in stream
            choices = chunk_obj.get("choices", [])
            for c in choices:
                delta = c.get("delta", {})
                if "content" in delta and delta["content"]:
                    accumulated_text.append(delta["content"])

        if not has_explicit_usage:
            # Fallback estimation based on content length
            total_output_chars = sum(len(c) for c in accumulated_text)
            completion_tokens = max(1, total_output_chars // 4) if total_output_chars > 0 else 0

            # Estimate input tokens from request prompt if available
            if req_body and "messages" in req_body:
                from ..utils import estimate_input_tokens
                prompt_tokens = estimate_input_tokens(req_body.get("messages", []), req_body.get("system", []))
            else:
                prompt_tokens = 100

        cached_tokens = (
            (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
            if isinstance(usage, dict) else 0
        ) or (usage.get("prompt_cache_hit_tokens", 0) if isinstance(usage, dict) else 0)

        total_tokens = prompt_tokens + completion_tokens
        pct = total_tokens / context_window if context_window else 0

        rate = get_model_cost(actual_model, provider)
        in_rate = rate.get("input_per_k", 0.0025)
        out_rate = rate.get("output_per_k", 0.0100)
        read_rate = rate.get("cache_read_per_k", in_rate * 0.5)

        uncached_tokens = max(0, prompt_tokens - cached_tokens)
        input_cost = (uncached_tokens / 1000) * in_rate + (cached_tokens / 1000) * read_rate
        output_cost = (completion_tokens / 1000) * out_rate
        total_cost = round(input_cost + output_cost, 6)

        usage_payload = {
            "model_name": actual_model,
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
            "cache_creation_tokens": 0,
            "cache_read_tokens": cached_tokens,
            "cost_usd": total_cost,
            "context_usage_pct": round(pct, 4),
            "context_warning": should_trigger_warning(pct),
            "provider": provider,
        }

        asyncio.create_task(_save_usage_async(usage_payload, session_id))
    except Exception:
        logger.exception("Failed to parse OpenAI/DeepSeek SSE stream usage")


def _extract_and_save_json(
    response_body: bytes,
    model_name: str,
    cost: dict,
    context_window: int,
    start_time: float,
    session_id: Optional[str] = None,
    provider: str = "openai",
):
    """Parse usage from OpenAI/DeepSeek non-streaming JSON response."""
    from ..proxy import _save_usage_async

    try:
        data = json.loads(response_body.decode("utf-8"))
        usage = data.get("usage", {})
        actual_model = data.get("model", model_name)

        if not usage:
            logger.debug("No usage data in %s response for %s", provider, model_name)
            return

        prompt_tokens = usage.get("prompt_tokens", 0) or 0
        completion_tokens = usage.get("completion_tokens", 0) or 0
        cached_tokens = (
            (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
            if isinstance(usage, dict) else 0
        ) or (usage.get("prompt_cache_hit_tokens", 0) if isinstance(usage, dict) else 0)

        total_tokens = prompt_tokens + completion_tokens
        pct = total_tokens / context_window if context_window else 0

        rate = get_model_cost(actual_model, provider)
        in_rate = rate.get("input_per_k", 0.0025)
        out_rate = rate.get("output_per_k", 0.0100)
        read_rate = rate.get("cache_read_per_k", in_rate * 0.5)

        uncached_tokens = max(0, prompt_tokens - cached_tokens)
        input_cost = (uncached_tokens / 1000) * in_rate + (cached_tokens / 1000) * read_rate
        output_cost = (completion_tokens / 1000) * out_rate
        total_cost = round(input_cost + output_cost, 6)

        usage_payload = {
            "model_name": actual_model,
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
            "cache_creation_tokens": 0,
            "cache_read_tokens": cached_tokens,
            "cost_usd": total_cost,
            "context_usage_pct": round(pct, 4),
            "context_warning": should_trigger_warning(pct),
            "provider": provider,
        }

        asyncio.create_task(_save_usage_async(usage_payload, session_id))
    except Exception:
        logger.exception("Failed to extract %s JSON usage", provider)

