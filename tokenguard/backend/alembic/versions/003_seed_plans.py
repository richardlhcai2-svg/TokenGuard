"""seed_plans

Revision ID: 003_seed_plans
Revises: 002_seed_pricing
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers
revision = "003_seed_plans"
down_revision = "002_seed_pricing"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "subscription_plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("monthly_budget_usd", sa.Numeric(10, 2), nullable=True),
        sa.Column("max_members", sa.Integer, nullable=False),
        sa.Column("retention_days", sa.Integer, nullable=False),
        sa.Column("include_alerts", sa.Boolean, nullable=False),
        sa.Column("include_predictions", sa.Boolean, nullable=False),
        sa.Column("include_team_features", sa.Boolean, nullable=False),
    )

    rows = [
        {
            "id": UUID(True).as_uuid(),
            "name": "free",
            "monthly_budget_usd": None,
            "max_members": 3,
            "retention_days": 7,
            "include_alerts": True,
            "include_predictions": False,
            "include_team_features": False,
        },
        {
            "id": UUID(True).as_uuid(),
            "name": "pro",
            "monthly_budget_usd": 500.00,
            "max_members": 10,
            "retention_days": 30,
            "include_alerts": True,
            "include_predictions": True,
            "include_team_features": False,
        },
        {
            "id": UUID(True).as_uuid(),
            "name": "team",
            "monthly_budget_usd": 5000.00,
            "max_members": 50,
            "retention_days": 90,
            "include_alerts": True,
            "include_predictions": True,
            "include_team_features": True,
        },
    ]
    table = sa.Table("subscription_plans", sa.MetaData(),
                     sa.Column("id", UUID(as_uuid=True), primary_key=True),
                     sa.Column("name", sa.String(50), nullable=False),
                     sa.Column("monthly_budget_usd", sa.Numeric(10, 2), nullable=True),
                     sa.Column("max_members", sa.Integer, nullable=False),
                     sa.Column("retention_days", sa.Integer, nullable=False),
                     sa.Column("include_alerts", sa.Boolean, nullable=False),
                     sa.Column("include_predictions", sa.Boolean, nullable=False),
                     sa.Column("include_team_features", sa.Boolean, nullable=False),
                     )
    op.bulk_insert(table, rows)


def downgrade():
    op.drop_table("subscription_plans")
