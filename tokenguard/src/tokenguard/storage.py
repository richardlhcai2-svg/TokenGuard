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
        cursor = conn.cursor()
        cursor.execute(
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
        row_id = cursor.lastrowid
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
