"""seed_pricing

Revision ID: 002_seed_pricing
Revises: 001_initial_models
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "002_seed_pricing"
down_revision = "001_initial_models"
branch_labels = None
depends_on = None


def upgrade():
    pricing_rows = [
        {
            "id": postgresql.UUID(True).as_uuid(),
            "model_id": "claude-sonnet-4-20250514",
            "display_name": "Claude Sonnet 4",
            "provider": "anthropic",
            "input_price_per_million": 3.00,
            "output_price_per_million": 15.00,
            "cache_read_price_per_million": 0.30,
            "cache_creation_price_per_million": 3.75,
            "capability_level": 3,
            "is_active": True,
        },
        {
            "id": postgresql.UUID(True).as_uuid(),
            "model_id": "claude-opus-4-20250514",
            "display_name": "Claude Opus 4",
            "provider": "anthropic",
            "input_price_per_million": 15.00,
            "output_price_per_million": 75.00,
            "cache_read_price_per_million": 1.50,
            "cache_creation_price_per_million": 18.75,
            "capability_level": 5,
            "is_active": True,
        },
        {
            "id": postgresql.UUID(True).as_uuid(),
            "model_id": "claude-haiku-4-20250514",
            "display_name": "Claude Haiku 4",
            "provider": "anthropic",
            "input_price_per_million": 0.80,
            "output_price_per_million": 4.00,
            "cache_read_price_per_million": 0.08,
            "cache_creation_price_per_million": 1.00,
            "capability_level": 2,
            "is_active": True,
        },
        {
            "id": postgresql.UUID(True).as_uuid(),
            "model_id": "claude-3-5-sonnet-20241022",
            "display_name": "Claude 3.5 Sonnet",
            "provider": "anthropic",
            "input_price_per_million": 3.00,
            "output_price_per_million": 15.00,
            "cache_read_price_per_million": 0.30,
            "cache_creation_price_per_million": 3.75,
            "capability_level": 3,
            "is_active": True,
        },
        {
            "id": postgresql.UUID(True).as_uuid(),
            "model_id": "claude-3-5-haiku-20241022",
            "display_name": "Claude 3.5 Haiku",
            "provider": "anthropic",
            "input_price_per_million": 1.00,
            "output_price_per_million": 5.00,
            "cache_read_price_per_million": 0.10,
            "cache_creation_price_per_million": 1.25,
            "capability_level": 2,
            "is_active": True,
        },
        {
            "id": postgresql.UUID(True).as_uuid(),
            "model_id": "claude-3-opus-20240229",
            "display_name": "Claude 3 Opus",
            "provider": "anthropic",
            "input_price_per_million": 15.00,
            "output_price_per_million": 75.00,
            "cache_read_price_per_million": 1.50,
            "cache_creation_price_per_million": 18.75,
            "capability_level": 5,
            "is_active": False,
        },
    ]
    table = sa.Table("model_pricings", sa.MetaData(),
                     sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
                     sa.Column("model_id", sa.String(100), nullable=False),
                     sa.Column("display_name", sa.String(200), nullable=False),
                     sa.Column("provider", sa.String(50), nullable=False),
                     sa.Column("input_price_per_million", sa.Numeric(10, 4), nullable=False),
                     sa.Column("output_price_per_million", sa.Numeric(10, 4), nullable=False),
                     sa.Column("cache_read_price_per_million", sa.Numeric(10, 4), nullable=True),
                     sa.Column("cache_creation_price_per_million", sa.Numeric(10, 4), nullable=True),
                     sa.Column("capability_level", sa.Integer, nullable=False),
                     sa.Column("is_active", sa.Boolean, nullable=True),
                     )
    for row in pricing_rows:
        op.bulk_insert(table, [row])


def downgrade():
    op.execute("DELETE FROM model_pricings WHERE provider = 'anthropic'")
