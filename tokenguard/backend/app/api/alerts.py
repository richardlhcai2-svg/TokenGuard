import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.models.usage import UsageRecord
from app.models.alerts import AlertRule
from app.schemas import AlertRuleCreate, AlertRuleUpdate, AlertRuleOut

logger = logging.getLogger("tokenguard.backend")
router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


# ── CRUD for alert rules ──────────────────────────────────────────────

@router.get("/")
async def list_alert_rules(
    db: AsyncSession = Depends(get_async_db),
):
    """List all alert rules for the org (org resolved from auth in production)."""
    rows = await db.execute(
        select(AlertRule).order_by(AlertRule.created_at.desc())
    )
    rules = rows.scalars().all()
    return [
        AlertRuleOut.model_validate(r).model_dump()
        for r in rules
    ]


@router.post("/", status_code=201)
async def create_alert_rule(
    body: AlertRuleCreate,
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new alert rule."""
    rule = AlertRule(
        organization_id="00000000-0000-0000-0000-000000000001",  # from auth in production
        rule_type=body.rule_type,
        config=body.config,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return AlertRuleOut.model_validate(rule).model_dump()


@router.patch("/{rule_id}")
async def update_alert_rule(
    rule_id: str,
    body: AlertRuleUpdate,
    db: AsyncSession = Depends(get_async_db),
):
    """Update an alert rule."""
    row = await db.execute(select(AlertRule).where(AlertRule.id == rule_id))
    rule = row.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)

    await db.commit()
    await db.refresh(rule)
    return AlertRuleOut.model_validate(rule).model_dump()


@router.delete("/{rule_id}", status_code=204)
async def delete_alert_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Delete an alert rule."""
    row = await db.execute(select(AlertRule).where(AlertRule.id == rule_id))
    rule = row.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    await db.delete(rule)
    await db.commit()


# ── Budget check service ──────────────────────────────────────────────

@router.post("/check-now")
async def run_budget_check(
    db: AsyncSession = Depends(get_async_db),
):
    """Manually trigger a budget check — called by Celery scheduler or CLI."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Get all alert rules
    rows = await db.execute(select(AlertRule).where(AlertRule.is_enabled == True))  # noqa: E712
    rules = rows.scalars().all()

    triggered = []
    for rule in rules:
        config = rule.config
        threshold_pct = config.get("threshold_pct", 0.9)
        channels = config.get("channels", ["email"])

        # Calculate current month cost for this org
        org_id = str(rule.organization_id)
        cost_row = await db.execute(
            select(func.coalesce(func.sum(UsageRecord.cost_usd), 0))
            .where(
                UsageRecord.organization_id == org_id,
                UsageRecord.started_at >= month_start,
                UsageRecord.started_at < now,
            )
        )
        current_cost = cost_row.scalar() or 0

        # Get org budget
        budget = config.get("budget_usd")  # if set, check absolute
        if budget and current_cost >= budget * threshold_pct:
            triggered.append({
                "rule_id": str(rule.id),
                "type": "budget_absolute",
                "current_cost": float(current_cost),
                "budget": float(budget),
                "pct": round(float(current_cost) / budget, 4),
                "channels": channels,
            })

        # Percentage-based check (of total spend vs previous period)
        prev_start = month_start - (now - month_start)
        prev_cost_row = await db.execute(
            select(func.coalesce(func.sum(UsageRecord.cost_usd), 0))
            .where(
                UsageRecord.organization_id == org_id,
                UsageRecord.started_at >= prev_start,
                UsageRecord.started_at < month_start,
            )
        )
        prev_cost = prev_cost_row.scalar() or 0
        if prev_cost > 0:
            growth = (current_cost - prev_cost) / prev_cost
            growth_threshold = config.get("growth_threshold_pct", 1.0)
            if growth >= growth_threshold:
                triggered.append({
                    "rule_id": str(rule.id),
                    "type": "budget_growth",
                    "current_cost": float(current_cost),
                    "previous_cost": float(prev_cost),
                    "growth_pct": round(float(growth), 4),
                    "channels": channels,
                })

    logger.info("Budget check complete: %d alerts triggered", len(triggered))
    return {"triggered": triggered}
