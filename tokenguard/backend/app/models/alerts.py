from sqlalchemy import Column, String, DateTime, ForeignKey, Index, UniqueConstraint, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.core.database import Base
import uuid

class AlertRule(Base):
    __tablename__ = "alert_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=False)
    rule_type = Column(String(100), nullable=False)
    config = Column(JSONB, nullable=False)
    is_enabled = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AlertHistory(Base):
    __tablename__ = "alert_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=False)
    rule_id = Column(UUID(as_uuid=True))
    user_id = Column(UUID(as_uuid=True))
    alert_type = Column(String(100), nullable=False)
    alert_key = Column(String(255), nullable=False)
    payload = Column(JSONB)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    channels_sent = Column(ARRAY(String))

    __table_args__ = (
        UniqueConstraint("organization_id", "alert_key"),
        Index("idx_alert_dedup", "organization_id", "alert_key"),
    )
