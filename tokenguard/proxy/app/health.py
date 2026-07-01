import logging
import os

import httpx
from fastapi import APIRouter, HTTPException

logger = logging.getLogger("tokenguard.proxy")

router = APIRouter()


@router.get("")
async def health_check():
    """Health endpoint with optional Anthropic connectivity test."""
    result = {"status": "healthy", "service": "tokenguard-proxy"}

    # Check Anthropic connectivity
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "anthropic-version": "2023-06-01",
                    "x-api-key": "should-fail",  # Intentionally invalid key
                },
            )
            # We expect a 401/403 — the important thing is connectivity
            result["anthropic_reachable"] = resp.status_code in (401, 403, 200)
    except Exception:
        result["anthropic_reachable"] = False
        result["status"] = "degraded"

    status_code = 503 if result["status"] == "unhealthy" else 200
    return result, status_code
