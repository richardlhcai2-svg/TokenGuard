from sqlalchemy import Column, String, Integer, Numeric, DateTime, Index, desc
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base
import uuid

class UsageRecord(Base):
    __tablename__ = "usage_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    tool_name = Column(String(50), nullable=False)
    model_name = Column(String(100))
    provider = Column(String(50))
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cache_creation_tokens = Column(Integer, default=0)
    cache_read_tokens = Column(Integer, default=0)
    cost_usd = Column(Numeric(10, 6), nullable=False)
    session_id = Column(String(255))
    project_name = Column(String(255))
    task_type = Column(String(100))
    context_window_size = Column(Integer)
    context_usage_pct = Column(Numeric(5, 4))
    started_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_usage_org_time", "organization_id", desc("started_at")),
        Index("idx_usage_user_time", "user_id", desc("started_at")),
        Index("idx_usage_session", "session_id"),
    )

class DailySummary(Base):
    __tablename__ = "daily_summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), nullable=False)
    user_id = Column(UUID(as_uuid=True))
    tool_name = Column(String(50))
    date = Column(DateTime, nullable=False)
    total_cost_usd = Column(Numeric(10, 4), default=0, nullable=False)
    total_input_tokens = Column(Integer, default=0, nullable=False)
    total_output_tokens = Column(Integer, default=0, nullable=False)
    total_requests = Column(Integer, default=0, nullable=False)
    avg_context_usage = Column(Numeric(5, 4))
