from sqlalchemy import Column, String, Numeric, Boolean, DateTime, Integer, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base
import uuid

class ModelPricing(Base):
    __tablename__ = "model_pricing"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(200), nullable=False)
    provider = Column(String(50), nullable=False)
    input_price_per_million = Column(Numeric(10, 4), nullable=False)
    output_price_per_million = Column(Numeric(10, 4), nullable=False)
    cache_write_price_per_million = Column(Numeric(10, 4), default=0)
    cache_read_price_per_million = Column(Numeric(10, 4), default=0)
    context_window = Column(Integer)
    capability_level = Column(Integer)
    is_active = Column(Boolean, default=True)
    effective_from = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
