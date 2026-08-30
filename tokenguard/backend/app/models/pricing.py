from sqlalchemy import Column, String, Numeric, Boolean, DateTime, Integer, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base
import uuid


class ModelPricing(Base):
    __tablename__ = "model_pricing"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id = Column(String(100), nullable=False, unique=True)
    display_name = Column(String(200), nullable=False)
    provider = Column(String(50), nullable=False)
    input_price_per_million = Column(Numeric(10, 4), nullable=False)
    output_price_per_million = Column(Numeric(10, 4), nullable=False)
    cache_read_price_per_million = Column(Numeric(10, 4))
    cache_creation_price_per_million = Column(Numeric(10, 4))
    capability_level = Column(Integer, nullable=False)
    is_active = Column(Boolean)
