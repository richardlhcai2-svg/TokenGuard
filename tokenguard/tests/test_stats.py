"""Tests for stats module formatting."""
from tokenguard.stats import _summary_table, _models_table, _feed_table


class TestStatsFormatting:
    def test_summary_table(self):
        t = _summary_table({
            "total_spent": 52.30, "total_tokens": 1200000,
            "total_requests": 342, "avg_cost_per_req": 0.15,
        })
        assert t.row_count == 4

    def test_models_empty(self):
        assert _models_table([]).row_count == 0

    def test_models_table(self):
        t = _models_table([{
            "model_name": "claude-sonnet-4", "provider": "anthropic",
            "total_spent": 28.50, "total_tokens": 500000, "requests": 100,
        }])
        assert t.row_count == 1

    def test_feed_empty(self):
        assert _feed_table([]).row_count == 0
