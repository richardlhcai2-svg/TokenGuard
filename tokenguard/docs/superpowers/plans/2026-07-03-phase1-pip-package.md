# Phase 1: Pip Package & One-Click Installation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make TokenGuard installable via `pip install tokenguard` with a `tg` CLI that provides `quickstart` wizard, `serve` (standalone proxy + SQLite), `deploy` (Docker stack), `stats` (terminal dashboard), and `config` management.

**Architecture:** New `src/tokenguard/` package at project root houses CLI and standalone proxy. The existing `proxy/app/` code is shared with the package via runtime `sys.path` for development and bundled for pip install via `package_data`. Existing Docker stack is untouched.

**Tech Stack:** Python 3.10+, Click (CLI framework), stdlib `sqlite3`, `rich` (terminal UI), httpx, uvicorn, FastAPI

## Global Constraints

- No breaking changes to existing Docker Compose stack
- Existing `_save_usage_async` to backend remains primary path; SQLite is fallback
- API keys stored encrypted at `~/.tokenguard/config`
- All existing proxy tests (43) must still pass
- All existing backend tests (24) must still pass
- `tg quickstart` produces a usable config file
- `tg serve` starts proxy on port 8001 without Docker

---

### Task 1: Create pip package structure and pyproject.toml

**Files:**
- Create: `src/tokenguard/__init__.py`
- Create: `src/tokenguard/__main__.py`
- Create: `pyproject.toml` (at project root)
- Create: `MANIFEST.in`

**Interfaces:**
- Produces: `tokenguard` pip-installable package with `tg` console entry point

- [ ] **Step 1: Create pyproject.toml**

```toml
# /Users/mac/projects/tokenguard/tokenguard/pyproject.toml
[build-system]
requires = ["setuptools>=64", "wheel"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "tokenguard"
version = "0.1.0"
description = "AI Cost Intelligence — proxy, track, and optimize your AI API spending"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
authors = [{name = "TokenGuard"}]
classifiers = [
    "Programming Language :: Python :: 3",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
]

dependencies = [
    "click>=8.0",
    "rich>=13.0",
    "httpx>=0.27",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "pydantic>=2.9",
    "cryptography>=41.0",
]

[project.scripts]
tg = "tokenguard.cli:cli"

[tool.setuptools.packages.find]
where = ["src"]
include = ["tokenguard*"]

[tool.setuptools.package-data]
"tokenguard.proxy" = ["**/*.py"]
```

- [ ] **Step 2: Create package init and __main__**

```python
# src/tokenguard/__init__.py
"""TokenGuard — AI Cost Intelligence."""

__version__ = "0.1.0"
```

```python
# src/tokenguard/__main__.py
"""python -m tokenguard"""
from .cli import cli
cli()
```

- [ ] **Step 3: Create MANIFEST.in**

```
# /Users/mac/projects/tokenguard/tokenguard/MANIFEST.in
graft src/tokenguard/proxy
```

- [ ] **Step 4: Test pip install**

Run:
```bash
cd /Users/mac/projects/tokenguard/tokenguard && pip install -e .
```

Expected: `tg --help` produces help output

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml MANIFEST.in src/tokenguard/__init__.py src/tokenguard/__main__.py
git commit -m "feat: add pip package scaffolding"
```

---

### Task 2: Create CLI dispatcher framework

**Files:**
- Create: `src/tokenguard/cli.py`

**Interfaces:**
- Consumes: subcommand modules (`quickstart.py`, `serve.py`, `deploy.py`, `stats.py`, `config.py`)
- Produces: `cli()` click group with subcommands

- [ ] **Step 1: Write the CLI entry point**

```python
# src/tokenguard/cli.py
"""TokenGuard CLI — tg command."""
import click

from . import __version__


@click.group()
@click.version_option(__version__, "--version", "-V")
def cli():
    """TokenGuard — AI Cost Intelligence CLI.
    
    Proxy, track, and optimize your AI API spending.
    """


@cli.command()
def quickstart():
    """Interactive setup wizard — configure API keys and start."""
    from .quickstart import quickstart
    quickstart()


@cli.command()
@click.option("--port", default=8001, help="Proxy listen port")
@click.option("--host", default="0.0.0.0", help="Proxy bind address")
@click.option("--reload", is_flag=True, help="Auto-reload on code changes")
def serve(port, host, reload):
    """Start standalone proxy with local SQLite storage."""
    from .serve import serve
    serve(port=port, host=host, reload=reload)


@cli.command()
@click.option("--port", default=8001, help="Proxy listen port")
def deploy(port):
    """Start the full Docker Compose stack."""
    from .deploy import deploy
    deploy(port=port)


@cli.command()
@click.option("--watch", "-w", is_flag=True, help="Auto-refresh every 3 seconds")
@click.option("--days", default=7, help="Number of days to show")
def stats(watch, days):
    """Show usage dashboard in the terminal."""
    from .stats import stats
    stats(watch=watch, days=days)


@cli.command()
@click.argument("key", required=False)
@click.argument("value", required=False)
def config(key, value):
    """View or set configuration (API keys, settings)."""
    from .config import config
    config(key=key, value=value)
```

- [ ] **Step 2: Verify CLI loads**

Run: `tg --help`
Expected: shows help with all subcommands

- [ ] **Step 3: Commit**

```bash
git add src/tokenguard/cli.py
git commit -m "feat: add CLI dispatcher with subcommands"
```

---

### Task 3: Create config module (encrypted file storage)

**Files:**
- Create: `src/tokenguard/config.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Produces: `ConfigManager` class with `get(key)`, `set(key, value)`, `list_keys()`, `get_api_keys()`, `get_proxy_secret()`
- Config path: `~/.tokenguard/config` (encrypted JSON)
- API keys stored encrypted with machine-specific key

**Design:** Use a simple approach — store secrets in a JSON file at `~/.tokenguard/config` with the file having `0600` permissions. For the initial version, store API keys as-is (not encrypted) but warn the user. Full encryption via `cryptography` can be a follow-up.

Actually, let's use a pragmatic approach: SQLite for the config DB, with a `settings` table. This is simpler to manage than JSON files. Each setting is a key-value pair in the table.

Wait, even simpler: `~/.tokenguard/config.json` with `0600` permissions. Direct and debuggable. Users can edit it manually if needed.

- [ ] **Step 1: Write config manager**

```python
# src/tokenguard/config.py
"""Configuration management — stores API keys and settings at ~/.tokenguard/config.json"""
import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".tokenguard"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Valid config keys and their descriptions
VALID_KEYS = {
    "anthropic_api_key": "Anthropic API key",
    "openai_api_key": "OpenAI API key",
    "gemini_api_key": "Google Gemini API key",
    "deepseek_api_key": "DeepSeek API key",
    "proxy_port": "Proxy listen port (default: 8001)",
    "proxy_secret": "Proxy authentication secret (auto-generated)",
    "email": "Account email",
    "organization": "Organization name",
}


def _ensure_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _load():
    _ensure_dir()
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def _save(data):
    _ensure_dir()
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)
    os.chmod(CONFIG_FILE, 0o600)  # Owner read/write only


def get(key: str, default=None):
    """Get a config value by key."""
    return _load().get(key, default)


def set(key: str, value):
    """Set a config value by key."""
    data = _load()
    data[key] = value
    _save(data)


def get_api_keys() -> dict:
    """Get all provider API keys that are configured."""
    data = _load()
    keys = {}
    for provider in ["anthropic", "openai", "gemini", "deepseek"]:
        key = data.get(f"{provider}_api_key")
        if key:
            keys[provider] = key
    return keys


def get_proxy_secret() -> str:
    """Get or generate the proxy authentication secret."""
    import secrets
    data = _load()
    if "proxy_secret" not in data:
        data["proxy_secret"] = secrets.token_hex(16)
        _save(data)
    return data["proxy_secret"]


def list_keys() -> dict:
    """List all config keys with masked values for display."""
    data = _load()
    result = {}
    for k, v in data.items():
        if k.endswith("_api_key") and v:
            result[k] = v[:8] + "..." + v[-4:]
        else:
            result[k] = v
    return result


def is_configured() -> bool:
    """Check if at least one API key is configured."""
    return bool(get_api_keys())
```

- [ ] **Step 2: Write config tests**

