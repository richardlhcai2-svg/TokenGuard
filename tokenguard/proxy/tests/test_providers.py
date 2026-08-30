"""Tests for multi-provider pricing lookup."""
import pytest
from app.pricing import (
    get_model_cost,
    get_context_window,
    normalize_model_name,
    PROVIDER_COST_MAP,
)


class TestPricing:
    def test_get_known_anthropic_cost(self):
        cost = get_model_cost("claude-sonnet-4-20250514", "anthropic")
        assert cost["input_per_k"] > 0
        assert cost["output_per_k"] > 0

    def test_get_known_openai_cost(self):
        cost = get_model_cost("gpt-4.1", "openai")
        assert cost["input_per_k"] > 0
        assert cost["output_per_k"] > 0

    def test_get_known_gemini_cost(self):
        cost = get_model_cost("gemini-2.5-pro", "gemini")
        assert cost["input_per_k"] > 0
        assert cost["output_per_k"] > 0

    def test_get_known_deepseek_cost(self):
        cost = get_model_cost("deepseek-r1", "deepseek")
        assert cost["input_per_k"] == 0.00055
        assert cost["output_per_k"] == 0.00219
        assert cost["cache_read_per_k"] == 0.00014

    def test_get_known_groq_cost(self):
        cost = get_model_cost("llama-3.3-70b-versatile", "groq")
        assert cost["input_per_k"] == 0.00059
        assert cost["output_per_k"] == 0.00079

    def test_get_known_kimi_cost(self):
        cost = get_model_cost("kimi-k3", "kimi")
        assert cost["input_per_k"] == 0.00050
        assert cost["output_per_k"] == 0.00150

    def test_get_known_zhipu_cost(self):
        cost = get_model_cost("glm-4-plus", "zhipu")
        assert cost["input_per_k"] == 0.00080
        assert cost["output_per_k"] == 0.00160

    def test_get_known_qwen_cost(self):
        cost = get_model_cost("qwen-2.5-72b-instruct", "qwen")
        assert cost["input_per_k"] == 0.00035
        assert cost["output_per_k"] == 0.00070

    def test_normalize_model_name(self):
        assert normalize_model_name("gemini/gemini-3.7-flash (Antigravity)") == "gemini-3.7-flash"
        assert normalize_model_name("deepseek-ai/DeepSeek-V3") == "deepseek-v3"
        assert normalize_model_name("tokenrouter/moonshotai/kimi-k3") == "kimi-k3"
        assert normalize_model_name("groq/llama-3.3-70b-versatile") == "llama-3.3-70b-versatile"
        assert normalize_model_name("z-ai/glm-4-plus") == "glm-4-plus"

    def test_unknown_model_fallback(self):
        cost = get_model_cost("unknown-model", "anthropic")
        assert cost["input_per_k"] == 0.003
        assert cost["output_per_k"] == 0.015

    def test_unknown_provider_fallback(self):
        cost = get_model_cost("test-model", "unknown_provider")
        assert cost["input_per_k"] == 0.002
        assert cost["output_per_k"] == 0.008

    def test_model_context_window_known(self):
        ctx = get_context_window("claude-sonnet-4-20250514")
        assert ctx == 200000

    def test_model_context_window_gpt(self):
        ctx = get_context_window("gpt-4.1")
        assert ctx == 2000000  # gpt-4.1 has 2M context

    def test_model_context_window_gpt4o(self):
        ctx = get_context_window("gpt-4o")
        assert ctx == 128000

    def test_model_context_window_gemini(self):
        ctx = get_context_window("gemini-2.5-pro")
        assert ctx == 1048576

    def test_model_context_window_fallback(self):
        ctx = get_context_window("some-random-model-12345")
        assert ctx == 100000

    def test_provider_cost_map_has_all_providers(self):
        assert "anthropic" in PROVIDER_COST_MAP
        assert "openai" in PROVIDER_COST_MAP
        assert "gemini" in PROVIDER_COST_MAP
        assert "deepseek" in PROVIDER_COST_MAP
        assert "groq" in PROVIDER_COST_MAP
        assert "kimi" in PROVIDER_COST_MAP
        assert "zhipu" in PROVIDER_COST_MAP
        assert "qwen" in PROVIDER_COST_MAP
