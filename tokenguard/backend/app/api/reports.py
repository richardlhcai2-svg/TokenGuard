"""ROI reports and data export endpoints."""

import csv
import io
import logging
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_org
from app.core.database import get_async_db
from app.models.usage import UsageRecord
from app.models.member import OrganizationMember
from app.schemas import ROIReport

logger = logging.getLogger("tokenguard.backend")
router = APIRouter(prefix="/api/v1", tags=["reports"])

# Baseline: traditional developer hourly cost and PR time
BASELINE_DEVELOPER_HOURLY = 75  # USD
BASELINE_PR_TIME_HOURS = 4.0   # hours per PR without AI


@router.get("/reports/roi", response_model=ROIReport)
async def roi_report(
    org = Depends(get_current_org),
    db: AsyncSession = Depends(get_async_db),
    month: str = Query(default=None, description="YYYY-MM format"),
):
    """Calculate ROI report for the organization.

    Compares AI costs against time saved via faster PR cycles.
    """
    now = datetime.now(timezone.utc)
    if month:
        year, mo = map(int, month.split("-"))
    else:
        year, mo = now.year, now.month

    month_start = datetime(year, mo, 1, tzinfo=timezone.utc)
    import calendar as cal
    month_end = datetime(year, mo, cal.monthrange(year, mo)[1], 23, 59, 59, tzinfo=timezone.utc)

    # Total AI cost this month
    cost_result = (await db.execute(
        select(func.coalesce(func.sum(UsageRecord.cost_usd), 0)).where(
            UsageRecord.organization_id == org.id,
            UsageRecord.started_at >= month_start,
            UsageRecord.started_at <= month_end,
        )
    )).scalar() or Decimal("0")

    # Total requests and tokens
    req_result = await db.execute(
        select(func.count(UsageRecord.id)).where(
            UsageRecord.organization_id == org.id,
            UsageRecord.started_at >= month_start,
            UsageRecord.started_at <= month_end,
        )
    )
    total_requests = req_result.scalar() or 0

    # Estimate PRs: assume ~10 AI sessions per PR on average
    pr_count = max(total_requests // 10, 1)

    # Time saved estimate: each AI session saves ~30% vs manual coding
    # Average session duration estimate from token throughput
    avg_cost_per_request = float(cost_result) / total_requests if total_requests > 0 else 0

    # Estimate time saved: faster coding = ~2 hours saved per PR for AI assistance
    hours_saved_per_pr = 2.0
    total_time_saved = pr_count * hours_saved_per_pr

    # Value of time saved
    time_value = total_time_saved * BASELINE_DEVELOPER_HOURLY

    # ROI calculation
    roi_multiple = float(time_value / cost_result) if cost_result and cost_result > 0 else 0.0

    # Cost breakdown by tool
    tool_rows = await db.execute(
        select(
            UsageRecord.tool_name,
            func.coalesce(func.sum(UsageRecord.cost_usd), 0).label("tc"),
        ).where(
            UsageRecord.organization_id == org.id,
            UsageRecord.started_at >= month_start,
            UsageRecord.started_at <= month_end,
        ).group_by(UsageRecord.tool_name)
    )
    cost_breakdown = {}
    for r in tool_rows.fetchall():
        cost_breakdown[r.tool_name or "unknown"] = float(r.tc)

    # Optimization suggestions
    suggestions = []
    if cost_result > 100:
        suggestions.append({
            "type": "high_cost",
            "message": "Monthly spend exceeds $100. Consider setting up budget alerts.",
            "potential_saving_pct": 20,
        })
    if total_requests > 1000:
        suggestions.append({
            "type": "high_volume",
            "message": "High request volume. Batch operations to reduce API calls.",
            "potential_saving_pct": 15,
        })

    # Check for expensive models that could be downgraded for simple tasks
    suggestions.append({
        "type": "model_optimization",
        "message": "Use cheaper models for documentation/testing tasks, reserve premium for debugging.",
        "potential_saving_pct": 30,
    })

    return ROIReport(
        month=f"{year}-{mo:02d}",
        ai_cost_usd=cost_result,
        pr_count=pr_count,
        avg_pr_time_hours=round(BASELINE_PR_TIME_HOURS - hours_saved_per_pr, 1),
        baseline_pr_time_hours=BASELINE_PR_TIME_HOURS,
        time_saved_hours=Decimal(str(round(total_time_saved, 1))),
        time_value_usd=Decimal(str(round(time_value, 2))),
        roi_multiple=round(roi_multiple, 2),
        cost_breakdown=cost_breakdown,
        optimization_suggestions=suggestions,
    )


@router.get("/reports/export")
async def export_report(
    org = Depends(get_current_org),
    db: AsyncSession = Depends(get_async_db),
    format: str = Query(default="csv", description="Export format: csv or json"),
    start_date: str = Query(default=None),
    end_date: str = Query(default=None),
):
    """Export usage data as CSV or JSON."""
    q = select(UsageRecord).where(
        UsageRecord.organization_id == org.id,
    )
    if start_date:
        q = q.where(UsageRecord.started_at >= start_date)
    if end_date:
        q = q.where(UsageRecord.started_at <= end_date)

    rows = (await db.execute(q.order_by(UsageRecord.started_at.desc()))).scalars().all()

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "started_at", "user_id", "tool", "model", "provider",
            "input_tokens", "output_tokens", "cache_creation_tokens",
            "cache_read_tokens", "cost_usd", "session_id",
            "context_usage_pct",
        ])
        for r in rows:
            writer.writerow([
                r.started_at, str(r.user_id), r.tool_name, r.model_name,
                r.provider, r.input_tokens, r.output_tokens,
                r.cache_creation_tokens, r.cache_read_tokens,
                r.cost_usd, r.session_id, r.context_usage_pct,
            ])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=tokenguard_export_{now_iso()}.csv"},
        )

    # JSON export
    import json
    data = []
    for r in rows:
        data.append({
            "started_at": str(r.started_at),
            "user_id": str(r.user_id),
            "tool_name": r.tool_name,
            "model_name": r.model_name,
            "provider": r.provider,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "cache_creation_tokens": r.cache_creation_tokens,
            "cache_read_tokens": r.cache_read_tokens,
            "cost_usd": str(r.cost_usd),
            "session_id": r.session_id,
            "context_usage_pct": str(r.context_usage_pct) if r.context_usage_pct else None,
        })
    return Response(
        content=json.dumps(data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=tokenguard_export_{now_iso()}.json"},
    )


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