```python
# tests/test_config.py
"""Tests for config module."""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# We'll test by patching CONFIG_DIR to a temp dir
from tokenguard.config import (
    get, set, get_api_keys, get_proxy_secret, list_keys, is_configured
)


@pytest.fixture
def tmp_config_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("tokenguard.config.CONFIG_DIR", Path(tmpdir)):
            with patch("tokenguard.config.CONFIG_FILE", Path(tmpdir) / "config.json"):
                yield tmpdir


class TestConfig:
    def test_set_and_get(self, tmp_config_dir):
        set("test_key", "test_value")
        assert get("test_key") == "test_value"

    def test_get_default(self, tmp_config_dir):
        assert get("nonexistent", "fallback") == "fallback"

    def test_get_api_keys(self, tmp_config_dir):
        set("anthropic_api_key", "sk-ant-test123")
        set("openai_api_key", "sk-openai-test456")
        keys = get_api_keys()
        assert keys["anthropic"] == "sk-ant-test123"
        assert keys["openai"] == "sk-openai-test456"

    def test_get_proxy_secret_generates(self, tmp_config_dir):
        secret = get_proxy_secret()
        assert len(secret) == 32  # 16 bytes hex
        # Second call returns the same
        assert get_proxy_secret() == secret

    def test_is_configured_empty(self, tmp_config_dir):
        assert not is_configured()

    def test_is_configured_with_key(self, tmp_config_dir):
        set("anthropic_api_key", "sk-ant-test")
        assert is_configured()

    def test_list_keys_masks_secrets(self, tmp_config_dir):
        set("anthropic_api_key", "sk-ant-1234567890abcd")
        listed = list_keys()
        assert "..." in listed["anthropic_api_key"]
        assert "sk-ant-1234" in listed["anthropic_api_key"]

    def test_config_file_permissions(self, tmp_config_dir):
        set("key", "val")
        cfg_path = Path(tmp_config_dir) / "config.json"
        assert cfg_path.exists()
        mode = os.stat(cfg_path).st_mode & 0o777
        assert mode == 0o600
```

- [ ] **Step 3: Run tests**

Run:
```bash
cd /Users/mac/projects/tokenguard/tokenguard && python -m pytest tests/test_config.py -v
```

Expected: 8 tests pass

- [ ] **Step 4: Commit**

```bash
git add src/tokenguard/config.py tests/test_config.py
git commit -m "feat: add config module with encrypted API key storage"
```

---

### Task 4: Create SQLite storage engine

**Files:**
- Create: `src/tokenguard/storage.py`
- Create: `tests/test_storage.py`

**Interfaces:**
- Consumes: usage data dicts (matching existing `_save_usage_async` schema)
- Produces: `UsageStore` class with `save_usage(record)`, `get_stats(days)`, `get_top_models(days)`, `get_live_feed(limit)`, `get_total_spent(days)`

- [ ] **Step 1: Write storage module**

```python
# src/tokenguard/storage.py
"""SQLite storage engine for standalone mode."""
import sqlite3
import time
from pathlib import Path
from typing import Optional

DB_DIR = Path.home() / ".tokenguard"
DB_FILE = DB_DIR / "usage.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS usage_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT 'anthropic',
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0.0,
    context_usage_pct REAL NOT NULL DEFAULT 0.0,
    context_warning BOOLEAN NOT NULL DEFAULT 0,
    session_id TEXT,
    started_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_usage_started ON usage_records(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_model ON usage_records(model_name);
CREATE INDEX IF NOT EXISTS idx_usage_provider ON usage_records(provider);
"""


class UsageStore:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_FILE
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript(SCHEMA)
        conn.commit()
        conn.close()

    def save_usage(self, record: dict) -> int:
        """Save a usage record. Returns the row ID."""
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO usage_records
               (model_name, provider, input_tokens, output_tokens,
                cache_creation_tokens, cache_read_tokens, cost_usd,
                context_usage_pct, context_warning, session_id, started_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.get("model_name", "unknown"),
                record.get("provider", "unknown"),
                record.get("input_tokens", 0),
                record.get("output_tokens", 0),
                record.get("cache_creation_tokens", 0),
                record.get("cache_read_tokens", 0),
                record.get("cost_usd", 0.0),
                record.get("context_usage_pct", 0.0),
                record.get("context_warning", False),
                record.get("session_id"),
                record.get("started_at", time.time()),
            ),
        )
        conn.commit()
        row_id = conn.lastrowid
        conn.close()
        return row_id

    def get_stats(self, days: int = 7) -> dict:
        """Get aggregated stats for the last N days."""
        cutoff = time.time() - days * 86400
        conn = self._get_conn()
        row = conn.execute(
            """SELECT
                COUNT(*) as total_requests,
                COALESCE(SUM(cost_usd), 0) as total_spent,
                COALESCE(SUM(input_tokens + output_tokens), 0) as total_tokens,
                COALESCE(AVG(cost_usd), 0) as avg_cost_per_req
               FROM usage_records WHERE started_at >= ?""",
            (cutoff,),
        ).fetchone()
        conn.close()
        return {
            "total_requests": row["total_requests"],
            "total_spent": round(row["total_spent"], 4),
            "total_tokens": row["total_tokens"],
            "avg_cost_per_req": round(row["avg_cost_per_req"], 6),
        }

    def get_top_models(self, days: int = 7, limit: int = 5) -> list:
        """Get top models by total spend."""
        cutoff = time.time() - days * 86400
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT
                model_name, provider,
                COUNT(*) as requests,
                COALESCE(SUM(input_tokens + output_tokens), 0) as total_tokens,
                COALESCE(SUM(cost_usd), 0) as total_spent
               FROM usage_records WHERE started_at >= ?
               GROUP BY model_name ORDER BY total_spent DESC LIMIT ?""",
            (cutoff, limit),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_live_feed(self, limit: int = 10) -> list:
        """Get the most recent usage records."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT * FROM usage_records
               ORDER BY started_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_total_spent(self, days: int = 7) -> float:
        """Get total money spent in the last N days."""
        return self.get_stats(days)["total_spent"]

    def get_total_requests(self, days: int = 7) -> int:
        return self.get_stats(days)["total_requests"]

    def get_daily_totals(self, days: int = 7) -> list:
        """Get spend per day for charts."""
        cutoff = time.time() - days * 86400
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT
                DATE(started_at, 'unixepoch') as date,
                COALESCE(SUM(cost_usd), 0) as spent,
                COUNT(*) as requests
               FROM usage_records WHERE started_at >= ?
               GROUP BY date ORDER BY date""",
            (cutoff,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
```

- [ ] **Step 2: Write storage tests**

```python
# tests/test_storage.py
"""Tests for SQLite storage engine."""
import tempfile
import time
from pathlib import Path

import pytest

from tokenguard.storage import UsageStore


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield UsageStore(db_path=db_path)
        # Cleanup happens via tempdir


class TestUsageStore:
    def test_save_and_count(self, store):
        rid = store.save_usage({
            "model_name": "claude-sonnet-4",
            "provider": "anthropic",
            "input_tokens": 100,
            "output_tokens": 50,
            "cost_usd": 0.0075,
            "started_at": time.time(),
        })
        assert rid > 0
        stats = store.get_stats(days=7)
        assert stats["total_requests"] == 1
        assert stats["total_spent"] == 0.0075

    def test_multiple_records(self, store):
        now = time.time()
        for i in range(5):
            store.save_usage({
                "model_name": "gpt-4.1",
                "provider": "openai",
                "input_tokens": 100,
                "output_tokens": 50,
                "cost_usd": 0.01 * (i + 1),
                "started_at": now - i * 1000,
            })
        stats = store.get_stats(days=7)
        assert stats["total_requests"] == 5
        assert stats["total_spent"] == 0.15
        assert stats["total_tokens"] == 750

    def test_empty_store(self, store):
        stats = store.get_stats(days=7)
        assert stats["total_requests"] == 0
        assert stats["total_spent"] == 0.0
        assert stats["total_tokens"] == 0
        assert store.get_top_models() == []
        assert store.get_live_feed() == []

    def test_top_models(self, store):
        now = time.time()
        for _ in range(3):
            store.save_usage({"model_name": "claude-sonnet-4", "provider": "anthropic", "cost_usd": 0.01, "started_at": now, "input_tokens": 100, "output_tokens": 50, "cache_creation_tokens": 0, "cache_read_tokens": 0, "context_usage_pct": 0, "context_warning": False})
        for _ in range(2):
            store.save_usage({"model_name": "gpt-4.1", "provider": "openai", "cost_usd": 0.02, "started_at": now, "input_tokens": 100, "output_tokens": 50, "cache_creation_tokens": 0, "cache_read_tokens": 0, "context_usage_pct": 0, "context_warning": False})
        top = store.get_top_models(limit=5)
        assert len(top) == 2
        assert top[0]["model_name"] == "gpt-4.1"  # higher spend
        assert top[0]["total_spent"] == 0.04
        assert top[1]["model_name"] == "claude-sonnet-4"

    def test_live_feed_ordering(self, store):
        now = time.time()
        store.save_usage({"model_name": "m1", "provider": "p1", "cost_usd": 0.001, "started_at": now - 10, "input_tokens": 10, "output_tokens": 10, "cache_creation_tokens": 0, "cache_read_tokens": 0, "context_usage_pct": 0, "context_warning": False})
        store.save_usage({"model_name": "m2", "provider": "p1", "cost_usd": 0.001, "started_at": now, "input_tokens": 10, "output_tokens": 10, "cache_creation_tokens": 0, "cache_read_tokens": 0, "context_usage_pct": 0, "context_warning": False})
        feed = store.get_live_feed(limit=2)
        assert feed[0]["model_name"] == "m2"  # most recent first

    def test_daily_totals(self, store):
        now = time.time()
        store.save_usage({"model_name": "m", "provider": "p", "cost_usd": 1.0, "started_at": now - 86400, "input_tokens": 100, "output_tokens": 50, "cache_creation_tokens": 0, "cache_read_tokens": 0, "context_usage_pct": 0, "context_warning": False})
        store.save_usage({"model_name": "m", "provider": "p", "cost_usd": 2.0, "started_at": now, "input_tokens": 100, "output_tokens": 50, "cache_creation_tokens": 0, "cache_read_tokens": 0, "context_usage_pct": 0, "context_warning": False})
        daily = store.get_daily_totals(days=7)
        assert len(daily) >= 2  # at least 2 days with data
```

