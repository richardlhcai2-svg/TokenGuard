import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pydantic import BaseModel
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
    SavingsEstimate,
    PerModelSavings,
    OptimizationReport,
    OptimizationAction,
)

logger = logging.getLogger("tokenguard.backend")
router = APIRouter(prefix="/api/v1", tags=["usage"])

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
        total_input_tokens=int(total_input or 0),
        total_output_tokens=int(total_output or 0),
        avg_context_usage=float(avg_ctx) if avg_ctx else None,
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


# ── Savings estimate ────────────────────────────────────────────────────

# Simplified pricing tiers ($/1M tokens input/output) — mirrors proxy/pricing.py
_MODEL_PRICING = {
    # Anthropic
    "claude-opus": (15.0, 75.0),
    "claude-sonnet": (3.0, 15.0),
    "claude-haiku": (0.8, 4.0),
    "claude-fast": (1.5, 7.5),
    "claude-": (3.0, 15.0),  # default Claude
    # OpenAI
    "o1": (5.0, 25.0),
    "o3": (10.0, 40.0),
    "o4": (1.1, 4.4),
    "gpt-4.5": (7.5, 30.0),
    "gpt-4.1": (4.0, 16.0),
    "gpt-4.1-mini": (0.4, 1.6),
    "gpt-4.1-nano": (0.1, 0.4),
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
    "gpt-4": (2.5, 10.0),  # default GPT-4
    "gpt-": (2.5, 10.0),
    # Gemini
    "gemini-2.5-pro": (1.25, 15.0),
    "gemini-2.5-flash": (0.15, 1.0),
    "gemini-2.0": (0.15, 0.6),
    "gemini-": (1.0, 2.0),
    # DeepSeek
    "deepseek-r1": (0.55, 2.19),
    "deepseek-v3": (0.27, 1.1),
    "deepseek": (0.5, 2.0),
}

# Cheapest model per task type (model_id prefix)
_CHEAPEST_BY_TASK = {
    "documentation": "claude-haiku",
    "testing": "gpt-4.1-nano",
    "code_generation": "gpt-4.1-mini",
    "debugging": "claude-sonnet",
    "refactoring": "gpt-4.1",
    "architectural": "claude-sonnet",
    "general": "claude-fast",
}


def _match_pricing(model_name: str) -> tuple[float, float] | None:
    """Look up ($/1M input, $/1M output) for a model name via prefix match."""
    if not model_name:
        return None
    mn = model_name.lower()
    # Try longest prefix first
    matches = [(k, v) for k, v in _MODEL_PRICING.items() if k != "__default__" and mn.startswith(k)]
    if matches:
        k, v = max(matches, key=lambda x: len(x[0]))
        return (float(v[0]), float(v[1]))
    return None


@router.get("/dashboard/savings", response_model=SavingsEstimate)
async def savings_estimate(
    db: AsyncSession = Depends(get_async_db),
    days: int = Query(default=30, ge=1, le=365),
):
    """Estimate savings by using cheapest suitable model for each task."""
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)

    rows = await db.execute(
        select(
            UsageRecord.model_name,
            UsageRecord.provider,
            UsageRecord.task_type,
            UsageRecord.cost_usd,
            UsageRecord.input_tokens,
            UsageRecord.output_tokens,
        )
        .where(UsageRecord.started_at >= start)
        .order_by(UsageRecord.model_name)
    )
    records = rows.fetchall()

    if not records:
        return SavingsEstimate(
            total_actual_cost_usd=Decimal("0"),
            total_alternative_cost_usd=Decimal("0"),
            total_savings_usd=Decimal("0"),
            savings_pct=0.0,
            per_model=[],
        )

    # Aggregate by (model_name, task_type)
    from collections import defaultdict
    buckets: dict[tuple[str, str], list] = defaultdict(list)
    for r in records:
        key = (r.model_name or "unknown", r.task_type or "general")
        buckets[key].append(r)

    total_actual = Decimal("0")
    total_alternative = Decimal("0")
    per_model: list[PerModelSavings] = []

    for (model_name, task_type), recs in buckets.items():
        actual_cost = sum(r.cost_usd for r in recs)
        req_count = len(recs)
        total_input = sum(int(r.input_tokens or 0) for r in recs)
        total_output = sum(int(r.output_tokens or 0) for r in recs)

        # Find cheapest suitable model for this task type
        cheapest_prefix = _CHEAPEST_BY_TASK.get(task_type, "general")
        pricing = _match_pricing(cheapest_prefix)
        if pricing is None:
            pricing = (0.003, 0.015)  # fallback $/1M

        alt_cost = Decimal(str(
            (total_input / 1_000_000) * pricing[0] + (total_output / 1_000_000) * pricing[1]
        ))

        savings = actual_cost - alt_cost
        savings_pct = float(savings / actual_cost * 100) if actual_cost > 0 else 0.0

        total_actual += actual_cost
        total_alternative += alt_cost

        per_model.append(PerModelSavings(
            model_name=model_name,
            provider=recs[0].provider,
            actual_cost_usd=actual_cost,
            alternative_cost_usd=alt_cost,
            savings_usd=savings,
            savings_pct=round(savings_pct, 2),
            request_count=req_count,
            recommended_model=cheapest_prefix,
        ))

    total_savings = total_actual - total_alternative
    savings_pct = float(total_savings / total_actual * 100) if total_actual > 0 else 0.0

    return SavingsEstimate(
        total_actual_cost_usd=total_actual,
        total_alternative_cost_usd=total_alternative,
        total_savings_usd=total_savings,
        savings_pct=round(savings_pct, 2),
        per_model=per_model,
    )


