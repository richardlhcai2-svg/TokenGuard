"""Configuration management — stores settings at ~/.tokenguard/config.json."""
import json
import os
import secrets
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".tokenguard"
CONFIG_FILE = CONFIG_DIR / "config.json"


def _ensure_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _load() -> dict:
    _ensure_dir()
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def _save(data: dict):
    _ensure_dir()
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)
    os.chmod(CONFIG_FILE, 0o600)


def get(key: str, default=None):
    return _load().get(key, default)


def set(key: str, value):
    data = _load()
    data[key] = value
    _save(data)


def get_api_keys() -> dict:
    """Get all configured provider API keys."""
    data = _load()
    keys = {}
    for provider in ["anthropic", "openai", "gemini", "deepseek"]:
        val = data.get(f"{provider}_api_key")
        if val:
            keys[provider] = val
    return keys


def get_proxy_secret() -> str:
    """Get or generate proxy auth secret."""
    data = _load()
    if "proxy_secret" not in data:
        data["proxy_secret"] = secrets.token_hex(16)
        _save(data)
    return data["proxy_secret"]


def list_keys() -> dict:
    """List all keys with secret values masked."""
    data = _load()
    result = {}
    for k, v in data.items():
        if k.endswith("_api_key") and v:
            result[k] = v[:8] + "..." + v[-4:] if len(v) > 16 else "***"
        else:
            result[k] = v
    return result


def is_configured() -> bool:
    return bool(get_api_keys())