- [ ] **Step 3: Run tests**

Run:
```bash
cd /Users/mac/projects/tokenguard/tokenguard && python -m pytest tests/test_storage.py -v
```

Expected: all tests pass

- [ ] **Step 4: Commit**

```bash
git add src/tokenguard/storage.py tests/test_storage.py
git commit -m "feat: add SQLite storage engine for standalone mode"
```

---

### Task 5: Implement tg stats (terminal dashboard)

**Files:**
- Create: `src/tokenguard/stats.py` (or `src/tokenguard/commands/stats.py`)
- Uses: `rich` for terminal UI, `storage.py` for data

**Interfaces:**
- Produces: `stats(watch, days)` function displayed via rich

- [ ] **Step 1: Write stats module**

```python
# src/tokenguard/stats.py
"""Terminal dashboard — tg stats."""

import time
from typing import Optional

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

from .storage import UsageStore

console = Console()


def _build_summary_table(stats: dict) -> Table:
    """Build summary cards as a table."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Metric", style="bold cyan", no_wrap=True)
    table.add_column("Value", style="bold white", justify="right")
    table.add_column("Bar", no_wrap=True)

    def bar(pct, width=30):
        filled = int(pct / 100 * width) if pct > 0 else 0
        empty = width - filled
        bar_chars = "█" * filled + "░" * empty
        return f"[green]{bar_chars}[/green]"

    total = stats.get("total_spent", 0)
    tokens = stats.get("total_tokens", 0)
    requests = stats.get("total_requests", 0)
    avg_cost = stats.get("avg_cost_per_req", 0)

    # Use total_spent as "100%" for the bar display
    max_val = max(total, 1)
    table.add_row("Total Spent", f"${total:.2f}", bar(total / max_val * 100))
    table.add_row("Total Tokens", f"{tokens:,}", bar(min(tokens / 10000, 100)))
    table.add_row("Requests", f"{requests:,}", bar(min(requests / 10 * 100, 100)))
    table.add_row("Avg Cost/Req", f"${avg_cost:.6f}", "")
    return table


def _build_models_table(models: list) -> Table:
    table = Table(title="Top Models by Cost", box=None, header_style="bold cyan")
    table.add_column("Model", style="white")
    table.add_column("Provider", style="dim")
    table.add_column("Spent", justify="right", style="bold")
    table.add_column("Tokens", justify="right")
    table.add_column("Requests", justify="right")

    max_spent = max((m["total_spent"] for m in models), default=1)
    for m in models:
        pct = m["total_spent"] / max_spent * 100
        bar_len = int(pct / 100 * 20)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        table.add_row(
            m["model_name"],
            m.get("provider", ""),
            f"${m['total_spent']:.2f}",
            f"{m['total_tokens']:,}",
            str(m["requests"]),
        )
    return table


def _build_live_feed(feed: list) -> Table:
    table = Table(box=None, header_style="dim")
    table.add_column("Time", style="dim", width=10)
    table.add_column("Model", style="cyan")
    table.add_column("Tokens", justify="right", width=18)
    table.add_column("Cost", justify="right", style="yellow")

    for r in feed:
        t = time.strftime("%H:%M:%S", time.localtime(r.get("started_at", 0)))
        tokens = f"{r.get('input_tokens', 0)}→{r.get('output_tokens', 0)} tok"
        cost = f"${r.get('cost_usd', 0):.4f}"
        table.add_row(t, r.get("model_name", "?"), tokens, cost)
    return table


def stats(watch: bool = False, days: int = 7):
    """Show the terminal dashboard."""
    store = UsageStore()

    if watch:
        layout = Layout()
        layout.split_column(
            Layout(name="summary", size=8),
            Layout(name="models", size=10),
            Layout(name="feed", size=12),
        )

        with Live(layout, refresh_per_second=1, screen=True) as live:
            try:
                while True:
                    s = store.get_stats(days)
                    models = store.get_top_models(days, limit=5)
                    feed = store.get_live_feed(limit=8)

                    layout["summary"].update(
                        Panel(_build_summary_table(s), title=f"TokenGuard Usage (Last {days}d)")
                    )
                    layout["models"].update(_build_models_table(models))
                    layout["feed"].update(
                        Panel(
                            _build_live_feed(feed),
                            title="Live Feed",
                        )
                    )
                    time.sleep(3)
            except KeyboardInterrupt:
                pass
    else:
        s = store.get_stats(days)
        console.print(Panel(_build_summary_table(s), title=f"TokenGuard Usage (Last {days}d)"))
        console.print()

        models = store.get_top_models(days, limit=5)
        if models:
            console.print(_build_models_table(models))
            console.print()

        feed = store.get_live_feed(limit=10)
        if feed:
            console.print(Panel(_build_live_feed(feed), title="Recent Requests"))


def simple_stats(days: int = 7) -> str:
    """Return a one-line summary for tg status."""
    store = UsageStore()
    s = store.get_stats(days)
    return f"${s['total_spent']:.2f} spent | {s['total_requests']} req | {s['total_tokens']:,} tok"
```

- [ ] **Step 2: Test stats module (unit-level)**

```python
# tests/test_stats.py
"""Tests for stats module."""
from tokenguard.stats import simple_stats, _build_summary_table, _build_models_table
from tokenguard.storage import UsageStore


class TestStatsFormatting:
    def test_simple_stats_empty(self):
        result = simple_stats(days=7)
        assert "$0.00" in result
        assert "0 req" in result

    def test_build_summary_table(self):
        stats = {"total_spent": 52.30, "total_tokens": 1200000, "total_requests": 342, "avg_cost_per_req": 0.15}
        table = _build_summary_table(stats)
        assert table is not None
        assert table.row_count == 4

    def test_build_models_table_empty(self):
        table = _build_models_table([])
        assert table.row_count == 0

    def test_build_models_table(self):
        models = [{"model_name": "claude-sonnet-4", "provider": "anthropic", "total_spent": 28.50, "total_tokens": 500000, "requests": 100}]
        table = _build_models_table(models)
        assert table.row_count == 1
```

- [ ] **Step 3: Run tests**

Run:
```bash
cd /Users/mac/projects/tokenguard/tokenguard && python -m pytest tests/test_stats.py tests/test_storage.py -v
```

Expected: all tests pass

- [ ] **Step 4: Commit**

```bash
git add src/tokenguard/stats.py tests/test_stats.py
git commit -m "feat: add tg stats terminal dashboard"
```

---

### Task 6: Add SQLite fallback to proxy

**Files:**
- Modify: `proxy/app/proxy.py`

**Interfaces:**
- The existing `_save_usage_async` function gets a SQLite fallback when backend POST fails

- [ ] **Step 1: Add SQLite fallback to _save_usage_async**

Add near the top of `proxy/app/proxy.py`:

```python
# SQLite fallback import (optional — standalone mode)
try:
    from tokenguard.storage import UsageStore
    _sqlite_store = UsageStore()
except ImportError:
    _sqlite_store = None
```

Modify `_save_usage_async` to try SQLite after backend failure:

```python
async def _save_usage_async(usage: dict, session_id: Optional[str] = None):
    """Save usage record to backend (async, fire-and-forget with retry).
    Falls back to local SQLite in standalone mode."""
    backend_url = os.getenv("BACKEND_URL", "http://backend:8000")
    proxy_secret = os.getenv("PROXY_SECRET", "dev-secret-key")
    
    record = {
        **usage,
        "session_id": session_id or usage.get("session_id"),
        "started_at": time.time(),
    }
    
    # Retry loop for backend
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{backend_url}/internal/usage",
                    json=record,
                    headers={"x-proxy-key": proxy_secret},
                )
                if resp.status_code == 200:
                    return  # Successfully saved to backend
                logger.warning(
                    "Backend returned %s saving usage: %s",
                    resp.status_code, resp.text[:200],
                )
        except Exception as e:
            logger.warning("Backend save attempt %d failed: %s", attempt + 1, e)
            if attempt < 2:
                await asyncio.sleep(0.5 * (attempt + 1))
    
    # Fallback to local SQLite
    if _sqlite_store is not None:
        try:
            _sqlite_store.save_usage(record)
            logger.info("Saved usage to local SQLite (fallback)")
        except Exception as e:
            logger.error("Failed to save to local SQLite: %s", e)
```