# ── Personalized recommendations ────────────────────────────────────────

class ModelRecommendation(BaseModel):
    current_model: str
    recommended_model: str
    provider: Optional[str] = None
    saving_pct: float
    reason: str
    request_count: int
    total_cost_usd: Decimal


@router.get("/dashboard/recommendations", response_model=list[ModelRecommendation])
async def model_recommendations(
    db: AsyncSession = Depends(get_async_db),
    days: int = Query(default=30, ge=1, le=365),
):
    """Recommend cheaper models based on actual usage patterns."""
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)

    rows = await db.execute(
        select(
            UsageRecord.model_name,
            UsageRecord.provider,
            UsageRecord.task_type,
            UsageRecord.cost_usd,
            UsageRecord.input_tokens,
            UsageRecord.output_tokens,
        )
        .where(UsageRecord.started_at >= start)
    )
    records = rows.fetchall()

    if not records:
        return []

    # Aggregate by model
    from collections import defaultdict
    buckets: dict[str, list] = defaultdict(list)
    for r in records:
        name = r.model_name or "unknown"
        buckets[name].append(r)

    recommendations: list[ModelRecommendation] = []
    for model_name, recs in sorted(buckets.items(), key=lambda x: sum(r.cost_usd for r in x[1]), reverse=True):
        actual_cost = sum(r.cost_usd for r in recs)
        req_count = len(recs)
        total_input = sum(int(r.input_tokens or 0) for r in recs)
        total_output = sum(int(r.output_tokens or 0) for r in recs)
        provider = recs[0].provider
        task_type = recs[0].task_type or "general"

        # Find cheapest suitable model
        cheapest_prefix = _CHEAPEST_BY_TASK.get(task_type, "general")
        current_pricing = _match_pricing(model_name)
        alt_pricing = _match_pricing(cheapest_prefix)

        if current_pricing is None:
            current_pricing = (0.003, 0.015)
        if alt_pricing is None:
            alt_pricing = (0.003, 0.015)

        current_estimated = (total_input / 1_000_000) * current_pricing[0] + (total_output / 1_000_000) * current_pricing[1]
        alt_estimated = (total_input / 1_000_000) * alt_pricing[0] + (total_output / 1_000_000) * alt_pricing[1]

        # Use actual cost for saving calculation
        saving_pct = float((actual_cost - alt_estimated) / actual_cost * 100) if actual_cost > 0 else 0.0

        # Only recommend if there's meaningful saving (>5%)
        if saving_pct > 5.0 and cheapest_prefix != model_name:
            reasons = {
                "documentation": "Documentation tasks need basic reasoning — cheaper models handle it fine",
                "testing": "Test generation requires moderate capability — mid-tier models are sufficient",
                "code_generation": "Code generation benefits from advanced models — but not the most expensive",
                "debugging": "Debugging needs strong reasoning — mid-high tier is the sweet spot",
                "refactoring": "Refactoring requires solid understanding — mid-tier models handle structural changes well",
                "architectural": "System design needs expert reasoning — but top-tier may be overkill",
                "general": "For general tasks, a balanced cost/performance model is usually best",
            }
            reason = reasons.get(task_type, "This model may be overkill for your usage pattern")

            recommendations.append(ModelRecommendation(
                current_model=model_name,
                recommended_model=cheapest_prefix,
                provider=provider,
                saving_pct=round(max(0, saving_pct), 2),
                reason=f"{reason}. Switching to {cheapest_prefix} could save ~{saving_pct:.0f}%.",
                request_count=req_count,
                total_cost_usd=actual_cost,
            ))

    return recommendations[:10]  # Top 10 recommendations


