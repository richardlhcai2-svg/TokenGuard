"""Model recommendation engine + alert notification delivery."""

import re
import logging
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_org
from app.core.database import get_async_db
from app.models.pricing import ModelPricing
from app.models.alerts import AlertRule, AlertHistory
from app.models.usage import UsageRecord
from app.schemas import (
    RecommendationResponse,
    AlertHistoryOut,
)

logger = logging.getLogger("tokenguard.backend")
router = APIRouter(prefix="/api/v1", tags=["recommendations"])

# ── Task classification rules ──────────────────────────────────────────

TASK_PATTERNS = [
    ("code_generation", [
        "generate", "create", "implement", "write", "build", "develop",
        "function", "class", "api", "endpoint", "route",
    ]),
    ("debugging", [
        "bug", "error", "fix", "crash", "exception", "traceback",
        "fail", "issue", "problem", "break",
    ]),
    ("refactoring", [
        "refactor", "restructure", "clean up", "rename", "extract",
        "simplify", "modernize", "migrate",
    ]),
    ("documentation", [
        "doc", "document", "readme", "comment", "explain",
        "describe", "tutorial", "guide", "how-to",
    ]),
    ("testing", [
        "test", "spec", "assert", "mock", "fixture", "coverage",
        "unit test", "integration test",
    ]),
    ("architectural", [
        "design", "architecture", "pattern", "system", "scal",
        "performance", "optimize", "profiling",
    ]),
]

# Capability-level thresholds: level 1=basic, 2=intermediate, 3=advanced, 4=expert
MODEL_SUITABILITY = {
    "code_generation": 3,
    "debugging": 4,
    "refactoring": 3,
    "documentation": 1,
    "testing": 2,
    "architectural": 4,
}


def classify_task(prompt: str) -> str:
    """Classify the task type from the prompt text."""
    text = prompt.lower()
    scores: dict[str, int] = {}
    for task_type, keywords in TASK_PATTERNS:
        scores[task_type] = sum(1 for kw in keywords if kw in text)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


# ── Recommendation engine ─────────────────────────────────────────────

@router.post("/recommendations/model", response_model=RecommendationResponse)
async def recommend_model(
    body: dict,
    org = Depends(get_current_org),
    db: AsyncSession = Depends(get_async_db),
):
    """Recommend the best model for a given task/prompt.

    Request body: { "prompt": "...", "current_model": "claude-sonnet-4-20250514" }
    """
    prompt = body.get("prompt", "")
    current_model_name = body.get("current_model", "claude-sonnet-4-20250514")

    task_type = classify_task(prompt)
    required_level = MODEL_SUITABILITY.get(task_type, 2)

    # Fetch all active pricing for this org's region (we use global pricing)
    rows = (await db.execute(
        select(ModelPricing).where(
            ModelPricing.is_active == True,  # noqa: E712
        ).order_by(ModelPricing.capability_level)
    )).scalars().all()

    if not rows:
        return RecommendationResponse(
            recommended_model=current_model_name,
            current_model=current_model_name,
            task_type=task_type,
            estimated_saving_pct=0.0,
            confidence=0.5,
            reason="No pricing data available",
            current_cost_estimate=Decimal("0"),
            recommended_cost_estimate=Decimal("0"),
        )

    # Find current model pricing
    current_model = None
    for m in rows:
        if current_model_name in (m.model_id, m.display_name):
            current_model = m
            break

    # Score models: suitable level + cost efficiency
    candidates = []
    for m in rows:
        suitable = m.capability_level >= required_level
        # Higher capability = more suitable, but also more expensive
        suitability_score = m.capability_level if suitable else 0
        # Cost efficiency: lower cost per token is better
        cost_per_m = float(m.input_price_per_million or 0) + float(m.output_price_per_million or 0)
        efficiency = 1.0 / (cost_per_m + 0.001) if cost_per_m > 0 else 1.0
        candidates.append((m, suitability_score * efficiency))

    # Pick best candidate
    best = max(candidates, key=lambda x: x[1])
    best_model = best[0]

    # Calculate estimated saving
    if current_model:
        current_cost = float(current_model.input_price_per_million) + float(current_model.output_price_per_million)
        recommended_cost = float(best_model.input_price_per_million) + float(best_model.output_price_per_million)
        saving_pct = max(0.0, (current_cost - recommended_cost) / current_cost * 100) if current_cost > 0 else 0.0
    else:
        saving_pct = 0.0

    # Confidence based on cost delta
    confidence = min(0.95, 0.5 + saving_pct / 100)

    # Build reason
    reasons = {
        "code_generation": "High-capability model needed for complex code generation tasks",
        "debugging": "Expert-level model best for diagnosing complex bugs",
        "refactoring": "Advanced model handles structural changes safely",
        "documentation": "Basic model sufficient for documentation tasks — saves cost",
        "testing": "Intermediate model adequate for test generation",
        "architectural": "Expert-level reasoning required for system design",
    }

    reason_text = reasons.get(task_type, "General recommendation")
    if current_model and best_model.id != current_model.id:
        reason_text += f" — {best_model.display_name} is cheaper for {task_type} tasks."
    else:
        reason_text += f" Current model ({current_model_name}) is already well-suited."

    return RecommendationResponse(
        recommended_model=best_model.model_id,
        current_model=current_model_name,
        task_type=task_type,
        estimated_saving_pct=round(saving_pct, 2),
        confidence=round(confidence, 2),
        reason=reason_text,
        current_cost_estimate=Decimal(str(round(current_cost if current_model else 0, 4))),
        recommended_cost_estimate=Decimal(str(round(recommended_cost, 4))),
    )