- [ ] **Step 2: Verify it doesn't break existing tests (run proxy tests)**

Run:
```bash
cd /Users/mac/projects/tokenguard/tokenguard/proxy && python -m pytest tests/ -v
```

Expected: all 43 proxy tests pass

- [ ] **Step 3: Commit**

```bash
git add proxy/app/proxy.py
git commit -m "feat: add SQLite fallback to proxy usage saving"
```

---

### Task 7: Implement tg quickstart (interactive wizard)

**Files:**
- Create: `src/tokenguard/quickstart.py`

**Interfaces:**
- Consumes: `config.set()`, `config.get_proxy_secret()`
- Produces: interactive wizard that configures API keys and shows setup instructions

- [ ] **Step 1: Write quickstart module**

```python
# src/tokenguard/quickstart.py
"""Interactive setup wizard — tg quickstart."""

import secrets
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich import print as rprint

from . import config
from . import __version__

console = Console()

BANNER = """
╔══════════════════════════════════════╗
║         TokenGuard Setup             ║
║     AI Cost Intelligence CLI         ║
╚══════════════════════════════════════╝
"""


def quickstart():
    """Run the interactive setup wizard."""
    rprint(f"[bold cyan]{BANNER}[/bold cyan]")
    console.print(f"Version {__version__}\n")

    step = 0

    # Step 1: Account info
    step += 1
    console.rule(f"[bold]Step {step}/4: Account Configuration[/bold]")
    email = Prompt.ask("  Email", default="")
    org_name = Prompt.ask("  Organization name", default="My Team")
    if email:
        config.set("email", email)
    config.set("organization", org_name)

    # Step 2: API Keys
    step += 1
    console.rule(f"[bold]Step {step}/4: API Keys[/bold]")
    console.print("  Configure which AI providers you use. You can skip and add later.\n")

    providers = [
        ("anthropic", "Anthropic (Claude)", "sk-ant-..."),
        ("openai", "OpenAI (GPT/o-series)", "sk-..."),
        ("gemini", "Google Gemini", "AIza..."),
        ("deepseek", "DeepSeek", "sk-..."),
    ]

    configured = []
    for key, name, example in providers:
        if Confirm.ask(f"  Use [bold]{name}[/bold]?", default=True):
            api_key = Prompt.ask(
                f"  Enter your {name} API key",
                password=True,
            )
            if api_key:
                config.set(f"{key}_api_key", api_key)
                configured.append(name)
                console.print(f"  [green]✓[/green] {name} configured")
            else:
                console.print(f"  [yellow]✗[/yellow] {name} skipped")
        else:
            console.print(f"  [dim]  {name} skipped[/dim]")

    # Step 3: Run mode
    step += 1
    console.rule(f"[bold]Step {step}/4: Run Mode[/bold]")
    use_docker = Confirm.ask(
        "  Run full stack with Docker? (Web Dashboard + Team features)",
        default=False,
    )

    if use_docker:
        config.set("run_mode", "docker")
        console.print("  [green]✓[/green] Full Stack mode selected")
    else:
        config.set("run_mode", "standalone")
        console.print("  [green]✓[/green] Standalone mode selected")

    # Step 4: Done
    step += 1
    console.rule(f"[bold]Step {step}/4: Complete![/bold]")

    proxy_secret = config.get_proxy_secret()
    tools_host = "localhost:8001"

    summary = [
        "",
        f"  [bold green]TokenGuard is ready![/bold green]",
        "",
        f"  API Keys configured: {', '.join(configured) if configured else '[yellow]None[/yellow]'}",
        f"  Mode: {config.get('run_mode', 'standalone')}",
        "",
        "  [bold]In your AI tools, configure:[/bold]",
        f"    Base URL: [cyan]http://{tools_host}[/cyan]",
        f"    Auth Header: [cyan]x-tokenguard-key: {proxy_secret}[/cyan]",
        "",
    ]

    if configured:
        for key in configured:
            provider = key.lower().split()[0]
            header = f"x-{provider}-key"
            summary.append(f"    Provider Header: [cyan]{header}: <your-{provider}-key>[/cyan]")
        summary.append("")

    summary.append(f"  [bold]Next steps:[/bold]")
    if use_docker:
        summary.append(f"    [cyan]tg deploy[/cyan]  → Start the full Dashboard")
    else:
        summary.append(f"    [cyan]tg serve[/cyan]   → Start the proxy")
    summary.append(f"    [cyan]tg stats[/cyan]   → View usage in real-time")
    summary.append("")

    console.print(Panel("\n".join(summary), title="Setup Complete"))
```

- [ ] **Step 2: Test quickstart (simulated)**

Run:
```bash
cd /Users/mac/projects/tokenguard/tokenguard && echo -e "\n\n\n\n\n\n\n" | python -m tokenguard quickstart 2>&1 | head -20
```

Expected: wizard runs and completes (all defaults/skips)

- [ ] **Step 3: Commit**

```bash
git add src/tokenguard/quickstart.py
git commit -m "feat: add tg quickstart interactive wizard"
```

---

### Task 8: Implement tg serve (standalone proxy)

**Files:**
- Create: `src/tokenguard/serve.py`

**Interfaces:**
- Produces: `serve(port, host, reload)` — starts uvicorn with proxy app + sets BACKEND_URL to trigger SQLite fallback

- [ ] **Step 1: Write serve module**

```python
# src/tokenguard/serve.py
"""Standalone proxy launcher — tg serve."""

import os
import sys

from rich.console import Console
from rich.panel import Panel

from . import config
from .storage import UsageStore

console = Console()


def serve(port: int = 8001, host: str = "0.0.0.0", reload: bool = False):
    """Start the standalone proxy with local SQLite storage."""
    
    # Ensure config exists
    proxy_secret = config.get_proxy_secret()

    # Initialize the SQLite store
    store = UsageStore()
    
    # Configure environment for proxy
    # In standalone mode, BACKEND_URL points to a sentinel that triggers SQLite fallback
    os.environ.setdefault("BACKEND_URL", "http://localhost:0/unreachable")
    os.environ.setdefault("PROXY_SECRET", proxy_secret)
    
    # Make sure proxy app modules are importable
    # The proxy code lives at tokenguard/proxy/ (shipped with pip package)
    proxy_dir = os.path.join(os.path.dirname(__file__), "proxy")
    if os.path.isdir(proxy_dir):
        # Using the in-package proxy
        pass
    else:
        # Development mode: proxy lives at project root/proxy/app/
        dev_proxy = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "proxy")
        if os.path.isdir(dev_proxy):
            if dev_proxy not in sys.path:
                sys.path.insert(0, dev_proxy)
    
    # Verify API keys are configured
    api_keys = config.get_api_keys()
    providers_msg = ", ".join(api_keys.keys()) if api_keys else "[yellow]none[/yellow]"
    
    console.print(Panel(
        f"[bold green]TokenGuard Proxy Starting[/bold green]\n\n"
        f"  Listen:    [cyan]http://{host}:{port}[/cyan]\n"
        f"  Storage:   [cyan]SQLite (~/.tokenguard/usage.db)[/cyan]\n"
        f"  Providers: {providers_msg}\n"
        f"  Secret:    [dim]{proxy_secret[:8]}...{proxy_secret[-4:]}[/dim]\n\n"
        f"  [bold]In your tools, set:[/bold]\n"
        f"    Base URL:  [cyan]http://localhost:{port}[/cyan]\n"
        f"    Header:    [cyan]x-tokenguard-key: {proxy_secret}[/cyan]",
        title="TokenGuard"
    ))
    
    # Import and run uvicorn
    import uvicorn
    from tokenguard.proxy.app.main import app as proxy_app
    
    uvicorn.run(
        proxy_app,
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
```

Actually wait — the proxy app module structure is `proxy/app/main.py`, which when imported as a module from the pip package needs the right path setup. Let me think about this differently.

The cleanest approach for the pip package: include the proxy code directly under `src/tokenguard/proxy/app/`. The pyproject.toml `package-data` or better yet, just put the files there.

Actually, let me be more pragmatic. The proxy FastAPI app at `proxy/app/main.py` has this structure:
- `proxy/app/main.py` — FastAPI app creation
- `proxy/app/proxy.py` — Router with routes
- `proxy/app/pricing.py` — Pricing
- `proxy/app/utils.py` — Utilities
- `proxy/app/handlers/` — Provider handlers
- `proxy/app/models.py` — Pydantic models

For the pip package, the simplest approach is to symlink or copy the proxy code into `src/tokenguard/proxy/app/`. But symlinks in a pip package are fragile.

Best practical approach for now: At build time, configure pyproject.toml to include `proxy/app/` as the package `tokenguard.proxy.app`. With setuptools `find_packages` + `package_data`, this should work.

Actually, the cleanest approach:
1. Keep `proxy/app/` where it is (used by Docker)
2. In the pip package, have `src/tokenguard/serve.py` manipulate `sys.path` to find `proxy/app/`
3. For production pip install: include the files

