import uuid
from app.models.organization import Organization
from app.models.user import User
from app.models.usage import UsageRecord, DailySummary
from app.models.alerts import AlertRule, AlertHistory
from app.models.pricing import ModelPricing


def test_organization_defaults():
    org = Organization(name="Acme Corp", slug="acme-corp", plan="free")
    assert org.name == "Acme Corp"
    assert org.slug == "acme-corp"
    assert org.plan == "free"
    assert org.id is None  # UUID default fires on DB insert, not here


def test_user_defaults():
    user = User(email="alex@example.com", name="Alex")
    assert user.email == "alex@example.com"
    assert user.name == "Alex"
    assert user.id is None  # UUID default fires on DB insert


def test_usage_record_creation():
    record = UsageRecord(
        organization_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        tool_name="claude_code",
        model_name="claude-opus-4-8",
        input_tokens=45800,
        output_tokens=2340,
        cost_usd=28.34,
        context_usage_pct=0.91,
    )
    assert record.cost_usd == 28.34
    assert record.context_usage_pct == 0.91
    assert record.tool_name == "claude_code"


def test_daily_summary_defaults():
    org_id = uuid.uuid4()
    summary = DailySummary(
        organization_id=org_id,
        date="2026-05-01",
        total_cost_usd=100.0,
    )
    assert summary.total_cost_usd == 100.0
    assert summary.total_input_tokens is None  # default fires on DB insert


def test_model_pricing_defaults():
    pricing = ModelPricing(
        model_id="claude-haiku-4-5",
        display_name="Claude Haiku 4.5",
        provider="anthropic",
        input_price_per_million=0.80,
        output_price_per_million=4.00,
        capability_level=2,
    )
    assert pricing.model_id == "claude-haiku-4-5"
    assert pricing.provider == "anthropic"
    assert pricing.capability_level == 2
    assert pricing.is_active is None  # default fires on DB insert


def test_alert_rule_defaults():
    rule = AlertRule(
        organization_id=uuid.uuid4(),
        rule_type="budget_threshold",
        config={"threshold_pct": 0.9, "channels": ["email", "slack"]},
    )
    assert rule.rule_type == "budget_threshold"
    assert rule.is_enabled is None  # default fires on DB insert
