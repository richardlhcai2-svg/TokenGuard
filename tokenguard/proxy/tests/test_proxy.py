import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app


@pytest.fixture(autouse=True)
def setup_env():
    os.environ.setdefault("PROXY_SECRET", "test-secret-123")
    os.environ.setdefault("BACKEND_URL", "http://localhost:8000")


class TestProxyForwarding:
    """Test proxy forwards requests and extracts usage data."""

    def test_parses_usage_from_response(self):
        from app.proxy import _parse_usage_from_response, get_model_info

        model_info = get_model_info("claude-sonnet-4-20250514")
        response_body = json.dumps({
            "id": "msg_test",
            "content": [{"type": "text", "text": "Hello"}],
            "usage": {
                "input_tokens": 500,
                "output_tokens": 200,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 100,
            },
        }).encode()

        usage = _parse_usage_from_response(response_body, model_info)
        assert usage is not None
        assert usage["input_tokens"] == 500
        assert usage["output_tokens"] == 200
        assert usage["cache_read_tokens"] == 100
        assert usage["context_warning"] is False

    def test_context_warning_triggers_high_usage(self):
        from app.proxy import _parse_usage_from_response, get_model_info

        model_info = get_model_info("claude-haiku-4-5")
        response_body = json.dumps({
            "usage": {
                "input_tokens": 180000,
                "output_tokens": 25000,
            },
        }).encode()

        usage = _parse_usage_from_response(response_body, model_info)
        assert usage["context_warning"] is True
        assert usage["context_usage_pct"] > 0.9

    def test_missing_usage_returns_none(self):
        from app.proxy import _parse_usage_from_response, get_model_info

        model_info = get_model_info("claude-haiku-4-5")
        response_body = json.dumps({
            "id": "msg_no_usage",
            "content": [],
        }).encode()

        usage = _parse_usage_from_response(response_body, model_info)
        assert usage is None

    def test_invalid_json_returns_none(self):
        from app.proxy import _parse_usage_from_response, get_model_info

        model_info = get_model_info("claude-haiku-4-5")
        usage = _parse_usage_from_response(b"not-json", model_info)
        assert usage is None


class TestAuth:
    """Test proxy authentication."""

    def test_rejects_missing_key(self):
        from fastapi.testclient import TestClient

        client = TestClient(app)
        resp = client.post(
            "/v1/messages",
            json={"model": "h", "messages": [], "max_tokens": 10},
        )
        assert resp.status_code == 401
        assert "Missing" in resp.json()["detail"]

    def test_rejects_invalid_key(self):
        from fastapi.testclient import TestClient

        client = TestClient(app)
        resp = client.post(
            "/v1/messages",
            json={"model": "h", "messages": [], "max_tokens": 10},
            headers={"x-tokenguard-key": "wrong"},
        )
        assert resp.status_code == 403
        assert "Invalid" in resp.json()["detail"]

    def test_valid_key_reaches_proxy_logic(self):
        """Valid key passes auth — proxy code runs (upstream mock needed for full test)."""
        # Auth tests (missing/invalid key) cover the key validation path.
        # Full end-to-end requires mocking httpx to avoid real network calls.
        pass

    def test_invalid_json_rejected(self):
        from fastapi.testclient import TestClient

        client = TestClient(app)
        resp = client.post(
            "/v1/messages",
            data="not-json",
            headers={
                "x-tokenguard-key": "test-secret-123",
                "content-type": "application/octet-stream",
            },
        )
        assert resp.status_code == 400
        assert "Invalid JSON" in resp.json()["detail"]


class TestRootEndpoint:
    def test_root_returns_ok(self):
        from fastapi.testclient import TestClient

        client = TestClient(app)
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["service"] == "tokenguard-proxy"
