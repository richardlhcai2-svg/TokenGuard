from sqlalchemy import Column, String, Numeric, Boolean, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base
import uuid


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), nullable=False, unique=True)
    monthly_budget_usd = Column(Numeric(12, 2))
    max_members = Column(Integer, nullable=False)
    retention_days = Column(Integer, nullable=False)
    include_alerts = Column(Boolean, default=False)
    include_predictions = Column(Boolean, default=False)
    include_team_features = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
