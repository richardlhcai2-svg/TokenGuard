import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pydantic import ValidationError
from app.schemas import (
    OrgCreate, OrgOut, OrgUpdate,
    UserCreate, UserOut,
    UsageRecordCreate,
    AlertRuleCreate, AlertRuleOut,
    DashboardSummary,
)


class TestOrganizationSchema:
    def test_create_valid(self):
        org = OrgCreate(name="Acme Corp", slug="acme-corp", plan="free")
        assert org.name == "Acme Corp"
        assert org.slug == "acme-corp"
        assert org.plan == "free"
        assert org.monthly_budget is None

    def test_create_with_budget(self):
        org = OrgCreate(name="BigCo", slug="bigco", plan="pro", monthly_budget=500)
        assert org.monthly_budget == 500

    def test_update_partial(self):
        update = OrgUpdate(name="New Name")
        assert update.name == "New Name"

    def test_slug_min_length_validation(self):
        try:
            OrgCreate(name="X", slug="")
            assert False, "Should raise"
        except ValidationError:
            pass

    def test_out_has_from_attributes(self):
        assert OrgOut.model_config.get("from_attributes") is True


class TestUserSchema:
    def test_create_valid(self):
        user = UserCreate(email="test@example.com", name="Test User")
        assert user.email == "test@example.com"
        assert user.name == "Test User"

    def test_invalid_email(self):
        try:
            UserCreate(email="not-an-email", name="Bad")
            assert False
        except ValidationError:
            pass

    def test_out_has_from_attributes(self):
        assert UserOut.model_config.get("from_attributes") is True


class TestUsageRecordSchema:
    def test_create_valid(self):
        from datetime import datetime
        record = UsageRecordCreate(
            organization_id="00000000-0000-0000-0000-000000000001",
            user_id="00000000-0000-0000-0000-000000000002",
            tool_name="claude_code",
            model_name="claude-sonnet-4-20250514",
            input_tokens=5000,
            output_tokens=1000,
            cost_usd=0.15,
            context_usage_pct=0.3,
            started_at=datetime.now(),
        )
        assert record.tool_name == "claude_code"
        assert record.input_tokens == 5000
        from decimal import Decimal
        assert record.context_usage_pct == Decimal("0.3")


class TestAlertRuleSchema:
    def test_create_valid(self):
        rule = AlertRuleCreate(
            rule_type="budget_threshold",
            config={"threshold_pct": 0.9, "channels": ["email"]},
        )
        assert rule.rule_type == "budget_threshold"
        assert rule.config["threshold_pct"] == 0.9

    def test_out_has_from_attributes(self):
        assert AlertRuleOut.model_config.get("from_attributes") is True


class TestDashboardSummary:
    def test_valid_data(self):
        from decimal import Decimal
        summary = DashboardSummary(
            total_cost_usd=Decimal("100.50"),
            total_requests=50,
            total_input_tokens=100000,
            total_output_tokens=50000,
            avg_context_usage=Decimal("0.45"),
            cost_today=Decimal("10.00"),
            cost_yesterday=Decimal("15.00"),
            cost_last_7_days=Decimal("70.00"),
            cost_last_30_days=Decimal("100.50"),
        )
        assert summary.total_cost_usd == Decimal("100.50")
        assert summary.total_requests == 50
