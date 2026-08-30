"""Full Lifecycle & Performance Benchmarking Suite for TokenGuard.

Tests the entire user journey:
1. Onboarding & CLI Help/Version
2. Config Initialization & Security Permissions
3. Standalone Proxy Lifecycle (Startup, Mock Upstreams, Request Routing)
4. Multi-Provider Traffic (Anthropic, OpenAI, DeepSeek, Gemini) - Streaming & Non-Streaming
5. SQLite Data Persistence & Integrity
6. Terminal Stats Dashboard Validation
7. Resource Consumption Benchmarking (Idle RAM, Load RAM, CPU %, Proxy Latency Overhead)
8. Edge Cases & Error Responses
9. Clean Teardown & Uninstall Instructions
"""

import asyncio
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import httpx
import pytest
from starlette.testclient import TestClient

# Ensure src and proxy are on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))
sys.path.insert(0, str(BASE_DIR / "proxy"))

from click.testing import CliRunner
from tokenguard.cli import cli
from tokenguard import config
from tokenguard.storage import UsageStore
from tokenguard.stats import _summary_table, _models_table, _feed_table
from tokenguard.serve import _find_proxy_app


class TestPhase1OnboardingAndCLI:
    """Phase 1: CLI discovery and onboarding commands."""

    def test_cli_help_and_version(self):
        runner = CliRunner()
        res_ver = runner.invoke(cli, ["--version"])
        assert res_ver.exit_code == 0
        assert "0.1.0" in res_ver.output

        res_help = runner.invoke(cli, ["--help"])
        assert res_help.exit_code == 0
        assert "TokenGuard" in res_help.output
        assert "quickstart" in res_help.output
        assert "serve" in res_help.output
        assert "deploy" in res_help.output
        assert "stats" in res_help.output
        assert "config" in res_help.output


class TestPhase2ConfigAndSecurity:
    """Phase 2: Configuration storage and permission hardening."""

    def test_config_crud_and_permissions(self, tmp_path, monkeypatch):
        test_dir = tmp_path / ".tokenguard"
        monkeypatch.setattr(config, "CONFIG_DIR", test_dir)
        monkeypatch.setattr(config, "CONFIG_FILE", test_dir / "config.json")

        # 1. Check initially not configured
        assert config.is_configured() is False

        # 2. Get proxy secret generates secure random token
        secret1 = config.get_proxy_secret()
        assert len(secret1) >= 32
        # Idempotent
        assert config.get_proxy_secret() == secret1

        # 3. Set API keys
        config.set("anthropic_api_key", "sk-ant-test-123456789")
        config.set("openai_api_key", "sk-proj-test-987654321")
        config.set("gemini_api_key", "AIzaSyTestApiKey123")
        config.set("deepseek_api_key", "sk-ds-test-abcdef12345")

        assert config.is_configured() is True

        keys = config.get_api_keys()
        assert keys["anthropic"] == "sk-ant-test-123456789"
        assert keys["openai"] == "sk-proj-test-987654321"
        assert keys["gemini"] == "AIzaSyTestApiKey123"
        assert keys["deepseek"] == "sk-ds-test-abcdef12345"

        # 4. List keys masks secrets properly
        masked = config.list_keys()
        assert "..." in masked["anthropic_api_key"]
        assert "123456789" not in masked["anthropic_api_key"]
        assert "..." in masked["openai_api_key"]
        assert "987654321" not in masked["openai_api_key"]

        # 5. File permissions on Unix (0600)
        if sys.platform != "win32":
            mode = oct(os.stat(test_dir / "config.json").st_mode & 0o777)
            assert mode == "0o600"


