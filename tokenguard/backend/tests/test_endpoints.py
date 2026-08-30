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

        # Dashboard savings + recommendations + optimizations endpoints
        assert "/api/v1/dashboard/savings" in paths
        assert "get" in paths["/api/v1/dashboard/savings"]
        assert "/api/v1/dashboard/recommendations" in paths
        assert "get" in paths["/api/v1/dashboard/recommendations"]
        assert "/api/v1/dashboard/optimizations" in paths
        assert "get" in paths["/api/v1/dashboard/optimizations"]


class TestSavingsEndpoint:
    def test_savings_empty_data(self):
        """Empty usage → zero savings."""
        from app.core.database import get_async_db

        mock_rows = MagicMock()
        mock_rows.fetchall.return_value = []

        mock_session = AsyncMock()

        async def mock_execute(stmt):
            return mock_rows

        mock_session.execute = mock_execute

        async def mock_gen():
            yield mock_session

        app.dependency_overrides[get_async_db] = mock_gen
        try:
            resp = client.get("/api/v1/dashboard/savings")
            assert resp.status_code == 200
            data = resp.json()
            assert float(data["total_actual_cost_usd"]) == 0.0
            assert data["savings_pct"] == 0.0
            assert data["per_model"] == []
        finally:
            app.dependency_overrides.clear()

    def test_savings_with_data(self):
        """Has usage → non-zero savings estimate."""
        from app.core.database import get_async_db
        from decimal import Decimal
        from datetime import datetime, timezone

        mock_record = MagicMock()
        mock_record.model_name = "claude-opus-4-20250514"
        mock_record.provider = "anthropic"
        mock_record.task_type = "debugging"
        mock_record.cost_usd = Decimal("1.50")
        mock_record.input_tokens = 10000
        mock_record.output_tokens = 5000

        mock_rows = MagicMock()
        mock_rows.fetchall.return_value = [mock_record]

        mock_session = AsyncMock()

        async def mock_execute(stmt):
            return mock_rows

        mock_session.execute = mock_execute

        async def mock_gen():
            yield mock_session

        app.dependency_overrides[get_async_db] = mock_gen
        try:
            resp = client.get("/api/v1/dashboard/savings?days=30")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_actual_cost_usd"] is not None
            assert float(data["total_actual_cost_usd"]) > 0
            assert len(data["per_model"]) >= 1
            assert data["per_model"][0]["recommended_model"] == "claude-sonnet"  # cheapest for debugging
        finally:
            app.dependency_overrides.clear()


class TestOptimizationsEndpoint:
    def test_optimizations_empty_data(self):
        """Empty usage → zero optimizations."""
        from app.core.database import get_async_db

        mock_rows = MagicMock()
        mock_rows.fetchall.return_value = []

        mock_session = AsyncMock()

        async def mock_execute(stmt):
            return mock_rows

        mock_session.execute = mock_execute

        async def mock_gen():
            yield mock_session

        app.dependency_overrides[get_async_db] = mock_gen
        try:
            resp = client.get("/api/v1/dashboard/optimizations")
            assert resp.status_code == 200
            data = resp.json()
            assert float(data["total_savings_usd"]) == 0.0
            assert data["action_count"] == 0
            assert data["actions"] == []
        finally:
            app.dependency_overrides.clear()

    def test_optimizations_with_usage(self):
        """Usage data generates optimization actions."""
        from app.core.database import get_async_db
        from decimal import Decimal

        mock_record = MagicMock()
        mock_record.model_name = "claude-opus-4-20250514"
        mock_record.provider = "anthropic"
        mock_record.task_type = "documentation"
        mock_record.cost_usd = Decimal("100.00")
        mock_record.input_tokens = 500000
        mock_record.output_tokens = 200000

        mock_rows = MagicMock()
        mock_rows.fetchall.return_value = [mock_record]

        mock_session = AsyncMock()

        async def mock_execute(stmt):
            return mock_rows

        mock_session.execute = mock_execute

        async def mock_gen():
            yield mock_session

        app.dependency_overrides[get_async_db] = mock_gen
        try:
            resp = client.get("/api/v1/dashboard/optimizations?min_savings=0")
            assert resp.status_code == 200
            data = resp.json()
            assert data["action_count"] >= 1
            assert data["actions"][0]["recommended_model"] == "claude-haiku"
            assert data["actions"][0]["priority"] == "high"  # $100 savings should be high priority
        finally:
            app.dependency_overrides.clear()
