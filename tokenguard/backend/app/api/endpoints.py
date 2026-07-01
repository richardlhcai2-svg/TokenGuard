import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.models.usage import UsageRecord
from app.schemas import (
    UsageRecordIn,
    DashboardSummary,
    CostTrendPoint,
    TopModel,
    TopUser,
)

logger = logging.getLogger("tokenguard.backend")
router = APIRouter(prefix="/api/v1", tags=["usage"])

# ── Proxy key dependency ────────────────────────────────────────────────

PROXY_SECRET: Optional[str] = None


def set_proxy_secret(secret: str):
    """Called at startup to configure the proxy secret."""
    global PROXY_SECRET
    PROXY_SECRET = secret


async def validate_proxy_key(x_tokenguard_key: str = Header()):
    """Dependency: reject requests without valid proxy key."""
    if not PROXY_SECRET or x_tokenguard_key != PROXY_SECRET:
        raise HTTPException(status_code=403, detail="Invalid proxy key")


# ── Proxy endpoints (key-protected) ─────────────────────────────────────

proxy_router = APIRouter(tags=["proxy"])


@proxy_router.post("/usage")
async def proxy_usage(
    record: UsageRecordIn,
    db: AsyncSession = Depends(get_async_db),
    _key: str = Depends(validate_proxy_key),
):
    """Called by the proxy — persists usage record."""
    usage = UsageRecord(
        organization_id=record.organization_id,
        user_id=record.user_id,
        tool_name=record.tool_name,
        model_name=record.model_name,
        provider=record.provider,
        input_tokens=record.input_tokens,
        output_tokens=record.output_tokens,
        cache_creation_tokens=record.cache_creation_tokens,
        cache_read_tokens=record.cache_read_tokens,
        cost_usd=record.cost_usd,
        session_id=record.session_id,
        project_name=record.project_name,
        task_type=record.task_type,
        context_window_size=record.context_window_size,
        context_usage_pct=record.context_usage_pct,
        started_at=record.started_at,
        ended_at=record.ended_at,
    )
    db.add(usage)
    await db.commit()
    await db.refresh(usage)
    return {"status": "saved", "id": str(usage.id)}


# ── Public dashboard endpoints ──────────────────────────────────────────

@router.get("/dashboard/summary")
async def dashboard_summary(db: AsyncSession = Depends(get_async_db)):
    """Aggregate dashboard metrics."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    async def _scalar(stmt):
        result = await db.execute(stmt)
        return result.scalar()

    total_cost = await _scalar(
        select(func.coalesce(func.sum(UsageRecord.cost_usd), 0))
    )
    cost_today = await _scalar(
        select(func.coalesce(func.sum(UsageRecord.cost_usd), 0))
        .where(UsageRecord.started_at >= today_start)
    )
    cost_yesterday = await _scalar(
        select(func.coalesce(func.sum(UsageRecord.cost_usd), 0))
        .where(
            UsageRecord.started_at >= today_start - timedelta(days=1),
            UsageRecord.started_at < today_start,
        )
    )
    cost_7 = await _scalar(
        select(func.coalesce(func.sum(UsageRecord.cost_usd), 0))
        .where(UsageRecord.started_at >= today_start - timedelta(days=7))
    )
    cost_30 = await _scalar(
        select(func.coalesce(func.sum(UsageRecord.cost_usd), 0))
        .where(UsageRecord.started_at >= today_start - timedelta(days=30))
    )
    total_req = await _scalar(select(func.count(UsageRecord.id)))
    total_input = await _scalar(
        select(func.coalesce(func.sum(UsageRecord.input_tokens), 0))
    )
    total_output = await _scalar(
        select(func.coalesce(func.sum(UsageRecord.output_tokens), 0))
    )
    avg_ctx = await _scalar(
        select(func.coalesce(func.avg(UsageRecord.context_usage_pct), 0))
    )

    return DashboardSummary(
        total_cost_usd=total_cost or 0,
        total_requests=total_req or 0,
        total_input_tokens=int(total_input.scalar() or 0),
        total_output_tokens=int(total_output.scalar() or 0),
        avg_context_usage=avg_ctx.scalar() or None,
        cost_today=cost_today or 0,
        cost_yesterday=cost_yesterday or 0,
        cost_last_7_days=cost_7 or 0,
        cost_last_30_days=cost_30 or 0,
    )


@router.get("/dashboard/trends")
async def cost_trends(
    db: AsyncSession = Depends(get_async_db),
    days: int = Query(default=30, ge=1, le=365),
):
    """Daily cost and token trends."""
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)

    rows = await db.execute(
        select(
            func.date(UsageRecord.started_at).label("d"),
            func.coalesce(func.sum(UsageRecord.cost_usd), 0).label("cost"),
            func.coalesce(func.sum(UsageRecord.input_tokens), 0).label("tokens"),
        )
        .where(UsageRecord.started_at >= start)
        .group_by(func.date(UsageRecord.started_at))
        .order_by("d")
    )
    return [
        CostTrendPoint(date=str(r.d), cost=r.cost or 0, tokens=int(r.tokens or 0))
        for r in rows.fetchall()
    ]


@router.get("/dashboard/top-models")
async def top_models(
    db: AsyncSession = Depends(get_async_db),
    limit: int = Query(default=10, ge=1, le=100),
):
    """Top models by cost."""
    rows = await db.execute(
        select(
            UsageRecord.model_name,
            func.coalesce(func.sum(UsageRecord.cost_usd), 0).label("total_cost"),
            func.count(UsageRecord.id).label("requests"),
            func.coalesce(func.avg(UsageRecord.context_usage_pct), 0).label("avg_ctx"),
        )
        .group_by(UsageRecord.model_name)
        .order_by(func.sum(UsageRecord.cost_usd).desc())
        .limit(limit)
    )
    return [
        TopModel(
            model_name=r.model_name or "unknown",
            total_cost_usd=r.total_cost or 0,
            total_requests=r.requests or 0,
            avg_context_usage=r.avg_ctx or None,
        )
        for r in rows.fetchall()
    ]


@router.get("/dashboard/top-users")
async def top_users(
    db: AsyncSession = Depends(get_async_db),
    limit: int = Query(default=10, ge=1, le=100),
):
    """Top users by cost."""
    rows = await db.execute(
        select(
            UsageRecord.user_id,
            func.coalesce(func.sum(UsageRecord.cost_usd), 0).label("total_cost"),
            func.count(UsageRecord.id).label("requests"),
        )
        .group_by(UsageRecord.user_id)
        .order_by(func.sum(UsageRecord.cost_usd).desc())
        .limit(limit)
    )
    return [
        TopUser(
            user_id=str(r.user_id),
            user_name=str(r.user_id)[:8],
            total_cost_usd=r.total_cost or 0,
            total_requests=r.requests or 0,
        )
        for r in rows.fetchall()
    ]