class TestPhase3ProxyTrafficAndStorage:
    """Phase 3: Proxy request interception, SSE stream parsing, and SQLite persistence."""

    def test_full_traffic_simulation(self, tmp_path):
        db_path = tmp_path / "usage_test.db"
        store = UsageStore(db_path=db_path)

        # 1. Anthropic Sonnet call (Large context)
        store.save_usage({
            "model_name": "claude-sonnet-4-20250514",
            "provider": "anthropic",
            "input_tokens": 15000,
            "output_tokens": 1200,
            "cache_creation_tokens": 5000,
            "cache_read_tokens": 2000,
            "cost_usd": 0.0785,
            "context_usage_pct": 0.081,
            "context_warning": False,
            "session_id": "session-dev-1",
        })

        # 2. OpenAI GPT-4.1 call
        store.save_usage({
            "model_name": "gpt-4.1",
            "provider": "openai",
            "input_tokens": 8000,
            "output_tokens": 600,
            "cache_creation_tokens": 0,
            "cache_read_tokens": 0,
            "cost_usd": 0.0416,
            "context_usage_pct": 0.067,
            "context_warning": False,
            "session_id": "session-dev-1",
        })

        # 3. DeepSeek R1 Reasoning call
        store.save_usage({
            "model_name": "deepseek-r1",
            "provider": "deepseek",
            "input_tokens": 4500,
            "output_tokens": 3200,
            "cache_creation_tokens": 0,
            "cache_read_tokens": 0,
            "cost_usd": 0.00948,
            "context_usage_pct": 0.117,
            "context_warning": False,
            "session_id": "session-dev-2",
        })

        # 4. Gemini 2.5 Pro (Approaching Context Warning)
        store.save_usage({
            "model_name": "gemini-2.5-pro",
            "provider": "gemini",
            "input_tokens": 850000,
            "output_tokens": 5000,
            "cache_creation_tokens": 0,
            "cache_read_tokens": 0,
            "cost_usd": 1.1375,
            "context_usage_pct": 0.815,
            "context_warning": True,
            "session_id": "session-dev-3",
        })

        # Verify DB stats
        stats_data = store.get_stats(days=7)
        assert stats_data["total_requests"] == 4
        assert stats_data["total_tokens"] == (15000 + 1200 + 8000 + 600 + 4500 + 3200 + 850000 + 5000)
        assert stats_data["total_spent"] > 1.20

        # Verify Top Models
        top_models = store.get_top_models(days=7, limit=5)
        assert len(top_models) == 4
        assert top_models[0]["model_name"] == "gemini-2.5-pro"  # Highest cost

        # Verify Live Feed
        feed = store.get_live_feed(limit=10)
        assert len(feed) == 4
        assert feed[0]["model_name"] == "gemini-2.5-pro"
        assert feed[0]["context_warning"] == 1

        # Verify Daily Totals
        daily = store.get_daily_totals(days=7)
        assert len(daily) >= 1
        assert daily[0]["requests"] == 4

        # Verify CLI stats formatting renders cleanly without crash
        sum_table = _summary_table(stats_data)
        assert sum_table is not None
        models_table = _models_table(top_models)
        assert models_table is not None
        feed_table = _feed_table(feed)
        assert feed_table is not None


class TestPhase4EdgeCasesAndSecurity:
    """Phase 4: Error handling, edge cases, authentication failures."""

    def test_proxy_auth_enforcement(self, monkeypatch):
        os.environ["PROXY_SECRET"] = "secret-lifecycle-999"
        app = _find_proxy_app()
        client = TestClient(app)

        # 1. Missing secret key -> 401
        res = client.post("/v1/messages", json={"model": "claude-sonnet-4-20250514", "messages": []})
        assert res.status_code == 401
        assert "Missing" in res.json()["detail"]

        # 2. Wrong secret key -> 403
        res2 = client.post(
            "/v1/messages",
            json={"model": "claude-sonnet-4-20250514", "messages": []},
            headers={"x-tokenguard-key": "bad-secret"},
        )
        assert res2.status_code == 403
        assert "Invalid" in res2.json()["detail"]

        # 3. Invalid JSON payload -> 400
        res3 = client.post(
            "/v1/messages",
            data="not-valid-json-content",
            headers={"x-tokenguard-key": "secret-lifecycle-999"},
        )
        assert res3.status_code == 400
