"""SQLite storage engine for standalone mode with Project-Level Attribution."""
import sqlite3
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

DB_DIR = Path.home() / ".tokenguard"
DB_FILE = DB_DIR / "usage.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS usage_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT 'unknown',
    project_name TEXT NOT NULL DEFAULT 'General',
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
CREATE INDEX IF NOT EXISTS idx_usage_project ON usage_records(project_name, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_session ON usage_records(session_id);
"""


class UsageStore:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_FILE
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript(SCHEMA)
            # Handle migration for existing databases without project_name
            columns = [row[1] for row in conn.execute("PRAGMA table_info(usage_records)").fetchall()]
            if "project_name" not in columns:
                conn.execute("ALTER TABLE usage_records ADD COLUMN project_name TEXT NOT NULL DEFAULT 'General'")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_project ON usage_records(project_name, started_at DESC)")
            conn.commit()

    def save_usage(self, record: dict) -> int:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO usage_records
                   (model_name, provider, project_name, input_tokens, output_tokens,
                    cache_creation_tokens, cache_read_tokens, cost_usd,
                    context_usage_pct, context_warning, session_id, started_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.get("model_name", "unknown"),
                    record.get("provider", "unknown"),
                    record.get("project_name", "General"),
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
            return cursor.lastrowid

    def get_stats(self, days: int = 7, project: Optional[str] = None) -> dict:
        cutoff = time.time() - days * 86400
        with self._get_conn() as conn:
            query = """SELECT
                    COUNT(*) as total_requests,
                    COALESCE(SUM(cost_usd), 0) as total_spent,
                    COALESCE(SUM(input_tokens + output_tokens), 0) as total_tokens,
                    COALESCE(AVG(cost_usd), 0) as avg_cost_per_req
                   FROM usage_records WHERE started_at >= ?"""
            params = [cutoff]
            if project and project != "all":
                query += " AND project_name = ?"
                params.append(project)

            row = conn.execute(query, tuple(params)).fetchone()
            return {
                "total_requests": row["total_requests"],
                "total_spent": round(row["total_spent"], 4),
                "total_tokens": row["total_tokens"],
                "avg_cost_per_req": round(row["avg_cost_per_req"], 6),
            }

    def get_project_stats(self, days: Optional[int] = None) -> list:
        """Get project-level cost and token attribution. If days is None, returns all-time attribution from project inception."""
        with self._get_conn() as conn:
            query = """SELECT
                    project_name,
                    COUNT(*) as requests,
                    COALESCE(SUM(cost_usd), 0) as spent,
                    COALESCE(SUM(input_tokens), 0) as input_tokens,
                    COALESCE(SUM(output_tokens), 0) as output_tokens,
                    COALESCE(SUM(input_tokens + output_tokens), 0) as tokens,
                    MIN(started_at) as created_at,
                    MAX(started_at) as last_active
                   FROM usage_records"""
            params = []
            if days is not None:
                cutoff = time.time() - days * 86400
                query += " WHERE started_at >= ?"
                params.append(cutoff)
            query += """ GROUP BY project_name
                   ORDER BY spent DESC"""
            rows = conn.execute(query, tuple(params)).fetchall()
            total_spent = sum(r["spent"] for r in rows) or 0.0001
            return [
                {
                    "project_name": r["project_name"],
                    "requests": r["requests"],
                    "spent": round(r["spent"], 4),
                    "input_tokens": r["input_tokens"],
                    "output_tokens": r["output_tokens"],
                    "tokens": r["tokens"],
                    "cost_pct": round((r["spent"] / total_spent) * 100, 1),
                    "created_at": r["created_at"],
                    "last_active": r["last_active"],
                }
                for r in rows
            ]

    def get_top_models(self, days: int = 7, limit: int = 5, project: Optional[str] = None) -> list:
        cutoff = time.time() - days * 86400
        with self._get_conn() as conn:
            query = """SELECT model_name, provider,
                          COUNT(*) as requests,
                          COALESCE(SUM(cost_usd), 0) as total_spent,
                          COALESCE(SUM(input_tokens + output_tokens), 0) as total_tokens
                   FROM usage_records
                   WHERE started_at >= ?"""
            params = [cutoff]
            if project and project != "all":
                query += " AND project_name = ?"
                params.append(project)
            query += """ GROUP BY model_name, provider
                   ORDER BY total_spent DESC
                   LIMIT ?"""
            params.append(limit)

            rows = conn.execute(query, tuple(params)).fetchall()
            return [
                {
                    "model_name": r["model_name"],
                    "provider": r["provider"],
                    "requests": r["requests"],
                    "total_spent": round(r["total_spent"], 4),
                    "total_tokens": r["total_tokens"],
                }
                for r in rows
            ]

    def get_live_feed(self, limit: int = 20, project: Optional[str] = None) -> list:
        with self._get_conn() as conn:
            query = """SELECT id, model_name, provider, project_name, input_tokens, output_tokens,
                          cost_usd, context_usage_pct, context_warning, session_id, started_at
                   FROM usage_records"""
            params = []
            if project and project != "all":
                query += " WHERE project_name = ?"
                params.append(project)
            query += " ORDER BY started_at DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, tuple(params)).fetchall()
            return [dict(r) for r in rows]

    def get_daily_totals(self, days: int = 7, project: Optional[str] = None) -> list:
        cutoff = time.time() - days * 86400
        with self._get_conn() as conn:
            query = """SELECT
                    DATE(started_at, 'unixepoch', 'localtime') as day,
                    COUNT(*) as requests,
                    COALESCE(SUM(cost_usd), 0) as total_spent,
                    COALESCE(SUM(input_tokens + output_tokens), 0) as total_tokens
                   FROM usage_records
                   WHERE started_at >= ?"""
            params = [cutoff]
            if project and project != "all":
                query += " AND project_name = ?"
                params.append(project)
            query += " GROUP BY day ORDER BY day ASC"

            rows = conn.execute(query, tuple(params)).fetchall()
            return [
                {
                    "day": r["day"],
                    "requests": r["requests"],
                    "total_spent": round(r["total_spent"], 4),
                    "total_tokens": r["total_tokens"],
                }
                for r in rows
            ]
