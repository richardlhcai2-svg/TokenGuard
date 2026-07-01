"""initial_models

Revision ID: 001_initial_models
Revises:
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "001_initial_models"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # --- organizations ---
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("plan", sa.String(50), nullable=False, server_default="free"),
        sa.Column("monthly_budget", sa.Numeric(12, 2), nullable=True),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True, unique=True),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("github_id", sa.String(255), nullable=True, unique=True),
        sa.Column("google_id", sa.String(255), nullable=True, unique=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- organization_members ---
    op.create_table(
        "organization_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="member"),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("organization_id", "user_id", name="uix_org_member"),
    )

    # --- tool_integrations ---
    op.create_table(
        "tool_integrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("api_key_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )

    # --- usage_records ---
    op.create_table(
        "usage_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_name", sa.String(50), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("input_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cache_creation_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cache_read_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False),
        sa.Column("session_id", sa.String(255), nullable=True),
        sa.Column("project_name", sa.String(255), nullable=True),
        sa.Column("task_type", sa.String(100), nullable=True),
        sa.Column("context_window_size", sa.Integer, nullable=True),
        sa.Column("context_usage_pct", sa.Numeric(5, 4), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Index("idx_usage_org_time", "organization_id", sa.text("started_at DESC")),
        sa.Index("idx_usage_user_time", "user_id", sa.text("started_at DESC")),
        sa.Index("idx_usage_session", "session_id"),
    )

    # --- daily_summaries ---
    op.create_table(
        "daily_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tool_name", sa.String(50), nullable=True),
        sa.Column("date", sa.DateTime, nullable=False),
        sa.Column("total_cost_usd", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("total_input_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_output_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_requests", sa.Integer, nullable=False, server_default="0"),
        sa.Column("avg_context_usage", sa.Numeric(5, 4), nullable=True),
        sa.Index("idx_daily_org_date", "organization_id", "date"),
    )

    # --- alert_rules ---
    op.create_table(
        "alert_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_type", sa.String(100), nullable=False),
        sa.Column("config", postgresql.JSONB, nullable=False),
        sa.Column("is_enabled", sa.Boolean, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
    )

    # --- alert_history ---
    op.create_table(
        "alert_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alert_rule_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("severity", sa.String(50), nullable=False, server_default="info"),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("alert_rule_id", "message", name="uq_alert_dedup"),
        sa.ForeignKeyConstraint(["alert_rule_id"], ["alert_rules.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
    )

    # --- model_pricings ---
    op.create_table(
        "model_pricings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("model_id", sa.String(100), nullable=False, unique=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("input_price_per_million", sa.Numeric(10, 4), nullable=False),
        sa.Column("output_price_per_million", sa.Numeric(10, 4), nullable=False),
        sa.Column("cache_read_price_per_million", sa.Numeric(10, 4), nullable=True),
        sa.Column("cache_creation_price_per_million", sa.Numeric(10, 4), nullable=True),
        sa.Column("capability_level", sa.Integer, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=True),
    )


def downgrade():
    op.drop_table("model_pricings")
    op.drop_table("alert_history")
    op.drop_table("alert_rules")
    op.drop_table("daily_summaries")
    op.drop_table("usage_records")
    op.drop_table("tool_integrations")
    op.drop_table("organization_members")
    op.drop_table("users")
    op.drop_table("organizations")