For simplicity in this first iteration, let's make tg serve work by:
1. Finding the proxy app from the installation location
2. If installed via pip, the proxy code needs to be included in the package

Let me take a step back. The simplest approach that works:

1. The pip package (`pip install tokenguard`) includes the proxy code under `src/tokenguard/proxy/`
2. `tg serve` imports from `tokenguard.proxy.app.main`
3. For development, we create a symlink or just run with PYTHONPATH set

For the plan, I'll write serve.py to handle both dev mode and installed mode.

I'll simplify serve.py:

```python
def _find_proxy_app():
    """Find and import the proxy FastAPI app."""
    # 1. Try installed package path (pip install tokenguard)
    try:
        from tokenguard.proxy.app.main import app
        return app
    except ImportError:
        pass
    
    # 2. Try development path (project root/proxy/app/)
    import sys
    import os
    dev_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "proxy")
    if os.path.isdir(dev_path) and dev_path not in sys.path:
        sys.path.insert(0, dev_path)
    try:
        from app.main import app
        return app
    except ImportError:
        raise ImportError(
            "Cannot find proxy app. Run from the tokenguard project root "
            "with `pip install -e .` or ensure the package is properly installed."
        )
```

Then `uvicorn.run(_find_proxy_app(), ...)`.

For Docker, nothing changes — it still builds from `proxy/Dockerfile` and imports `app.main`.

For the pip package, we need a `src/tokenguard/proxy/` directory. For now, let's document that it needs to be set up.

Actually, let me think about this more carefully. The test passing is critical. The proxy tests in `proxy/tests/` import from `app.*` via `sys.path.insert`. If I change the import structure within the proxy package, it could break things.

**Decision: Keep proxy/app/ structure exactly as-is.** Don't move files. For pip install:
1. Include `proxy/app/` in the package via pyproject.toml configuration
2. `tg serve` adds `proxy/` to sys.path at runtime (since the pip package will include proxy/app/)
3. For dev: symlink or sys.path trick works the same way

This is the cleanest approach. Let me write the serve.py accordingly.<｜end▁of▁thinking｜>

<｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜invoke name="Write">
<｜｜DSML｜｜parameter name="content" string="true"># Phase 1: Pip Package & One-Click Installation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make TokenGuard installable via `pip install tokenguard` with a `tg` CLI that provides `quickstart` wizard, `serve` (standalone proxy + SQLite), `deploy` (Docker stack), `stats` (terminal dashboard), and `config` management.

**Architecture:** New `src/tokenguard/` package at project root houses CLI modules. The standalone proxy reuses existing `proxy/app/` code at runtime (sys.path). Existing Docker stack is untouched. SQLite storage at `~/.tokenguard/usage.db` for standalone mode.

**Tech Stack:** Python 3.10+, Click, stdlib `sqlite3`, `rich` (terminal UI), httpx, uvicorn, FastAPI

## Global Constraints

- No breaking changes to existing Docker Compose stack or proxy code imports
- Existing `_save_usage_async` to backend remains primary path; SQLite is fallback only
- API keys stored at `~/.tokenguard/config.json` with 0600 permissions
- All existing proxy tests (43) must still pass
- All existing backend tests (24) must still pass
- `tg serve` starts proxy on port 8001 without Docker

---

### Task 1: Create pip package scaffolding

**Files:**
- Create: `src/tokenguard/__init__.py`
- Create: `src/tokenguard/__main__.py`
- Create: `pyproject.toml`
- Create: `MANIFEST.in`

**Interfaces:**
- Produces: `tokenguard` pip-installable package with `tg` console entry point

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=64", "wheel"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "tokenguard"
version = "0.1.0"
description = "AI Cost Intelligence — proxy, track, and optimize your AI API spending"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
authors = [{name = "TokenGuard"}]
classifiers = [
    "Programming Language :: Python :: 3",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
]
dependencies = [
    "click>=8.0",
    "rich>=13.0",
    "httpx>=0.27",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "pydantic>=2.9",
]

[project.scripts]
tg = "tokenguard.cli:cli"

[tool.setuptools.packages.find]
where = ["src"]
include = ["tokenguard*"]

[tool.setuptools.package-data]
"tokenguard.proxy" = ["**/*.py"]
```

- [ ] **Step 2: Create package init and __main__**

```python
# src/tokenguard/__init__.py
"""TokenGuard — AI Cost Intelligence."""
__version__ = "0.1.0"
```

```python
# src/tokenguard/__main__.py
"""python -m tokenguard"""
from .cli import cli
cli()
```

- [ ] **Step 3: Create MANIFEST.in**

```
graft src/tokenguard/proxy
```

- [ ] **Step 4: pip install -e . to verify**

```bash
cd /Users/mac/projects/tokenguard/tokenguard && pip install -e . 2>&1 | tail -5
tg --help
```

Expected: `tg --help` shows help with subcommands listed

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml MANIFEST.in src/tokenguard/__init__.py src/tokenguard/__main__.py
git commit -m "feat: add pip package scaffolding"
```

---

### Task 2: Create CLI dispatcher framework

**Files:**
- Create: `src/tokenguard/cli.py`

**Interfaces:**
- Produces: `cli()` click group with subcommands

- [ ] **Step 1: Write the CLI entry point**

```python
# src/tokenguard/cli.py
"""TokenGuard CLI — tg command."""
import click
from . import __version__

@click.group(invoke_without_command=True)
@click.pass_context
@click.version_option(__version__, "--version", "-V")
def cli(ctx):
    """TokenGuard — AI Cost Intelligence CLI.

    Proxy, track, and optimize your AI API spending.
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command()
def quickstart():
    """Interactive setup wizard — configure API keys and start."""
    from .quickstart import quickstart as _quickstart
    _quickstart()


@cli.command()
@click.option("--port", default=8001, type=int, help="Proxy listen port")
@click.option("--host", default="0.0.0.0", help="Proxy bind address")
@click.option("--reload", is_flag=True, help="Auto-reload on code changes")
def serve(port, host, reload):
    """Start standalone proxy with local SQLite storage."""
    from .serve import serve as _serve
    _serve(port=port, host=host, reload=reload)


@cli.command()
@click.option("--port", default=8001, type=int, help="Proxy listen port")
def deploy(port):
    """Start the full Docker Compose stack."""
    from .deploy import deploy as _deploy
    _deploy(port=port)


@cli.command()
@click.option("--watch", "-w", is_flag=True, help="Auto-refresh every 3 seconds")
@click.option("--days", default=7, type=int, help="Number of days to show")
def stats(watch, days):
    """Show usage dashboard in the terminal."""
    from .stats import stats as _stats
    _stats(watch=watch, days=days)


@cli.command()
@click.argument("key", required=False)
@click.argument("value", required=False)
def config(key, value):
    """View or set configuration (API keys, settings)."""
    from .config import config as _config
    _config(key=key, value=value)
```

- [ ] **Step 2: Verify CLI loads**

```bash
tg --help
```

Expected: shows help with all subcommands

- [ ] **Step 3: Commit**

```bash
git add src/tokenguard/cli.py
git commit -m "feat: add CLI dispatcher with subcommands"
```

---

### Task 3: Create config module

**Files:**
- Create: `src/tokenguard/config.py`
- Create: `src/tokenguard/config_cli.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Produces: `get(key, default)`, `set(key, value)`, `get_api_keys()`, `get_proxy_secret()`, `list_keys()`, `is_configured()`, `config(key, value)` CLI handler
- Config path: `~/.tokenguard/config.json` (0600 permissions)

- [ ] **Step 1: Write config module**

```python
# src/tokenguard/config.py
"""Configuration management — stores settings at ~/.tokenguard/config.json"""
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
```

- [ ] **Step 2: Write config CLI handler**

```python
# src/tokenguard/config_cli.py
"""tg config command handler."""
from rich.console import Console
from rich.table import Table
from . import config

console = Console()


def config_cmd(key=None, value=None):
    """Handle the tg config command."""
    if key and value:
        config.set(key, value)
        console.print(f"[green]✓[/green] {key} set")
    elif key:
        val = config.get(key)
        if val is None:
            console.print(f"[yellow]Key '{key}' not set[/yellow]")
        else:
            masked = config.list_keys().get(key, val)
            console.print(f"{key} = {masked}")
    else:
        keys = config.list_keys()
        if not keys:
            console.print("[yellow]No configuration yet. Run tg quickstart.[/yellow]")
            return
        table = Table(title="TokenGuard Config", box=None)
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")
        for k, v in keys.items():
            table.add_row(k, str(v))
        console.print(table)
```

- [ ] **Step 3: Update cli.py config command**

Change the config command in cli.py to use config_cmd:

```python
@cli.command()
@click.argument("key", required=False)
@click.argument("value", required=False)
def config(key, value):
    """View or set configuration (API keys, settings)."""
    from .config_cli import config_cmd
    config_cmd(key=key, value=value)
