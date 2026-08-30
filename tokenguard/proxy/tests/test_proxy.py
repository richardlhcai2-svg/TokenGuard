import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app


@pytest.fixture(autouse=True)
def setup_env():
    os.environ["PROXY_SECRET"] = "test-secret-123"
    os.environ.setdefault("BACKEND_URL", "http://localhost:8000")


class TestProxyForwarding:
    """Test proxy forwards requests and extracts usage data."""

    def test_get_model_info_known(self):
        from app.utils import get_model_info

        info = get_model_info("claude-sonnet-4-20250514")
        assert info["model_name"] == "claude-sonnet-4-20250514"
        assert info["context_window"] == 200000
        assert info["default_max"] == 8192

    def test_get_model_info_unknown_fallback(self):
        from app.utils import get_model_info

        info = get_model_info("unknown-model")
        assert info["context_window"] == 100000  # fallback
        assert info["default_max"] == 4096

    def test_proxy_route_without_prefix(self):
        """Legacy: no prefix defaults to Anthropic handler."""
        from fastapi.testclient import TestClient

        client = TestClient(app)
        resp = client.post(
            "/v1/messages",
            json={"model": "claude-sonnet-4-20250514", "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 10},
            headers={"x-tokenguard-key": "test-secret-123"},
        )
        # Should get upstream error (no/invalid api key) rather than proxy secret auth error
        assert resp.status_code in (400, 401, 500, 502)

    def test_proxy_route_with_anthropic_prefix(self):
        """Anthropic prefix routes to Anthropic handler."""
        from fastapi.testclient import TestClient

        client = TestClient(app)
        resp = client.post(
            "/anthropic/v1/messages",
            json={"model": "claude-sonnet-4-20250514", "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 10},
            headers={"x-tokenguard-key": "test-secret-123"},
        )
        assert resp.status_code in (400, 401, 500, 502)

    def test_proxy_route_with_openai_prefix(self):
        """OpenAI prefix routes to OpenAI handler."""
        from fastapi.testclient import TestClient

        client = TestClient(app)
        resp = client.post(
            "/openai/v1/chat/completions",
            json={"model": "gpt-4.1", "messages": [{"role": "user", "content": "Hi"}]},
            headers={"x-tokenguard-key": "test-secret-123"},
        )
        # Missing x-openai-key → 401
        assert resp.status_code == 401

    def test_proxy_route_with_gemini_prefix(self):
        """Gemini prefix routes to Gemini handler."""
        from fastapi.testclient import TestClient

        client = TestClient(app)
        resp = client.post(
            "/gemini/v1beta/models/gemini-2.5-pro:generateContent",
            json={"contents": [{"parts": [{"text": "Hi"}]}]},
            headers={"x-tokenguard-key": "test-secret-123"},
        )
        # Missing x-gemini-key → 401
        assert resp.status_code == 401

    def test_proxy_route_with_deepseek_prefix(self):
        """DeepSeek prefix routes to OpenAI-compatible handler."""
        from fastapi.testclient import TestClient

        client = TestClient(app)
        resp = client.post(
            "/deepseek/v1/chat/completions",
            json={"model": "deepseek-chat", "messages": [{"role": "user", "content": "Hi"}]},
            headers={"x-tokenguard-key": "test-secret-123"},
        )
        # Missing x-deepseek-key → 401
        assert resp.status_code == 401


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


class TestAnthropicSSEParsing:
    """Test Anthropic SSE streaming usage extraction."""

    def test_anthropic_sse_usage_extraction(self):
        from app.handlers.anthropic import _extract_and_save_sse, _resolve_api_key

        sse_body = (
            b'event: message_start\n'
            b'data: {"type":"message_start","message":{"id":"msg_1","type":"message","role":"assistant","model":"claude-sonnet-4-20250514","usage":{"input_tokens":250,"output_tokens":1,"cache_creation_input_tokens":0,"cache_read_input_tokens":50}}}\n\n'
            b'event: content_block_delta\n'
            b'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}\n\n'
            b'event: message_delta\n'
            b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":75}}\n\n'
            b'event: message_stop\n'
            b'data: {"type":"message_stop"}\n\n'
        )

        with patch("app.proxy._save_usage_async") as mock_save:
            _extract_and_save_sse(
                sse_body,
                model_name="claude-sonnet-4-20250514",
                cost={"input_per_k": 0.003, "output_per_k": 0.015},
                context_window=200000,
                start_time=0,
                session_id="test-session-123",
            )

            assert mock_save.called
            call_args = mock_save.call_args[0][0]
            assert call_args["input_tokens"] == 250
            assert call_args["output_tokens"] == 75
            assert call_args["cache_read_tokens"] == 50
            assert call_args["provider"] == "anthropic"
            assert call_args["model_name"] == "claude-sonnet-4-20250514"
            assert call_args["cost_usd"] > 0

    def test_anthropic_key_fallback_headers(self):
        from app.handlers.anthropic import _resolve_api_key

        headers = {"x-api-key": "sk-ant-test-key-123"}
        key = _resolve_api_key(headers)
        assert key == "sk-ant-test-key-123"

