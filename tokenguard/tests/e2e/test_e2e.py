"""End-to-end tests for TokenGuard — assumes docker-compose is running."""

import pytest
import requests

BACKEND_URL = "http://localhost:8000"
PROXY_URL = "http://localhost:8001"
FRONTEND_URL = "http://localhost:3000"
TEST_KEY = "dev-secret-key"


def is_backend_up() -> bool:
    try:
        resp = requests.get(f"{BACKEND_URL}/health", timeout=0.5)
        return resp.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not is_backend_up(),
    reason="Full Docker stack (backend on http://localhost:8000) is not running — start with 'tg deploy' to run live e2e tests."
)


class TestHealthChecks:
    """Verify all services are reachable."""

    def test_backend_health(self):
        resp = requests.get(f"{BACKEND_URL}/health", timeout=5)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_frontend_reachable(self):
        resp = requests.get(FRONTEND_URL, timeout=5)
        assert resp.status_code == 200
        assert b"TokenGuard" in resp.content


class TestProxy:
    """Verify proxy rejects and forwards correctly."""

    def test_proxy_rejects_missing_key(self):
        resp = requests.post(
            f"{PROXY_URL}/v1/messages",
            json={"max_tokens": 1024, "messages": [], "model": "claude-sonnet-4-20250514"},
            timeout=5,
        )
        assert resp.status_code == 401

    def test_proxy_rejects_wrong_key(self):
        resp = requests.post(
            f"{PROXY_URL}/v1/messages",
            json={"max_tokens": 1024, "messages": [], "model": "claude-sonnet-4-20250514"},
            headers={"x-tokenguard-key": "wrong"},
            timeout=5,
        )
        assert resp.status_code == 403


class TestDashboardAPI:
    """Verify dashboard endpoints return valid schema."""

    def test_dashboard_summary_schema(self):
        resp = requests.get(f"{BACKEND_URL}/api/v1/dashboard/summary", timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_cost_usd" in data
        assert "total_requests" in data
        assert "total_input_tokens" in data
        assert "total_output_tokens" in data
        assert "cost_today" in data
        assert "cost_last_7_days" in data
        assert "cost_last_30_days" in data

    def test_dashboard_trends_returns_list(self):
        resp = requests.get(f"{BACKEND_URL}/api/v1/dashboard/trends?days=7", timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if data:
            assert "date" in data[0]
            assert "cost" in data[0]
            assert "tokens" in data[0]

    def test_dashboard_top_models_returns_list(self):
        resp = requests.get(f"{BACKEND_URL}/api/v1/dashboard/top-models", timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_dashboard_top_users_returns_list(self):
        resp = requests.get(f"{BACKEND_URL}/api/v1/dashboard/top-users", timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


class TestProxyUsagePipeline:
    """Verify proxy -> backend usage pipeline."""

    def test_save_via_internal_endpoint(self):
        """Direct save to backend internal endpoint (simulates proxy)."""
        resp = requests.post(
            f"{BACKEND_URL}/internal/usage",
            json={
                "organization_id": "00000000-0000-0000-0000-000000000001",
                "user_id": "00000000-0000-0000-0000-000000000002",
                "tool_name": "claude_code",
                "model_name": "claude-sonnet-4-20250514",
                "provider": "anthropic",
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_creation_tokens": 0,
                "cache_read_tokens": 0,
                "cost_usd": "0.001",
                "started_at": "2026-07-01T12:00:00Z",
                "context_usage_pct": "0.05",
            },
            headers={"x-tokenguard-key": TEST_KEY},
            timeout=5,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "saved"

    def test_alerts_list_empty(self):
        resp = requests.get(f"{BACKEND_URL}/api/v1/alerts/", timeout=5)
        assert resp.status_code == 200
        assert resp.json() == []
