import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.utils import (
    estimate_input_tokens,
    get_model_info,
    should_trigger_warning,
)


class TestGetModelInfo:
    def test_known_sonnet_model(self):
        info = get_model_info("claude-sonnet-4-20250514")
        assert info["context_window"] == 200_000
        assert info["default_max"] == 8192

    def test_known_opus_model(self):
        info = get_model_info("claude-opus-4-20250514")
        assert info["context_window"] == 200_000
        assert info["default_max"] == 8192

    def test_alias_normalization(self):
        info = get_model_info("anthropic/claude-haiku-4-20250514")
        assert info["model_name"] == "claude-haiku-4-20250514"

    def test_unknown_model_defaults(self):
        info = get_model_info("some-new-model")
        assert info["context_window"] == 100_000
        assert info["default_max"] == 4096


class TestEstimateInputTokens:
    def test_simple_message(self):
        msgs = [{"role": "user", "content": "Hello world"}]
        tokens = estimate_input_tokens(msgs, [])
        assert tokens > 0

    def test_longer_content(self):
        msgs = [{"role": "user", "content": "A" * 400}]
        tokens = estimate_input_tokens(msgs, [])
        assert tokens >= 80  # ~4 chars per token

    def test_multimessage(self):
        msgs = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
            {"role": "user", "content": "How are you?"},
        ]
        tokens = estimate_input_tokens(msgs, [])
        assert tokens > 10

    def test_with_system_prompt(self):
        msgs = [{"role": "user", "content": "Hi"}]
        system = [{"type": "text", "text": "You are a helpful assistant."}]
        tokens = estimate_input_tokens(msgs, system)
        assert tokens > 0


class TestShouldTriggerWarning:
    def test_below_threshold(self):
        assert should_trigger_warning(0.5) is False

    def test_at_threshold(self):
        assert should_trigger_warning(0.9) is True

    def test_above_threshold(self):
        assert should_trigger_warning(0.95) is True

    def test_critical(self):
        assert should_trigger_warning(0.99) is True
