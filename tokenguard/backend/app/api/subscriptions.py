"""Subscription plan enforcement and Stripe stub endpoints."""

import logging
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_org
from app.core.database import get_async_db
from app.models.organization import Organization
from app.models.member import OrganizationMember
from app.models.subscription import SubscriptionPlan
from app.schemas import SubscriptionPlanOut

logger = logging.getLogger("tokenguard.backend")
router = APIRouter(prefix="/api/v1/subscriptions", tags=["subscriptions"])

# ── Plan tiers ─────────────────────────────────────────────────────────

FREE_PLAN_LIMITS = {"max_members": 3, "retention_days": 30}
STANDARD_PLAN_LIMITS = {"max_members": 10, "retention_days": 90}
ENTERPRISE_PLAN_LIMITS = {"max_members": -1, "retention_days": -1}  # unlimited


def get_plan_limits(plan_name: str) -> dict:
    limits = {
        "free": FREE_PLAN_LIMITS,
        "standard": STANDARD_PLAN_LIMITS,
        "enterprise": ENTERPRISE_PLAN_LIMITS,
    }
    return limits.get(plan_name, FREE_PLAN_LIMITS)


@router.get("/plans", response_model=list[SubscriptionPlanOut])
async def list_plans(
    org = Depends(get_current_org),
    db: AsyncSession = Depends(get_async_db),
):
    """List available subscription plans."""
    rows = await db.execute(
        select(SubscriptionPlan).order_by(SubscriptionPlan.name)
    )
    return [SubscriptionPlanOut.model_validate(r) for r in rows.scalars().all()]


@router.get("/current")
async def current_plan(
    org = Depends(get_current_org),
    db: AsyncSession = Depends(get_async_db),
):
    """Get current org subscription status and limits."""
    plan_result = await db.execute(
        select(SubscriptionPlan).where(
            SubscriptionPlan.name == org.plan
        )
    )
    plan = plan_result.scalar_one_or_none()

    member_count = (await db.execute(
        select(func.count(OrganizationMember.id)).where(
            OrganizationMember.organization_id == org.id
        )
    )).scalar() or 0

    limits = get_plan_limits(org.plan or "free")
    can_add_member = limits["max_members"] < 0 or member_count < limits["max_members"]

    return {
        "plan": org.plan or "free",
        "is_active": org.is_active,
        "stripe_subscription_id": org.stripe_subscription_id,
        "limits": limits,
        "member_count": member_count,
        "can_add_member": can_add_member,
        "features": {
            "alerts": org.plan != "free" if org.plan else False,
            "predictions": org.plan in ("standard", "enterprise"),
            "team_features": org.plan in ("standard", "enterprise"),
        },
    }


@router.post("/stripe/create-checkout")
async def create_checkout(
    body: dict,
    org = Depends(get_current_org),
    db: AsyncSession = Depends(get_async_db),
):
    """Create Stripe checkout session (stub)."""
    plan_name = body.get("plan_name", "standard")

    # TODO: integrate with real Stripe API
    logger.info("[stripe stub] Creating checkout for plan=%s org=%s", plan_name, org.id)

    return {
        "checkout_url": f"https://checkout.stripe.com/mock/{org.id}/{plan_name}",
        "plan": plan_name,
        "status": "created",
    }


@router.post("/stripe/webhook")
async def stripe_webhook(body: dict):
    """Handle Stripe webhook events (stub)."""
    event_type = body.get("type", "")
    logger.info("[stripe stub] Received event=%s", event_type)

    # TODO: verify Stripe signature and handle real events
    if event_type == "customer.subscription.updated":
        pass  # Update org.plan and org.stripe_subscription_id
    elif event_type == "invoice.payment_failed":
        pass  # Mark org.is_active = False

    return {"status": "received"}


# ── Rate limiting middleware for free tier ────────────────────────────

async def enforce_free_tier_limits(
    org: Organization,
    db: AsyncSession,
):
    """Check if org has exceeded free tier limits. Raises HTTPException if over."""
    limits = get_plan_limits(org.plan or "free")
    max_members = limits["max_members"]

    if max_members > 0:
        member_count = (await db.execute(
            select(func.count(OrganizationMember.id)).where(
                OrganizationMember.organization_id == org.id
            )
        )).scalar() or 0

        if member_count > max_members:
            raise HTTPException(
                status_code=403,
                detail=f"Free plan limited to {max_members} members. Upgrade to add more.",
            )

    return True