# ── Cost Optimization Report ─────────────────────────────────────────────

@router.get("/dashboard/optimizations", response_model=OptimizationReport)
async def cost_optimizations(
    db: AsyncSession = Depends(get_async_db),
    days: int = Query(default=30, ge=1, le=365),
    min_savings: float = Query(default=1.0, ge=0, description="Minimum $ savings to include"),
):
    """Generate actionable cost optimization suggestions based on usage patterns."""
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)

    rows = await db.execute(
        select(
            UsageRecord.model_name,
            UsageRecord.provider,
            UsageRecord.task_type,
            UsageRecord.cost_usd,
            UsageRecord.input_tokens,
            UsageRecord.output_tokens,
        )
        .where(UsageRecord.started_at >= start)
    )
    records = rows.fetchall()

    if not records:
        return OptimizationReport(
            total_actual_cost_usd=Decimal("0"),
            total_potential_cost_usd=Decimal("0"),
            total_savings_usd=Decimal("0"),
            savings_pct=0.0,
            action_count=0,
            actions=[],
        )

    from collections import defaultdict
    buckets: dict[tuple[str, str], list] = defaultdict(list)
    for r in records:
        key = (r.model_name or "unknown", r.task_type or "general")
        buckets[key].append(r)

    actions: list[OptimizationAction] = []
    for (model_name, task_type), recs in buckets.items():
        actual_cost = sum(r.cost_usd for r in recs)
        req_count = len(recs)
        total_input = sum(int(r.input_tokens or 0) for r in recs)
        total_output = sum(int(r.output_tokens or 0) for r in recs)
        provider = recs[0].provider

        # Find cheapest suitable model
        cheapest_prefix = _CHEAPEST_BY_TASK.get(task_type, "general")
        current_pricing = _match_pricing(model_name)
        alt_pricing = _match_pricing(cheapest_prefix)

        if current_pricing is None:
            current_pricing = (0.003, 0.015)
        if alt_pricing is None:
            alt_pricing = (0.003, 0.015)

        # Compare current vs alternative cost using actual token volumes
        alt_cost = Decimal(str(
            (total_input / 1_000_000) * alt_pricing[0] + (total_output / 1_000_000) * alt_pricing[1]
        ))

        savings = actual_cost - alt_cost
        if savings <= 0:
            continue

        savings_pct = float(savings / actual_cost * 100) if actual_cost > 0 else 0.0

        # Skip if below min savings threshold
        if float(savings) < min_savings:
            continue

        # Determine priority
        if float(savings) >= 50:
            priority = "high"
        elif float(savings) >= 10:
            priority = "medium"
        else:
            priority = "low"

        actions.append(OptimizationAction(
            current_model=model_name,
            recommended_model=cheapest_prefix,
            task_type=task_type,
            provider=provider,
            actual_cost_usd=actual_cost,
            potential_cost_usd=alt_cost,
            savings_usd=savings,
            savings_pct=round(savings_pct, 2),
            request_count=req_count,
            action="downgrade",
            priority=priority,
        ))

    # Sort by savings (high to low)
    actions.sort(key=lambda a: float(a.savings_usd), reverse=True)
    total_actual = sum(a.actual_cost_usd for a in actions)
    total_potential = sum(a.potential_cost_usd for a in actions)
    total_savings = total_actual - total_potential
    savings_pct = float(total_savings / total_actual * 100) if total_actual > 0 else 0.0

    return OptimizationReport(
        total_actual_cost_usd=total_actual,
        total_potential_cost_usd=total_potential,
        total_savings_usd=total_savings,
        savings_pct=round(savings_pct, 2),
        action_count=len(actions),
        actions=actions,
    )
