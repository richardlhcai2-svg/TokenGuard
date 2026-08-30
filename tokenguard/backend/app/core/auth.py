"""FastAPI dependencies for auth and org resolution."""

import uuid

from fastapi import Header, HTTPException, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.security import require_auth
from app.models.organization import Organization
from app.models.user import User


async def get_current_user(
    authorization: str = Header(..., alias="Authorization"),
    db: AsyncSession = Depends(get_async_db),
) -> User:
    """Extract and validate Bearer token, return current User."""
    try:
        user_id = require_auth(authorization)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def get_current_org(
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(get_current_user),
) -> Organization:
    """Return the user's default organization."""
    result = await db.execute(
        select(Organization).where(Organization.is_active == True).limit(1)
    )
    org = result.scalar_one_or_none()
    if not org:
        slug = user.email.split("@")[0][:100]
        org = Organization(
            id=uuid.uuid4(),
            name=f"{user.name}'s Team",
            slug=slug,
            plan="free",
        )
        db.add(org)
        await db.commit()
        await db.refresh(org)
    return org
