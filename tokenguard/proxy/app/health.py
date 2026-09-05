import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from .queue import get_usage_queue

logger = logging.getLogger("tokenguard.proxy")

router = APIRouter()


@router.get("")
async def health_check():
    """Health check endpoint with memory queue telemetry."""
    q = get_usage_queue()
    result = {
        "status": "healthy",
        "service": "tokenguard-proxy",
        "queue": q.stats(),
    }
    return JSONResponse(content=result, status_code=200)
