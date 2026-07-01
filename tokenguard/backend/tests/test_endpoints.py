import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from app.main import app

from app.api.endpoints import set_proxy_secret
set_proxy_secret("test-secret")

client = TestClient(app)


class TestProxyUsageEndpoint:
    def test_save_usage_success(self):
        from app.core.database import get_async_db

        mock_session = AsyncMock()
        mock_usage = MagicMock()
        mock_usage.id = "test-id-123"
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock(return_value=mock_usage)
        mock_session.add = MagicMock()

        async def mock_gen():
            yield mock_session

        app.dependency_overrides[get_async_db] = mock_gen
        try:
            resp = client.post(
                "/internal/usage",
                json={
                    "organization_id": "00000000-0000-0000-0000-000000000001",
                    "user_id": "00000000-0000-0000-0000-000000000002",
                    "tool_name": "claude_code",
                    "model_name": "claude-sonnet-4-20250514",
                    "input_tokens": 500,
                    "output_tokens": 200,
                    "cache_creation_tokens": 0,
                    "cache_read_tokens": 100,
                    "cost_usd": "0.15",
                    "started_at": "2026-07-01T12:00:00Z",
                },
                headers={"x-tokenguard-key": "test-secret"},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "saved"
        finally:
            app.dependency_overrides.clear()

    def test_proxy_rejects_invalid_key(self):
        resp = client.post(
            "/internal/usage",
            json={
                "organization_id": "00000000-0000-0000-0000-000000000001",
                "user_id": "00000000-0000-0000-0000-000000000002",
                "tool_name": "claude_code",
                "cost_usd": "0.10",
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_creation_tokens": 0,
                "cache_read_tokens": 0,
                "started_at": "2026-07-01T12:00:00Z",
            },
            headers={"x-tokenguard-key": "wrong-key"},
        )
        assert resp.status_code == 403

    def test_proxy_rejects_missing_key(self):
        resp = client.post(
            "/internal/usage",
            json={
                "organization_id": "00000000-0000-0000-0000-000000000001",
                "user_id": "00000000-0000-0000-0000-000000000002",
                "tool_name": "claude_code",
                "cost_usd": "0.10",
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_creation_tokens": 0,
                "cache_read_tokens": 0,
                "started_at": "2026-07-01T12:00:00Z",
            },
        )
        assert resp.status_code == 422


class TestHealth:
    def test_health_ok(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestRouteRegistration:
    """Verify all routes are registered via OpenAPI schema."""

    def test_all_routes_registered(self):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        paths = resp.json()["paths"]

        # Proxy endpoint
        assert "/internal/usage" in paths
        assert "post" in paths["/internal/usage"]

        # Dashboard endpoints
        assert "/api/v1/dashboard/summary" in paths
        assert "/api/v1/dashboard/trends" in paths
        assert "/api/v1/dashboard/top-models" in paths
        assert "/api/v1/dashboard/top-users" in paths