# ── Alert history listing ─────────────────────────────────────────────

@router.get("/alerts/history", response_model=list[AlertHistoryOut])
async def list_alert_history(
    org = Depends(get_current_org),
    db: AsyncSession = Depends(get_async_db),
    limit: int = Query(default=50, ge=1, le=200),
):
    """List recent alert history entries for the org."""
    rows = await db.execute(
        select(AlertHistory)
        .where(AlertHistory.organization_id == org.id)
        .order_by(AlertHistory.triggered_at.desc())
        .limit(limit)
    )
    return [AlertHistoryOut.model_validate(r) for r in rows.scalars().all()]


# ── Notification helpers ──────────────────────────────────────────────

async def send_email_notification(recipients: list[str], subject: str, body: str):
    """Send email via SendGrid (stub — replace with real integration)."""
    logger.info("[email stub] To=%s Subject=%s Body=%s", recipients, subject, body[:100])
    # TODO: integrate with SendGrid API
    # from sendgrid import SendGridAPIClient
    # from sendgrid.helpers.mail import Mail
    # msg = Mail(from_email, subject, to_email, body)
    # sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
    # sg.send(msg)


async def send_slack_webhook(url: str, text: str):
    """Send notification via Slack webhook."""
    logger.info("[slack stub] URL=%s Text=%s", url[:50], text[:100])
    # TODO: integrate with Slack webhook
    # import httpx
    # async with httpx.AsyncClient() as client:
    #     await client.post(url, json={"text": text})


async def send_push_notification(device_tokens: list[str], title: str, body: str):
    """Send push notifications (Firebase/APNs stub)."""
    logger.info("[push stub] Tokens=%d Title=%s Body=%s", len(device_tokens), title, body[:50])
    # TODO: integrate with Firebase Cloud Messaging or APNs


def format_alert_message(rule: AlertRule, alert_data: dict) -> str:
    """Format alert data into a human-readable message."""
    rule_type = rule.rule_type
    config = rule.config
    org_name = getattr(rule.organization, "name", "unknown") if hasattr(rule, "organization") else "org"

    messages = {
        "budget_percentage": (
            f"🔥 Budget Alert [{org_name}]: "
            f"Spend reached {config.get('threshold_pct', 0)*100:.0f}% of budget. "
            f"Current: ${alert_data.get('current_cost', 0):.2f}"
        ),
        "budget_absolute": (
            f"💰 Absolute Budget [{org_name}]: "
            f"Spend ${alert_data.get('current_cost', 0):.2f} "
            f"exceeds ${alert_data.get('budget', 0):.2f} * {alert_data.get('pct', 0):.1%}"
        ),
        "budget_growth": (
            f"📈 Growth Alert [{org_name}]: "
            f"Cost grew {alert_data.get('growth_pct', 0)*100:.1f}% vs last period. "
            f"Previous: ${alert_data.get('previous_cost', 0):.2f} → Current: ${alert_data.get('current_cost', 0):.2f}"
        ),
        "context_window": (
            f"⚠️ Context Window [{org_name}]: "
            f"Session approaching context limit. "
            f"Usage: {alert_data.get('pct', 0)*100:.1f}%"
        ),
    }
    return messages.get(rule_type, f"Alert [{rule_type}]: {alert_data}")


