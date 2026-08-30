import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_org
from app.core.database import get_async_db
from app.models.usage import UsageRecord
from app.models.alerts import AlertRule, AlertHistory
from app.schemas import AlertRuleCreate, AlertRuleUpdate, AlertRuleOut

logger = logging.getLogger("tokenguard.backend")
router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


# ── CRUD for alert rules ──────────────────────────────────────────────

@router.get("/")
async def list_alert_rules(
    org = Depends(get_current_org),
    db: AsyncSession = Depends(get_async_db),
):
    rows = await db.execute(
        select(AlertRule)
        .where(AlertRule.organization_id == org.id)
        .order_by(AlertRule.created_at.desc())
    )
    rules = rows.scalars().all()
    return [
        AlertRuleOut.model_validate(r).model_dump()
        for r in rules
    ]


@router.post("/", status_code=201)
async def create_alert_rule(
    body: AlertRuleCreate,
    org = Depends(get_current_org),
    db: AsyncSession = Depends(get_async_db),
):
    rule = AlertRule(
        organization_id=org.id,
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

def _format_alert_message(rule: AlertRule, alert_data: dict) -> str:
    """Format alert data into a human-readable message."""
    rule_type = rule.rule_type
    config = rule.config

    messages = {
        "budget_percentage": (
            f"🔥 Budget Alert: Spend reached {config.get('threshold_pct', 0)*100:.0f}% of budget. "
            f"Current: ${alert_data.get('current_cost', 0):.2f}"
        ),
        "budget_absolute": (
            f"💰 Absolute Budget Alert: Spend ${alert_data.get('current_cost', 0):.2f} "
            f"exceeds ${alert_data.get('budget', 0):.2f} ({alert_data.get('pct', 0):.1%})"
        ),
        "budget_growth": (
            f"📈 Growth Alert: Cost grew {alert_data.get('growth_pct', 0)*100:.1f}% vs last period. "
            f"Previous: ${alert_data.get('previous_cost', 0):.2f} → Current: ${alert_data.get('current_cost', 0):.2f}"
        ),
        "context_window": (
            f"⚠️ Context Window: Session approaching context limit. "
            f"Usage: {alert_data.get('pct', 0)*100:.1f}%"
        ),
    }
    return messages.get(rule_type, f"Alert [{rule_type}]: {alert_data}")


async def _send_notifications(channels: list[str], msg: str, config: dict):
    """Send alert notifications via configured channels (stubs)."""
    for ch in channels:
        if ch == "email":
            logger.info("[email stub] To=%s Body=%s", config.get("recipients", []), msg[:100])
        elif ch == "slack":
            logger.info("[slack stub] URL=%s Text=%s", config.get("webhook_url", "")[:50], msg[:100])


@router.post("/check-now")
async def run_budget_check(
    db: AsyncSession = Depends(get_async_db),
):
    """Trigger a budget check — saves AlertHistory for triggered alerts."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    rows = await db.execute(select(AlertRule).where(AlertRule.is_enabled == True))  # noqa: E712
    rules = rows.scalars().all()

    triggered = []
    for rule in rules:
        config = rule.config
        threshold_pct = config.get("threshold_pct", 0.9)
        channels = config.get("channels", ["email"])

        # Current month cost for this org
        cost_row = await db.execute(
            select(func.coalesce(func.sum(UsageRecord.cost_usd), 0))
            .where(
                UsageRecord.organization_id == rule.organization_id,
                UsageRecord.started_at >= month_start,
                UsageRecord.started_at < now,
            )
        )
        current_cost = cost_row.scalar() or 0

        # Absolute budget check
        budget = config.get("budget_usd")
        if budget and current_cost >= budget * threshold_pct:
            alert_data = {
                "rule_id": str(rule.id),
                "type": "budget_absolute",
                "current_cost": float(current_cost),
                "budget": float(budget),
                "pct": round(float(current_cost) / budget, 4),
            }
            msg = _format_alert_message(rule, alert_data)
            severity = "critical" if alert_data["pct"] >= 1.0 else "warning"

            history = AlertHistory(
                organization_id=rule.organization_id,
                alert_rule_id=rule.id,
                severity=severity,
                message=msg,
            )
            db.add(history)
            await _send_notifications(channels, msg, config)
            triggered.append(alert_data)

        # Growth check
        prev_start = month_start - (now - month_start)
        prev_cost_row = await db.execute(
            select(func.coalesce(func.sum(UsageRecord.cost_usd), 0))
            .where(
                UsageRecord.organization_id == rule.organization_id,
                UsageRecord.started_at >= prev_start,
                UsageRecord.started_at < month_start,
            )
        )
        prev_cost = prev_cost_row.scalar() or 0
        if prev_cost > 0:
            growth = (current_cost - prev_cost) / prev_cost
            growth_threshold = config.get("growth_threshold_pct", 1.0)
            if growth >= growth_threshold:
                alert_data = {
                    "rule_id": str(rule.id),
                    "type": "budget_growth",
                    "current_cost": float(current_cost),
                    "previous_cost": float(prev_cost),
                    "growth_pct": round(float(growth), 4),
                }
                msg = _format_alert_message(rule, alert_data)
                history = AlertHistory(
                    organization_id=rule.organization_id,
                    alert_rule_id=rule.id,
                    severity="warning",
                    message=msg,
                )
                db.add(history)
                await _send_notifications(channels, msg, config)
                triggered.append(alert_data)

    await db.commit()
    logger.info("Budget check complete: %d alerts triggered", len(triggered))
    return {
        "triggered": triggered,
        "count": len(triggered),
    }
