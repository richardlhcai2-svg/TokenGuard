"""Organization and member management endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, get_current_org
from app.core.database import get_async_db
from app.models.organization import Organization
from app.models.user import User
from app.models.member import OrganizationMember
from app.models.usage import UsageRecord
from app.schemas import (
    OrgCreate, OrgUpdate, OrgOut,
    MemberCreate, MemberOut,
)

router = APIRouter(prefix="/api/v1/orgs", tags=["organizations"])


@router.get("/me", response_model=OrgOut)
async def get_my_org(org: Organization = Depends(get_current_org)):
    return org


@router.put("/me", response_model=OrgOut)
async def update_my_org(
    body: OrgUpdate,
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_async_db),
):
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(org, field, value)
    await db.commit()
    await db.refresh(org)
    return org


@router.get("/members", response_model=list[MemberOut])
async def list_members(
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_async_db),
):
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org.id
        ).order_by(OrganizationMember.joined_at.desc())
    )
    return result.scalars().all()


@router.post("/members", status_code=201, response_model=MemberOut)
async def add_member(
    body: MemberCreate,
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_async_db),
):
    result = await db.execute(select(User).where(User.id == uuid.UUID(body.user_id)))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    dup = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org.id,
            OrganizationMember.user_id == uuid.UUID(body.user_id),
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Member already exists")

    member = OrganizationMember(
        id=uuid.uuid4(),
        organization_id=org.id,
        user_id=uuid.UUID(body.user_id),
        role=body.role,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


@router.delete("/members/{user_id}")
async def remove_member(
    user_id: str,
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_async_db),
):
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org.id,
            OrganizationMember.user_id == uuid.UUID(user_id),
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    await db.delete(member)
    await db.commit()


@router.get("/stats")
async def org_stats(
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_async_db),
):
    member_count = (await db.execute(
        select(func.count(OrganizationMember.id)).where(
            OrganizationMember.organization_id == org.id
        )
    )).scalar() or 0

    total_cost = (await db.execute(
        select(func.coalesce(func.sum(UsageRecord.cost_usd), 0)).where(
            UsageRecord.organization_id == org.id
        )
    )).scalar() or 0

    return {
        "member_count": member_count,
        "total_cost_usd": float(total_cost),
        "plan": org.plan,
        "monthly_budget": float(org.monthly_budget) if org.monthly_budget else None,
    }
