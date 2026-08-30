from sqlalchemy import Column, String, Numeric, DateTime, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base
import uuid


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    slug = Column(String(100), nullable=False, unique=True)
    plan = Column(String(50), nullable=False, server_default="free")
    monthly_budget = Column(Numeric(12, 2))
    stripe_customer_id = Column(String(255), unique=True)
    stripe_subscription_id = Column(String(255))
    is_active = Column(Boolean, nullable=False, server_default="true")
    settings = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
