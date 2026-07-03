"""Tests for config module."""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from tokenguard import config as cfg


@pytest.fixture
def tmpdir():
    with tempfile.TemporaryDirectory() as d:
        with patch.object(cfg, "CONFIG_DIR", Path(d)):
            with patch.object(cfg, "CONFIG_FILE", Path(d) / "config.json"):
                yield Path(d)


class TestConfig:
    def test_set_and_get(self, tmpdir):
        cfg.set("test_key", "test_value")
        assert cfg.get("test_key") == "test_value"

    def test_get_default(self, tmpdir):
        assert cfg.get("nonexistent", "fallback") == "fallback"

    def test_get_api_keys(self, tmpdir):
        cfg.set("anthropic_api_key", "sk-ant-test123")
        cfg.set("openai_api_key", "sk-openai-test456")
        keys = cfg.get_api_keys()
        assert keys["anthropic"] == "sk-ant-test123"
        assert keys["openai"] == "sk-openai-test456"
        assert "gemini" not in keys

    def test_proxy_secret_generates(self, tmpdir):
        secret = cfg.get_proxy_secret()
        assert len(secret) == 32
        assert cfg.get_proxy_secret() == secret

    def test_is_configured_empty(self, tmpdir):
        assert not cfg.is_configured()

    def test_is_configured_with_key(self, tmpdir):
        cfg.set("anthropic_api_key", "sk-ant-test")
        assert cfg.is_configured()

    def test_list_keys_masks_secrets(self, tmpdir):
        cfg.set("anthropic_api_key", "sk-ant-1234567890abcd")
        listed = cfg.list_keys()
        assert "..." in listed["anthropic_api_key"]
        assert listed["anthropic_api_key"].startswith("sk-ant-")

    def test_file_permissions(self, tmpdir):
        cfg.set("key", "val")
        mode = os.stat(tmpdir / "config.json").st_mode & 0o777
        assert mode == 0o600
