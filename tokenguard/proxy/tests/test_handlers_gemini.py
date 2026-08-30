"""Tests for Google Gemini handler usage parsing."""
import json
import pytest
from unittest.mock import patch
from app.handlers.gemini import _extract_and_save_json, _extract_and_save_stream, _resolve_api_key


class TestGeminiUsageParsing:
    """Test Gemini response usage parsing."""

    def test_parse_non_streaming_usage(self):
        """Test parsing usageMetadata from a Gemini response."""
        mock_response = {
            "candidates": [{"content": {"parts": [{"text": "Hello"}]}}],
            "usageMetadata": {
                "promptTokenCount": 100,
                "candidatesTokenCount": 50,
                "totalTokenCount": 150,
            },
        }
        response_body = json.dumps(mock_response).encode("utf-8")

        with patch("app.proxy._save_usage_async") as mock_save:
            _extract_and_save_json(
                response_body, "gemini-2.5-pro",
                {"input_per_k": 0.00125, "output_per_k": 0.015},
                1048576, 0, None,
            )

            assert mock_save.called
            call_args = mock_save.call_args[0][0]
            assert call_args["input_tokens"] == 100
            assert call_args["output_tokens"] == 50
            assert call_args["provider"] == "gemini"
            assert call_args["model_name"] == "gemini-2.5-pro"
            assert call_args["cost_usd"] > 0

    def test_parse_streaming_usage_array(self):
        """Test parsing Gemini chunk array with usageMetadata."""
        stream_data = json.dumps([
            {"candidates": [{"content": {"parts": [{"text": "Hello"}]}}]},
            {
                "candidates": [{"content": {"parts": [{"text": " world"}]}}],
                "usageMetadata": {"promptTokenCount": 80, "candidatesTokenCount": 40},
            },
        ]).encode("utf-8")

        with patch("app.proxy._save_usage_async") as mock_save:
            _extract_and_save_stream(
                stream_data, "gemini-2.5-flash",
                {"input_per_k": 0.00015, "output_per_k": 0.001},
                1048576, 0, None,
            )

            assert mock_save.called
            call_args = mock_save.call_args[0][0]
            assert call_args["input_tokens"] == 80
            assert call_args["output_tokens"] == 40
            assert call_args["provider"] == "gemini"

    def test_api_key_fallback(self):
        headers = {"x-goog-api-key": "AIzaSyTest123"}
        key = _resolve_api_key(headers)
        assert key == "AIzaSyTest123"