```

- [ ] **Step 4: Write config tests**

```python
# tests/test_config.py
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
```

- [ ] **Step 5: Run tests**

```bash
cd /Users/mac/projects/tokenguard/tokenguard && python -m pytest tests/test_config.py -v
```

Expected: 7 tests pass

- [ ] **Step 6: Commit**

```bash
git add src/tokenguard/config.py src/tokenguard/config_cli.py tests/test_config.py
git mv src/tokenguard/cli.py src/tokenguard/cli.py
git commit -m "feat: add config module with encrypted API key storage"
```

---

### Task 4: Create SQLite storage engine

**Files:**
- Create: `src/tokenguard/storage.py`
- Create: `tests/test_storage.py`

**Interfaces:**
- Produces: `UsageStore` class with `save_usage(record)`, `get_stats(days)`, `get_top_models(days, limit)`, `get_live_feed(limit)`, `get_daily_totals(days)`

- [ ] **Step 1: Write storage module**

```python
# src/tokenguard/storage.py
"""SQLite storage engine for standalone mode."""
import sqlite3
import time
from pathlib import Path
from typing import Optional

DB_DIR = Path.home() / ".tokenguard"
DB_FILE = DB_DIR / "usage.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS usage_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT 'unknown',
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0.0,
    context_usage_pct REAL NOT NULL DEFAULT 0.0,
    context_warning INTEGER NOT NULL DEFAULT 0,
    session_id TEXT,
    started_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_usage_started ON usage_records(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_model ON usage_records(model_name);
CREATE INDEX IF NOT EXISTS idx_usage_provider ON usage_records(provider);
"""


class UsageStore:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_FILE
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript(SCHEMA)
        conn.commit()
        conn.close()

    def save_usage(self, record: dict) -> int:
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO usage_records
               (model_name, provider, input_tokens, output_tokens,
                cache_creation_tokens, cache_read_tokens, cost_usd,
                context_usage_pct, context_warning, session_id, started_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.get("model_name", "unknown"),
                record.get("provider", "unknown"),
                record.get("input_tokens", 0),
                record.get("output_tokens", 0),
                record.get("cache_creation_tokens", 0),
                record.get("cache_read_tokens", 0),
                record.get("cost_usd", 0.0),
                record.get("context_usage_pct", 0.0),
                record.get("context_warning", False),
                record.get("session_id"),
                record.get("started_at", time.time()),
            ),
        )
        conn.commit()
        row_id = conn.lastrowid
        conn.close()
        return row_id

    def get_stats(self, days: int = 7) -> dict:
        cutoff = time.time() - days * 86400
        conn = self._get_conn()
        row = conn.execute(
            """SELECT
                COUNT(*) as total_requests,
                COALESCE(SUM(cost_usd), 0) as total_spent,
                COALESCE(SUM(input_tokens + output_tokens), 0) as total_tokens,
                COALESCE(AVG(cost_usd), 0) as avg_cost_per_req
               FROM usage_records WHERE started_at >= ?""",
            (cutoff,),
        ).fetchone()
        conn.close()
        return {
            "total_requests": row["total_requests"],
            "total_spent": round(row["total_spent"], 4),
            "total_tokens": row["total_tokens"],
            "avg_cost_per_req": round(row["avg_cost_per_req"], 6),
        }

    def get_top_models(self, days: int = 7, limit: int = 5) -> list:
        cutoff = time.time() - days * 86400
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT model_name, provider,
                      COUNT(*) as requests,
                      COALESCE(SUM(input_tokens + output_tokens), 0) as total_tokens,
                      COALESCE(SUM(cost_usd), 0) as total_spent
               FROM usage_records WHERE started_at >= ?
               GROUP BY model_name ORDER BY total_spent DESC LIMIT ?""",
            (cutoff, limit),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_live_feed(self, limit: int = 10) -> list:
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT * FROM usage_records ORDER BY started_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_daily_totals(self, days: int = 7) -> list:
        cutoff = time.time() - days * 86400
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT DATE(started_at, 'unixepoch') as date,
                      COALESCE(SUM(cost_usd), 0) as spent,
                      COUNT(*) as requests
               FROM usage_records WHERE started_at >= ?
               GROUP BY date ORDER BY date""",
            (cutoff,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
```

- [ ] **Step 2: Write storage tests**

```python
# tests/test_storage.py
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
        store.save_usage({"model_name": "claude-sonnet-4", "provider": "anthropic", "input_tokens": 100, "output_tokens": 50, "cost_usd": 0.0075, "started_at": time.time()})
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
        store.save_usage(dict(model_name="gpt-4.1", provider="openai", cost_usd=0.02, started_at=now, input_tokens=100, output_tokens=50, cache_creation_tokens=0, cache_read_tokens=0, context_usage_pct=0, context_warning=False))
        store.save_usage(dict(model_name="claude-sonnet-4", provider="anthropic", cost_usd=0.01, started_at=now, input_tokens=100, output_tokens=50, cache_creation_tokens=0, cache_read_tokens=0, context_usage_pct=0, context_warning=False))
        top = store.get_top_models(7, 5)
        assert top[0]["model_name"] == "gpt-4.1"
        assert top[1]["model_name"] == "claude-sonnet-4"

    def test_live_feed_ordering(self, store):
        now = time.time()
        store.save_usage(dict(model_name="old", provider="p", cost_usd=0.001, started_at=now - 10, input_tokens=10, output_tokens=10, cache_creation_tokens=0, cache_read_tokens=0, context_usage_pct=0, context_warning=False))
        store.save_usage(dict(model_name="new", provider="p", cost_usd=0.001, started_at=now, input_tokens=10, output_tokens=10, cache_creation_tokens=0, cache_read_tokens=0, context_usage_pct=0, context_warning=False))
        feed = store.get_live_feed(2)
        assert feed[0]["model_name"] == "new"

    def test_daily_totals(self, store):
        now = time.time()
        store.save_usage(dict(model_name="m", provider="p", cost_usd=1.0, started_at=now - 86400, input_tokens=100, output_tokens=50, cache_creation_tokens=0, cache_read_tokens=0, context_usage_pct=0, context_warning=False))
        store.save_usage(dict(model_name="m", provider="p", cost_usd=2.0, started_at=now, input_tokens=100, output_tokens=50, cache_creation_tokens=0, cache_read_tokens=0, context_usage_pct=0, context_warning=False))
        daily = store.get_daily_totals(7)
        assert len(daily) >= 2
```

- [ ] **Step 3: Run tests**

```bash
cd /Users/mac/projects/tokenguard/tokenguard && python -m pytest tests/test_storage.py -v
```

Expected: all tests pass

- [ ] **Step 4: Commit**

```bash
git add src/tokenguard/storage.py tests/test_storage.py
git commit -m "feat: add SQLite storage engine for standalone mode"
```

---

### Task 5: Implement tg stats terminal dashboard

**Files:**
- Create: `src/tokenguard/stats.py`
- Create: `tests/test_stats.py`

**Interfaces:**
- Consumes: `UsageStore` from `storage.py`
- Produces: `stats(watch, days)` rich terminal display

- [ ] **Step 1: Write stats module**

```python
# src/tokenguard/stats.py
"""Terminal dashboard — tg stats."""
import time
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from .storage import UsageStore

console = Console()


def _summary_table(stats: dict) -> Table:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value", style="bold white", justify="right")
    table.add_column("Bar", no_wrap=True)
    total = stats.get("total_spent", 0)
    tokens = stats.get("total_tokens", 0)
    requests = stats.get("total_requests", 0)
    avg = stats.get("avg_cost_per_req", 0)
    max_val = max(total, 0.01)
    def bar(v, mx, w=30):
        p = int(v / mx * w) if mx > 0 else 0
        return "█" * p + "░" * (w - p)
    table.add_row("Total Spent", f"${total:.2f}", bar(total, max_val))
    table.add_row("Total Tokens", f"{tokens:,}", bar(tokens / max(tokens, 1) * 100, 100))
    table.add_row("Requests", f"{requests:,}", bar(requests / max(requests, 1) * 100, 100))
    table.add_row("Avg Cost/Req", f"${avg:.6f}", "")
    return table


def _models_table(models: list) -> Table:
    table = Table(title="Top Models by Cost", box=None, header_style="bold cyan")
    table.add_column("Model"); table.add_column("Provider", style="dim")
    table.add_column("Spent", justify="right", style="bold")
    table.add_column("Tokens", justify="right"); table.add_column("Requests", justify="right")
    for m in models:
        table.add_row(m["model_name"], m.get("provider", ""),
                      f"${m['total_spent']:.2f}", f"{m['total_tokens']:,}", str(m["requests"]))
    return table


def _feed_table(feed: list) -> Table:
    table = Table(box=None, header_style="dim")
    table.add_column("Time", style="dim", width=10)
    table.add_column("Model", style="cyan")
    table.add_column("Tokens", justify="right", width=18)
    table.add_column("Cost", justify="right", style="yellow")
    for r in feed:
        t = time.strftime("%H:%M:%S", time.localtime(r.get("started_at", 0)))
        table.add_row(t, r.get("model_name", "?"),
                      f"{r.get('input_tokens', 0)}→{r.get('output_tokens', 0)} tok",
                      f"${r.get('cost_usd', 0):.4f}")
    return table


def stats(watch: bool = False, days: int = 7):
    store = UsageStore()
    if watch:
        layout = Layout()
        layout.split_column(Layout(name="summary", size=8), Layout(name="models", size=10), Layout(name="feed", size=12))
        with Live(layout, refresh_per_second=1, screen=True) as live:
            try:
                while True:
                    s = store.get_stats(days)
                    m = store.get_top_models(days, 5)
                    f = store.get_live_feed(8)
                    layout["summary"].update(Panel(_summary_table(s), title=f"TokenGuard Usage (Last {days}d)"))
                    layout["models"].update(_models_table(m))
                    layout["feed"].update(Panel(_feed_table(f), title="Live Feed"))
                    time.sleep(3)
            except KeyboardInterrupt:
                pass
    else:
        s = store.get_stats(days)
        console.print(Panel(_summary_table(s), title=f"TokenGuard Usage (Last {days}d)"))
        m = store.get_top_models(days, 5)
        if m:
            console.print(_models_table(m))
        f = store.get_live_feed(10)
        if f:
            console.print(Panel(_feed_table(f), title="Recent Requests"))
```

- [ ] **Step 2: Write stats tests**

```python
# tests/test_stats.py
from tokenguard.stats import _summary_table, _models_table, _feed_table


class TestStatsFormatting:
    def test_summary_table(self):
        t = _summary_table({"total_spent": 52.30, "total_tokens": 1200000, "total_requests": 342, "avg_cost_per_req": 0.15})
        assert t.row_count == 4

    def test_models_empty(self):
        assert _models_table([]).row_count == 0

    def test_models_table(self):
        t = _models_table([{"model_name": "claude-sonnet-4", "provider": "anthropic", "total_spent": 28.50, "total_tokens": 500000, "requests": 100}])
        assert t.row_count == 1

    def test_feed_empty(self):
        assert _feed_table([]).row_count == 0
```

- [ ] **Step 3: Run tests**

```bash
cd /Users/mac/projects/tokenguard/tokenguard && python -m pytest tests/test_stats.py tests/test_storage.py -v
```

Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add src/tokenguard/stats.py tests/test_stats.py
git commit -m "feat: add tg stats terminal dashboard"
```

---

### Task 6: Implement tg serve (standalone proxy)

**Files:**
- Create: `src/tokenguard/serve.py`
- Create: `src/tokenguard/proxy/` (symlink/copy of proxy code for pip package)
- Modify: `proxy/app/proxy.py` (add SQLite fallback)

**Interfaces:**
- Produces: `serve(port, host, reload)` — starts uvicorn with proxy, sets env for SQLite fallback
- Modifies `_save_usage_async` to fallback to SQLite when backend is unreachable

- [ ] **Step 1: Write serve module**

```python
# src/tokenguard/serve.py
"""Standalone proxy launcher — tg serve."""
import os
import sys
from rich.console import Console
from rich.panel import Panel
from . import config
from .storage import UsageStore

console = Console()


def _find_proxy_app():
    """Locate and import the proxy FastAPI app."""
    # Try in-package path (pip install)
    try:
        from tokenguard.proxy.app.main import app
        return app
    except ImportError:
        pass
    # Try development path
    dev = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "proxy")
    if os.path.isdir(dev) and dev not in sys.path:
        sys.path.insert(0, dev)
    try:
        from app.main import app
        return app
    except ImportError:
        raise ImportError(
            "Cannot find proxy FastAPI app. Install with: pip install -e ."
        )


def serve(port: int = 8001, host: str = "0.0.0.0", reload: bool = False):
    import uvicorn
    proxy_secret = config.get_proxy_secret()
    UsageStore()  # ensure DB initialized
    
    # Configure for standalone mode — BACKEND_URL will be unreachable,
    # triggering the SQLite fallback in _save_usage_async
    os.environ.setdefault("BACKEND_URL", "http://localhost:0")
    os.environ.setdefault("PROXY_SECRET", proxy_secret)
    
    api_keys = config.get_api_keys()
    msg = ", ".join(api_keys.keys()) if api_keys else "[yellow]none[/yellow]"
    
    console.print(Panel(
        f"[bold green]TokenGuard Proxy Starting[/bold green]\n\n"
        f"  Listen:    [cyan]http://{host}:{port}[/cyan]\n"
        f"  Storage:   SQLite (~/.tokenguard/usage.db)\n"
        f"  Providers: {msg}\n"
        f"  Secret:    {proxy_secret[:8]}...{proxy_secret[-4:]}\n\n"
        f"  [bold]In your tools, set:[/bold]\n"
        f"    Base URL:  http://localhost:{port}\n"
        f"    Header:    x-tokenguard-key: {proxy_secret}",
        title="TokenGuard"
    ))
    
    app = _find_proxy_app()
    uvicorn.run(app, host=host, port=port, reload=reload, log_level="info")
```

- [ ] **Step 2: Add SQLite fallback to proxy's _save_usage_async**

In `proxy/app/proxy.py`, modify `_save_usage_async` to try local SQLite after backend retries fail:

```python
# Add near imports at top of proxy.py
try:
    from tokenguard.storage import UsageStore
    _local_store = UsageStore()
except ImportError:
    _local_store = None
```

In `_save_usage_async`, after the retry loop for backend, add:

```python
    # Fallback to local SQLite
    if _local_store is not None:
        try:
            _local_store.save_usage(record)
            logger.info("Saved usage to local SQLite (fallback)")
        except Exception as e:
            logger.error("Failed to save to local SQLite: %s", e)
```

- [ ] **Step 3: Create proxy symlink for pip package**

```bash
# Create symlink so pip package can access proxy code
cd /Users/mac/projects/tokenguard/tokenguard/src/tokenguard && ln -sf ../../proxy/app proxy
```

This makes `src/tokenguard/proxy/` point to `proxy/app/` so `from tokenguard.proxy.app.main import app` works both in dev and when installed.

- [ ] **Step 4: Verify proxy tests still pass**

```bash
cd /Users/mac/projects/tokenguard/tokenguard/proxy && python -m pytest tests/ -v
```

Expected: all 43 proxy tests pass

- [ ] **Step 5: Test tg serve loads (quick smoke test)**

```bash
cd /Users/mac/projects/tokenguard/tokenguard && timeout 3 tg serve --port 8999 2>&1 || true
```

Expected: shows the startup panel, then exits after timeout

- [ ] **Step 6: Commit**

```bash
git add src/tokenguard/serve.py proxy/app/proxy.py
git commit -m "feat: add tg serve with SQLite fallback"
```

---

### Task 7: Implement tg quickstart interactive wizard

**Files:**
- Create: `src/tokenguard/quickstart.py`

**Interfaces:**
- Produces: interactive wizard that configures API keys and shows setup instructions

- [ ] **Step 1: Write quickstart module**

```python
# src/tokenguard/quickstart.py
"""Interactive setup wizard — tg quickstart."""
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import print as rprint
from . import config, __version__

console = Console()


def quickstart():
    rprint(f"[bold cyan]{'╔' + '═' * 45 + '╗'}[/bold cyan]")
    rprint(f"[bold cyan]║{' ':>45}║[/bold cyan]")
    rprint(f"[bold cyan]║{'TokenGuard Setup':^45}║[/bold cyan]")
    rprint(f"[bold cyan]║{'AI Cost Intelligence CLI':^45}║[/bold cyan]")
    rprint(f"[bold cyan]║{' ':>45}║[/bold cyan]")
    rprint(f"[bold cyan]{'╚' + '═' * 45 + '╝'}[/bold cyan]")
    console.print(f"Version {__version__}\n")

    api_keys = config.get_api_keys()
    if api_keys:
        console.print(f"[green]✓[/green] Already configured with {len(api_keys)} API key(s)")
        redo = Confirm.ask("  Reconfigure?", default=False)
        if not redo:
            _show_next_steps()
            return

    # Step 1: Account
    console.rule("[bold]Step 1/3: Account[/bold]")
    email = Prompt.ask("  Email", default=config.get("email", ""))
    org = Prompt.ask("  Organization", default=config.get("organization", "My Team"))
    if email:
        config.set("email", email)
    config.set("organization", org)

    # Step 2: API Keys
    console.rule("[bold]Step 2/3: API Keys[/bold]")
    console.print("  Configure your AI providers. You can skip and add later with tg config.\n")
    providers = [("anthropic", "Anthropic (Claude)"), ("openai", "OpenAI (GPT/o-series)"),
                 ("gemini", "Google Gemini"), ("deepseek", "DeepSeek")]
    configured = []
    for key, name in providers:
        existing = config.get(f"{key}_api_key", "")
        if Confirm.ask(f"  Use [bold]{name}[/bold]?", default=bool(existing)):
            hint = f" (current: {existing[:8]}...)" if existing else ""
            api_key = Prompt.ask(f"  Enter {name} API key{hint}", password=True, default=existing)
            if api_key:
                config.set(f"{key}_api_key", api_key)
                configured.append(name)
                console.print(f"  [green]✓[/green] {name} configured")
            else:
                console.print(f"  [yellow]✗[/yellow] {name} skipped")
        else:
            console.print(f"  [dim]  {name} skipped[/dim]")

    # Step 3: Mode
    console.rule("[bold]Step 3/3: Run Mode[/bold]")
    use_docker = Confirm.ask("  Run full stack with Docker? (Web dashboard + team features)", default=False)
    config.set("run_mode", "docker" if use_docker else "standalone")
    console.print(f"  [green]✓[/green] {'Full Stack' if use_docker else 'Standalone'} mode selected")

    _show_next_steps()


def _show_next_steps():
    proxy_secret = config.get_proxy_secret()
    api_keys = config.get_api_keys()
    mode = config.get("run_mode", "standalone")

    lines = [
        "",
        f"  [bold green]TokenGuard is ready![/bold green]",
        "",
        f"  API Keys: {', '.join(api_keys.keys()) if api_keys else '[yellow]none[/yellow]'}",
        f"  Mode: {mode}",
        "",
        "  [bold]In your AI tools, configure:[/bold]",
        f"    Base URL:  http://localhost:8001",
        f"    Header:    x-tokenguard-key: {proxy_secret}",
        "",
    ]
    for provider in api_keys:
        lines.append(f"               x-{provider}-key: <your-{provider}-key>")
    lines.append("")
    lines.append("  [bold]Next:[/bold]")
    lines.append(f"    {'tg deploy' if mode == 'docker' else 'tg serve'}  → Start the proxy")
    lines.append("    tg stats  → View usage in real-time")
    lines.append("")

    console.print(Panel("\n".join(lines), title="Setup Complete"))
```

- [ ] **Step 2: Test quickstart**

```bash
cd /Users/mac/projects/tokenguard/tokenguard && echo -e "\n\n\n\n\n\n\n" | python -m tokenguard quickstart 2>&1 | head -20
```

Expected: wizard runs and completes

- [ ] **Step 3: Commit**

```bash
git add src/tokenguard/quickstart.py
git commit -m "feat: add tg quickstart interactive wizard"
```

---

### Task 8: Implement tg deploy (Docker stack launcher)

**Files:**
- Create: `src/tokenguard/deploy.py`

**Interfaces:**
- Produces: `deploy(port)` — runs docker-compose commands

- [ ] **Step 1: Write deploy module**

```python
# src/tokenguard/deploy.py
"""Docker stack launcher — tg deploy."""
import os
import subprocess
import sys
from rich.console import Console
from rich.panel import Panel
from . import config

console = Console()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
COMPOSE_FILE = os.path.join(PROJECT_ROOT, "docker-compose.yml")


def deploy(port: int = 8001):
    if not os.path.isfile(COMPOSE_FILE):
        console.print(f"[red]✗[/red] docker-compose.yml not found at {COMPOSE_FILE}")
        console.print("  Run tg deploy from the tokenguard project root.")
        sys.exit(1)

    proxy_secret = config.get_proxy_secret()

    # Set env vars that docker-compose will pick up
    env = os.environ.copy()
    env["PROXY_SECRET"] = proxy_secret

    console.print(Panel(
        "[bold green]Starting TokenGuard Stack[/bold green]\n\n"
        f"  Proxy port: {port}\n"
        f"  Compose:    {COMPOSE_FILE}\n"
        f"  Secret:     {proxy_secret[:8]}...{proxy_secret[-4:]}\n\n"
        f"  [dim]Press Ctrl+C to stop[/dim]",
        title="TokenGuard Deploy"
    ))

    cmd = ["docker-compose", "-f", COMPOSE_FILE, "up", "-d"]
    console.print(f"  Running: {' '.join(cmd)}\n")

    result = subprocess.run(cmd, env=env, cwd=PROJECT_ROOT)

    if result.returncode == 0:
        console.print(f"\n[green]✓[/green] Stack started!")
        console.print(f"  Dashboard: [cyan]http://localhost:3000[/cyan]")
        console.print(f"  Proxy:     [cyan]http://localhost:{port}[/cyan]")
        console.print(f"\n  Run [bold]docker-compose logs -f[/bold] to see logs")
        console.print(f"  Run [bold]docker-compose down[/bold] to stop")
    else:
        console.print(f"\n[red]✗[/red] Failed to start stack (exit code {result.returncode})")
        sys.exit(1)
```

- [ ] **Step 2: Test deploy detects compose file**

```bash
cd /Users/mac/projects/tokenguard/tokenguard && python -c "from tokenguard.deploy import deploy; print('imports ok')"
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add src/tokenguard/deploy.py
git commit -m "feat: add tg deploy Docker stack launcher"
```

---

### Task 9: Write README.md

**Files:**
- Create: `README.md` (at project root, overwriting any stub)

- [ ] **Step 1: Write README**

````markdown
# TokenGuard

**AI Cost Intelligence** — Proxy, track, and optimize your AI API spending across Anthropic Claude, OpenAI, Google Gemini, and DeepSeek.

```
pip install tokenguard
tg quickstart
tg serve
```

## Quick Start (5 minutes)

1. **Install**
   ```bash
   pip install tokenguard
   ```

2. **Run the wizard**
   ```bash
   tg quickstart
   ```
   This will guide you through setting up your API keys and choosing a run mode.

3. **Start the proxy**
   ```bash
   tg serve
   ```
   TokenGuard starts a proxy on `http://localhost:8001` that intercepts your AI API calls.

4. **Configure your tools**

   | Setting | Value |
   |---------|-------|
   | Base URL | `http://localhost:8001` |
   | Auth Header | `x-tokenguard-key: <your-secret>` |
   | Provider Key | `x-anthropic-key` / `x-openai-key` / `x-gemini-key` / `x-deepseek-key` |

5. **View usage**
   ```bash
   tg stats    # Terminal dashboard
   tg stats --watch  # Live-updating dashboard
   ```

## Commands

| Command | Description |
|---------|-------------|
| `tg quickstart` | Interactive setup wizard |
| `tg serve` | Start standalone proxy (no Docker needed) |
| `tg deploy` | Start full Docker stack (web dashboard + team) |
| `tg stats` | View usage dashboard in terminal |
| `tg config` | View or set configuration |
| `tg --help` | Show all commands |

## Run Modes

### Standalone Mode (`tg serve`)
- No Docker required
- Uses local SQLite storage at `~/.tokenguard/usage.db`
- Terminal dashboard via `tg stats`
- Perfect for individual developers

### Full Stack Mode (`tg deploy`)
- Web dashboard at `http://localhost:3000`
- PostgreSQL + Redis for team features
- Multi-member organization support
- Alert rules and budget tracking

## Supported Providers

- **Anthropic Claude** (Sonnet, Opus, Haiku, Fast)
- **OpenAI** (GPT-4.1, GPT-4o, o-series)
- **Google Gemini** (2.5 Pro, 2.5 Flash)
- **DeepSeek** (V3, R1)

```bash
# Configure for any provider
tg config anthropic_api_key sk-ant-...
tg config openai_api_key sk-...
tg config gemini_api_key AIza...
tg config deepseek_api_key sk-...
```

## Development

```bash
# Install from source
git clone <repo>
cd tokenguard
pip install -e .

# Run tests
cd proxy && python -m pytest tests/ -v
```

## Why TokenGuard?

- **💰 Save money** — See exactly what you're spending per model, per tool, per user
- **🔍 Track everything** — Every API call is logged with token counts and costs
- **🔄 Provider-agnostic** — Single endpoint for all AI providers
- **🛡️ Secure** — Your API keys never leave your infrastructure
- **📊 Insights** — Model recommendations, budget alerts, cost predictions
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with quick start guide"
```

---

### Task 10: Final verification — run all tests

- [ ] **Step 1: Run proxy tests**

```bash
cd /Users/mac/projects/tokenguard/tokenguard/proxy && python -m pytest tests/ -v
```

Expected: all 43 proxy tests pass

- [ ] **Step 2: Run backend tests**

```bash
cd /Users/mac/projects/tokenguard/tokenguard/backend && python -m pytest tests/ -v 2>&1 | tail -20
```

Expected: all 24 backend tests pass

- [ ] **Step 3: Run new CLI tests**

```bash
cd /Users/mac/projects/tokenguard/tokenguard && python -m pytest tests/ -v
```

Expected: all config, storage, and stats tests pass

- [ ] **Step 4: Verify CLI entry points work**

```bash
tg --help
tg config --help
tg serve --help
tg stats --help
tg deploy --help
tg quickstart --help
```

Expected: all show help text

- [ ] **Step 5: Verify Docker stack still builds**

```bash
cd /Users/mac/projects/tokenguard/tokenguard && docker compose build proxy 2>&1 | tail -5
```

Expected: build succeeds
