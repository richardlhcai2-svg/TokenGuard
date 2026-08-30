"""Usage records listing and enhanced dashboard overview."""

import calendar
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_org
from app.core.database import get_async_db
from app.models.usage import UsageRecord
from app.models.member import OrganizationMember
from app.schemas import (
    UsageRecordOut,
    UsageRecordsResponse,
    DashboardOverview,
    CostTrendPoint,
    ToolBreakdown,
    MemberRanking,
    AnomalyEntry,
    BudgetStatus,
)

router = APIRouter(prefix="/api/v1", tags=["usage"])


# ── Usage records listing ─────────────────────────────────────────────

@router.get("/usage/records", response_model=UsageRecordsResponse)
async def list_usage_records(
    org = Depends(get_current_org),
    db: AsyncSession = Depends(get_async_db),
    start_date: str = Query(default=None),
    end_date: str = Query(default=None),
    user_id: str = Query(default=None),
    tool: str = Query(default=None),
    model: str = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="started_at"),
    order: str = Query(default="desc"),
):
    q = select(UsageRecord).where(UsageRecord.organization_id == org.id)

    if start_date:
        q = q.where(UsageRecord.started_at >= start_date)
    if end_date:
        q = q.where(UsageRecord.started_at <= end_date)
    if user_id:
        q = q.where(UsageRecord.user_id == user_id)
    if tool:
        q = q.where(UsageRecord.tool_name == tool)
    if model:
        q = q.where(UsageRecord.model_name == model)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()

    sort_col = getattr(UsageRecord, sort_by, UsageRecord.started_at)
    q = q.order_by(sort_col.desc() if order == "desc" else sort_col.asc())
    q = q.offset((page - 1) * per_page).limit(per_page)

    rows = (await db.execute(q)).scalars().all()
    return UsageRecordsResponse(
        records=[UsageRecordOut.model_validate(r) for r in rows],
        total=int(total or 0),
    )


# ── Enhanced dashboard overview ───────────────────────────────────────

