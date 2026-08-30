"""Tests for OpenAI-compatible handler usage parsing."""
import json
import pytest
from unittest.mock import patch
from app.handlers.openai import _extract_and_save_json, _extract_and_save_sse, _resolve_api_key


class TestOpenAIUsageParsing:
    """Test OpenAI response usage parsing."""

    def test_parse_non_streaming_usage(self):
        """Test parsing usage from a standard non-streaming OpenAI response."""
        mock_response = {
            "id": "chatcmpl-xxx",
            "choices": [{"message": {"role": "assistant", "content": "Hello"}}],
            "usage": {"prompt_tokens": 150, "completion_tokens": 50, "total_tokens": 200},
            "model": "gpt-4.1",
        }
        response_body = json.dumps(mock_response).encode("utf-8")

        with patch("app.proxy._save_usage_async") as mock_save:
            _extract_and_save_json(
                response_body,
                model_name="gpt-4.1",
                cost={"input_per_k": 0.004, "output_per_k": 0.016},
                context_window=128000,
                start_time=0,
                session_id=None,
                provider="openai",
            )

            assert mock_save.called
            call_args = mock_save.call_args[0][0]
            assert call_args["input_tokens"] == 150
            assert call_args["output_tokens"] == 50
            assert call_args["provider"] == "openai"
            assert call_args["model_name"] == "gpt-4.1"
            assert call_args["cost_usd"] > 0

    def test_parse_sse_streaming_usage_with_usage_block(self):
        """Test parsing SSE stream that includes usage block in final chunk."""
        sse_body = (
            b'data: {"id":"chatcmpl-1","choices":[{"delta":{"content":"Hi"}}],"model":"gpt-4o"}\n\n'
            b'data: {"id":"chatcmpl-1","choices":[],"usage":{"prompt_tokens":120,"completion_tokens":30},"model":"gpt-4o"}\n\n'
            b'data: [DONE]\n\n'
        )

        with patch("app.proxy._save_usage_async") as mock_save:
            _extract_and_save_sse(
                sse_body,
                model_name="gpt-4o",
                cost={"input_per_k": 0.0025, "output_per_k": 0.010},
                context_window=128000,
                start_time=0,
                session_id=None,
                provider="openai",
            )

            assert mock_save.called
            call_args = mock_save.call_args[0][0]
            assert call_args["input_tokens"] == 120
            assert call_args["output_tokens"] == 30
            assert call_args["provider"] == "openai"
            assert call_args["cost_usd"] > 0

    def test_parse_missing_usage_returns_none(self):
        """No usage data should not crash."""
        mock_response = {
            "id": "chatcmpl-xxx",
            "choices": [{"message": {"role": "assistant", "content": "Hi"}}],
        }
        response_body = json.dumps(mock_response).encode("utf-8")

        with patch("app.proxy._save_usage_async") as mock_save:
            _extract_and_save_json(
                response_body, "gpt-4.1",
                {"input_per_k": 0.004, "output_per_k": 0.016},
                128000, 0, None, "openai",
            )
            assert not mock_save.called

    def test_deepseek_usage_parsing(self):
        """DeepSeek has same API format as OpenAI."""
        mock_response = {
            "id": "xxx",
            "choices": [{"message": {"role": "assistant", "content": "Hello"}}],
            "usage": {"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300},
        }
        response_body = json.dumps(mock_response).encode("utf-8")

        with patch("app.proxy._save_usage_async") as mock_save:
            _extract_and_save_json(
                response_body, "deepseek-r1",
                {"input_per_k": 0.00055, "output_per_k": 0.00219},
                65536, 0, None, "deepseek",
            )
            assert mock_save.called
            call_args = mock_save.call_args[0][0]
            assert call_args["provider"] == "deepseek"
            assert call_args["input_tokens"] == 200

    def test_api_key_fallback_bearer(self):
        headers = {"authorization": "Bearer sk-test-openai-key-123"}
        key = _resolve_api_key(headers, "openai")
        assert key == "sk-test-openai-key-123"

