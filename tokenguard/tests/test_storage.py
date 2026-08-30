"""Tests for SQLite storage engine."""
import tempfile
import time
from pathlib import Path
import pytest
from tokenguard.storage import UsageStore


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield UsageStore(db_path=Path(tmpdir) / "test.db")


class TestUsageStore:
    def test_save_and_count(self, store):
        store.save_usage({
            "model_name": "claude-sonnet-4",
            "provider": "anthropic",
            "input_tokens": 100,
            "output_tokens": 50,
            "cost_usd": 0.0075,
            "started_at": time.time(),
        })
        s = store.get_stats(7)
        assert s["total_requests"] == 1
        assert s["total_spent"] == 0.0075
        assert s["total_tokens"] == 150

    def test_empty_store(self, store):
        s = store.get_stats(7)
        assert s["total_requests"] == 0
        assert s["total_spent"] == 0.0
        assert store.get_top_models() == []
        assert store.get_live_feed() == []

    def test_top_models_ordering(self, store):
        now = time.time()
        store.save_usage({
            "model_name": "gpt-4.1", "provider": "openai",
            "cost_usd": 0.02, "started_at": now,
            "input_tokens": 100, "output_tokens": 50,
            "cache_creation_tokens": 0, "cache_read_tokens": 0,
            "context_usage_pct": 0, "context_warning": False,
        })
        store.save_usage({
            "model_name": "claude-sonnet-4", "provider": "anthropic",
            "cost_usd": 0.01, "started_at": now,
            "input_tokens": 100, "output_tokens": 50,
            "cache_creation_tokens": 0, "cache_read_tokens": 0,
            "context_usage_pct": 0, "context_warning": False,
        })
        top = store.get_top_models(7, 5)
        assert top[0]["model_name"] == "gpt-4.1"
        assert top[1]["model_name"] == "claude-sonnet-4"

    def test_live_feed_ordering(self, store):
        now = time.time()
        store.save_usage({
            "model_name": "old", "provider": "p",
            "cost_usd": 0.001, "started_at": now - 10,
            "input_tokens": 10, "output_tokens": 10,
            "cache_creation_tokens": 0, "cache_read_tokens": 0,
            "context_usage_pct": 0, "context_warning": False,
        })
        store.save_usage({
            "model_name": "new", "provider": "p",
            "cost_usd": 0.001, "started_at": now,
            "input_tokens": 10, "output_tokens": 10,
            "cache_creation_tokens": 0, "cache_read_tokens": 0,
            "context_usage_pct": 0, "context_warning": False,
        })
        feed = store.get_live_feed(2)
        assert feed[0]["model_name"] == "new"

    def test_daily_totals(self, store):
        now = time.time()
        store.save_usage({
            "model_name": "m", "provider": "p",
            "cost_usd": 1.0, "started_at": now - 86400,
            "input_tokens": 100, "output_tokens": 50,
            "cache_creation_tokens": 0, "cache_read_tokens": 0,
            "context_usage_pct": 0, "context_warning": False,
        })
        store.save_usage({
            "model_name": "m", "provider": "p",
            "cost_usd": 2.0, "started_at": now,
            "input_tokens": 100, "output_tokens": 50,
            "cache_creation_tokens": 0, "cache_read_tokens": 0,
            "context_usage_pct": 0, "context_warning": False,
        })
        daily = store.get_daily_totals(7)
        assert len(daily) >= 2