@router.get("/dashboard/overview", response_model=DashboardOverview)
async def dashboard_overview(
    org = Depends(get_current_org),
    db: AsyncSession = Depends(get_async_db),
    days: int = Query(default=30, ge=1, le=365),
):
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    days_passed = max(now.day, 1)

    # Total cost this month
    month_cost = (await db.execute(
        select(func.coalesce(func.sum(UsageRecord.cost_usd), 0)).where(
            UsageRecord.organization_id == org.id,
            UsageRecord.started_at >= month_start,
        )
    )).scalar() or Decimal("0")

    # Predicted monthly
    daily_avg = month_cost / days_passed
    days_in_month_total = calendar.monthrange(now.year, now.month)[1]
    predicted = daily_avg * days_in_month_total

    # Mom change (compare to previous month)
    prev_start = month_start - (now - month_start)
    prev_cost = (await db.execute(
        select(func.coalesce(func.sum(UsageRecord.cost_usd), 0)).where(
            UsageRecord.organization_id == org.id,
            UsageRecord.started_at >= prev_start,
            UsageRecord.started_at < month_start,
        )
    )).scalar() or Decimal("0")
    mom_pct = float((month_cost - prev_cost) / prev_cost) if prev_cost and prev_cost > 0 else 0.0

    # Active tools count
    active_tools = (await db.execute(
        select(func.count(func.distinct(UsageRecord.tool_name))).where(
            UsageRecord.organization_id == org.id
        )
    )).scalar() or 0

    # Daily trend
    trend_rows = (await db.execute(
        select(
            func.date(UsageRecord.started_at).label("d"),
            func.coalesce(func.sum(UsageRecord.cost_usd), 0).label("cost"),
            func.coalesce(func.sum(UsageRecord.input_tokens), 0).label("tokens"),
        ).where(
            UsageRecord.organization_id == org.id,
            UsageRecord.started_at >= now - timedelta(days=days),
        ).group_by(func.date(UsageRecord.started_at)).order_by("d")
    )).fetchall()
    daily_trend = [
        CostTrendPoint(date=str(r.d), cost=r.cost, tokens=int(r.tokens))
        for r in trend_rows
    ]

    # Tool breakdown
    tool_rows = (await db.execute(
        select(
            UsageRecord.tool_name,
            func.coalesce(func.sum(UsageRecord.cost_usd), 0).label("tc"),
        ).where(
            UsageRecord.organization_id == org.id,
            UsageRecord.started_at >= month_start,
        ).group_by(UsageRecord.tool_name)
    )).fetchall()
    tool_breakdown = []
    for r in tool_rows:
        pct = float(r.tc / month_cost) if month_cost and month_cost > 0 else 0
        tool_breakdown.append(ToolBreakdown(tool=r.tool_name or "unknown", cost_usd=r.tc, pct=pct))

    # Member ranking
    member_rows = (await db.execute(
        select(
            UsageRecord.user_id,
            func.coalesce(func.sum(UsageRecord.cost_usd), 0).label("tc"),
            func.coalesce(func.avg(UsageRecord.context_usage_pct), 0).label("ac"),
        ).where(
            UsageRecord.organization_id == org.id,
            UsageRecord.started_at >= month_start,
        ).group_by(UsageRecord.user_id).order_by(func.sum(UsageRecord.cost_usd).desc()).limit(10)
    )).fetchall()
    member_ranking = [
        MemberRanking(
            user_id=str(r.user_id),
            name=str(r.user_id)[:8],
            cost_usd=r.tc,
            primary_tool="claude_code",
        )
        for r in member_rows
    ]

    # Recent anomalies (sessions > $20)
    anomaly_rows = (await db.execute(
        select(
            UsageRecord.user_id,
            UsageRecord.tool_name,
            UsageRecord.model_name,
            UsageRecord.cost_usd,
            UsageRecord.started_at,
        ).where(
            UsageRecord.organization_id == org.id,
            UsageRecord.cost_usd > 20,
            UsageRecord.started_at >= month_start,
        ).order_by(UsageRecord.cost_usd.desc()).limit(10)
    )).fetchall()
    anomalies = [
        AnomalyEntry(
            user_name=str(r.user_id)[:8],
            tool=r.tool_name or "unknown",
            model=r.model_name or "unknown",
            cost_usd=r.cost_usd,
            occurred_at=r.started_at,
            type="high_cost_session",
        )
        for r in anomaly_rows
    ]

    return DashboardOverview(
        total_cost_usd=month_cost,
        predicted_monthly_usd=predicted,
        mom_change_pct=mom_pct,
        active_tools_count=active_tools,
        daily_trend=daily_trend,
        tool_breakdown=tool_breakdown,
        member_ranking=member_ranking,
        recent_anomalies=anomalies,
    )


# ── Budget status ─────────────────────────────────────────────────────

@router.get("/budget/status", response_model=BudgetStatus)
async def budget_status(
    org = Depends(get_current_org),
    db: AsyncSession = Depends(get_async_db),
):
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    days_remaining = days_in_month - now.day

    budget = org.monthly_budget or Decimal("0")
    current = (await db.execute(
        select(func.coalesce(func.sum(UsageRecord.cost_usd), 0)).where(
            UsageRecord.organization_id == org.id,
            UsageRecord.started_at >= month_start,
        )
    )).scalar() or Decimal("0")

    usage_pct = float(current / budget) if budget and budget > 0 else 0.0
    predicted = current / max(now.day, 1) * days_in_month

    if usage_pct >= 1.0:
        status = "exceeded"
    elif usage_pct >= 0.9:
        status = "critical"
    elif usage_pct >= 0.7:
        status = "warning"
    else:
        status = "normal"

    return BudgetStatus(
        monthly_limit_usd=budget,
        current_spend_usd=current,
        usage_pct=round(usage_pct, 4),
        predicted_end_usd=predicted,
        days_remaining=max(days_remaining, 0),
        status=status,
    )
