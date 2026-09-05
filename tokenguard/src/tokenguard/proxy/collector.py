import asyncio
import glob
import json
import logging
import os
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Tuple, Set

from .pricing import get_model_cost, get_context_window

logger = logging.getLogger("tokenguard.collector")

KNOWN_PROJECTS = [
    "my-web-app", "data-pipeline", "ai-agent", "frontend-dashboard",
    "workspace-core", "tokenguard", "demo-project", "api-backend"
]

# File modification cache to avoid redundant disk I/O on unmodified sessions
# Format: filepath -> (mtime, file_size)
_FILE_MOD_CACHE: Dict[str, Tuple[float, int]] = {}


def _parse_timestamp(val) -> float:
    """Parse integer, float, ISO-8601 string, or epoch timestamp into UTC epoch float."""
    if val is None:
        return time.time()
    if isinstance(val, (int, float)):
        if val > 1e11:  # milliseconds
            return float(val) / 1000.0
        return float(val)
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return time.time()
        try:
            num = float(val)
            if num > 1e11:
                return num / 1000.0
            return num
        except ValueError:
            pass

        # Try parsing ISO formats
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                dt = datetime.strptime(val, fmt)
                return dt.timestamp()
            except ValueError:
                pass
        try:
            from dateutil import parser
            return parser.parse(val).timestamp()
        except Exception:
            return time.time()
    return time.time()


def _resolve_project_from_text(text: str, default: str = "General") -> str:
    """Extract known repository/project names from text snippets or prompt paths."""
    if not text:
        return default
    for p in KNOWN_PROJECTS:
        if re.search(r'\b' + re.escape(p) + r'\b', text, re.IGNORECASE):
            return p
        if f"/{p}/" in text or f"/{p}\"" in text or f"/{p}'" in text:
            return p
    return default


def collect_local_coding_tools_activity(db_path: Optional[str] = None) -> int:
    """
    Sync usage and context from local AI developer tools:
    1. Claude Code CLI (~/.claude/projects/*/*.jsonl)
    2. Antigravity IDE (~/.gemini/antigravity-ide/brain/*)
    3. ChatGPT / OpenAI Codex (~/Library/Application Support/OpenAI/Codex/sqlite.db or ~/.config/openai/codex.db)
    
    Optimized with file mtime/size caching for minimal CPU and zero redundant disk I/O.
    Returns total count of newly inserted records.
    """
    if not db_path:
        db_path = os.path.expanduser("~/.tokenguard/usage.db")
    
    if not os.path.exists(db_path):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    new_synced_count = 0
    with sqlite3.connect(db_path, timeout=10.0) as conn:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        cur = conn.cursor()

        # Ensure schema table exists
        cur.execute(
            """CREATE TABLE IF NOT EXISTS usage_records (
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
            );"""
        )

        # Ensure project_name column exists
        columns = [row[1] for row in cur.execute("PRAGMA table_info(usage_records)").fetchall()]
        if "project_name" not in columns:
            cur.execute("ALTER TABLE usage_records ADD COLUMN project_name TEXT NOT NULL DEFAULT 'General'")
            conn.commit()

        cur.execute("SELECT session_id FROM usage_records WHERE session_id IS NOT NULL")
        synced: Set[str] = {row[0] for row in cur.fetchall()}

        # ----------------------------------------------------
        # 1. Claude Code Session Sync (~/.claude/projects/*/*.jsonl)
        # ----------------------------------------------------
        try:
            claude_files = glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl"))
            for f in claude_files:
                try:
                    st = os.stat(f)
                    mtime, size = st.st_mtime, st.st_size
                except OSError:
                    continue

                # Skip un-modified files if already seen
                cached = _FILE_MOD_CACHE.get(f)
                if cached == (mtime, size):
                    continue

                dir_name = os.path.basename(os.path.dirname(f))
                file_base = os.path.basename(f).replace(".jsonl", "")
                
                session_text = ""
                seen_uuids = set()
                records = []
                
                with open(f, "r", encoding="utf-8", errors="ignore") as fp:
                    for line in fp:
                        if not line.strip():
                            continue
                        try:
                            d = json.loads(line)
                        except Exception:
                            continue

                        if len(session_text) < 300000:
                            session_text += json.dumps(d)

                        uuid = d.get("uuid")
                        msg = d.get("message") or {}
                        usage = msg.get("usage")
                        model = msg.get("model", "agnes-2.5-flash")

                        if uuid and usage and uuid not in seen_uuids:
                            seen_uuids.add(uuid)
                            in_tok = usage.get("input_tokens", 0)
                            out_tok = usage.get("output_tokens", 0)
                            cr_tok = usage.get("cache_read_input_tokens", 0)
                            cc_tok = usage.get("cache_creation_input_tokens", 0)
                            
                            ts = d.get("timestamp") or msg.get("timestamp")
                            started_at = _parse_timestamp(ts)
                            records.append((uuid, model, in_tok, out_tok, cr_tok, cc_tok, started_at))

                project_name = "General"
                if "tokenguard" in dir_name.lower():
                    project_name = "tokenguard"
                else:
                    project_name = _resolve_project_from_text(session_text, default="General")

                for uuid, model, in_tok, out_tok, cr_tok, cc_tok, started_at in records:
                    step_id = f"claude_cli_{file_base}_{uuid}"
                    if step_id in synced:
                        continue

                    rate = get_model_cost(model, "anthropic")
                    in_rate = rate.get("input_per_k", 0.0030)
                    out_rate = rate.get("output_per_k", 0.0150)
                    read_rate = rate.get("cache_read_per_k", in_rate * 0.1)
                    write_rate = in_rate * 1.25

                    cost = (in_tok / 1000) * in_rate + (cr_tok / 1000) * read_rate + (cc_tok / 1000) * write_rate + (out_tok / 1000) * out_rate
                    ctx_window = get_context_window(model)
                    ctx_pct = min(1.0, round((in_tok + cr_tok + cc_tok + out_tok) / ctx_window, 4))

                    cur.execute(
                        """
                        INSERT INTO usage_records (
                            provider, model_name, project_name, input_tokens, output_tokens,
                            cache_creation_tokens, cache_read_tokens, cost_usd,
                            context_usage_pct, context_warning, session_id, started_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                        """,
                        (
                            "anthropic",
                            model,
                            project_name,
                            in_tok,
                            out_tok,
                            cc_tok,
                            cr_tok,
                            round(cost, 6),
                            ctx_pct,
                            step_id,
                            started_at,
                        ),
                    )
                    synced.add(step_id)
                    new_synced_count += 1

                _FILE_MOD_CACHE[f] = (mtime, size)
        except Exception as e:
            logger.debug("Claude Code sync notice: %s", e)

        # ----------------------------------------------------
        # 2. Antigravity IDE Transcript Sync (Gemini 3.7 Flash)
        # ----------------------------------------------------
        try:
            files = glob.glob(os.path.expanduser("~/.gemini/antigravity-ide/brain/*/.system_generated/logs/transcript.jsonl"))
            for f in files:
                try:
                    st = os.stat(f)
                    mtime, size = st.st_mtime, st.st_size
                except OSError:
                    continue

                cached = _FILE_MOD_CACHE.get(f)
                if cached == (mtime, size):
                    continue

                conv_id = f.split("/")[-4]
                session_text = ""
                steps = []
                accumulated_chars = 0
                with open(f, "r", encoding="utf-8", errors="ignore") as fp:
                    for line in fp:
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                        except Exception:
                            continue

                        if len(session_text) < 150000:
                            session_text += line

                        accumulated_chars += len(line)

                        t_type = data.get("type")
                        if t_type == "PLANNER_RESPONSE":
                            step_index = data.get("step_index", 0)
                            step_id = f"agy_{conv_id}_{step_index}"

                            content_str = (data.get("content") or "") + (data.get("thinking") or "")
                            tool_calls_str = json.dumps(data.get("tool_calls") or []) if data.get("tool_calls") else ""
                            out_content = content_str + tool_calls_str
                            out_toks = max(10, int(len(out_content) / 3.8))
                            in_toks = max(500, int(accumulated_chars / 3.8))

                            rate = get_model_cost("gemini-3.7-flash", "gemini")
                            in_rate = rate.get("input_per_k", 0.00010)
                            out_rate = rate.get("output_per_k", 0.00040)
                            cost = (in_toks / 1000) * in_rate + (out_toks / 1000) * out_rate
                            
                            context_pct = min(1.0, round(in_toks / 1_048_576, 4))
                            started_at = _parse_timestamp(data.get("created_at"))

                            steps.append((step_id, in_toks, out_toks, cost, context_pct, started_at))

                project_name = "General"
                if "tokenguard" in f or "tokenguard" in session_text:
                    project_name = "tokenguard"
                else:
                    project_name = _resolve_project_from_text(session_text, default="General")

                for step_id, in_toks, out_toks, cost, context_pct, started_at in steps:
                    if step_id in synced:
                        continue

                    cur.execute(
                        """
                        INSERT INTO usage_records (
                            provider, model_name, project_name, input_tokens, output_tokens,
                            cache_creation_tokens, cache_read_tokens, cost_usd,
                            context_usage_pct, context_warning, session_id, started_at
                        ) VALUES (?, ?, ?, ?, ?, 0, 0, ?, ?, 0, ?, ?)
                        """,
                        (
                            "gemini",
                            "gemini-3.7-flash (Antigravity)",
                            project_name,
                            in_toks,
                            out_toks,
                            round(cost, 6),
                            context_pct,
                            step_id,
                            started_at,
                        ),
                    )
                    synced.add(step_id)
                    new_synced_count += 1

                _FILE_MOD_CACHE[f] = (mtime, size)
        except Exception as e:
            logger.debug("Antigravity sync notice: %s", e)

        # ----------------------------------------------------
        # 3. ChatGPT / OpenAI Codex Database Sync
        # ----------------------------------------------------
        codex_db = os.path.expanduser("~/Library/Application Support/OpenAI/Codex/sqlite.db")
        if not os.path.exists(codex_db):
            codex_db = os.path.expanduser("~/.config/openai/codex.db")

        if os.path.exists(codex_db):
            try:
                st = os.stat(codex_db)
                mtime, size = st.st_mtime, st.st_size
                cached = _FILE_MOD_CACHE.get(codex_db)
                if cached != (mtime, size):
                    with sqlite3.connect(codex_db) as c_conn:
                        c_cur = c_conn.cursor()
                        c_cur.execute("SELECT thread_id, turn_id, started_at, duration_ms FROM thread_turns ORDER BY started_at ASC")
                        turns = c_cur.fetchall()
                        
                        thread_accumulated = {}

                        for t in turns:
                            thread_id, turn_id = t[0], t[1]
                            step_id = f"codex_{turn_id}"

                            c_cur.execute("SELECT item_json FROM thread_items WHERE turn_id = ? ORDER BY rollout_ordinal ASC", (turn_id,))
                            items = c_cur.fetchall()
                            turn_text = "".join(item[0] for item in items if item and item[0])
                            
                            prev_len = thread_accumulated.get(thread_id, 0)
                            curr_len = prev_len + len(turn_text)
                            thread_accumulated[thread_id] = curr_len

                            if step_id in synced:
                                continue

                            project_name = _resolve_project_from_text(turn_text, default="General")

                            in_toks = max(300, int(curr_len / 3.8))
                            out_toks = max(50, int(len(turn_text) / 8.0))
                            
                            rate = get_model_cost("gpt-5.6-sol", "openai")
                            in_rate = rate.get("input_per_k", 0.0050)
                            out_rate = rate.get("output_per_k", 0.0150)
                            cost = (in_toks / 1000) * in_rate + (out_toks / 1000) * out_rate
                            
                            context_pct = min(1.0, round(in_toks / 200_000, 4))
                            started_at = _parse_timestamp(t[2])

                            cur.execute(
                                """
                                INSERT INTO usage_records (
                                    provider, model_name, project_name, input_tokens, output_tokens,
                                    cache_creation_tokens, cache_read_tokens, cost_usd,
                                    context_usage_pct, context_warning, session_id, started_at
                                ) VALUES (?, ?, ?, ?, ?, 0, 0, ?, ?, 0, ?, ?)
                                """,
                                (
                                    "openai",
                                    "gpt-5.6-sol (ChatGPT Codex)",
                                    project_name,
                                    in_toks,
                                    out_toks,
                                    round(cost, 6),
                                    context_pct,
                                    step_id,
                                    started_at,
                                ),
                            )
                            synced.add(step_id)
                            new_synced_count += 1

                    _FILE_MOD_CACHE[codex_db] = (mtime, size)
            except Exception as e:
                logger.debug("Codex sync notice: %s", e)

        conn.commit()
    return new_synced_count


async def start_collector_loop(interval_seconds: float = 60.0, db_path: Optional[str] = None):
    """Background loop that periodically syncs local coding tools activity with adaptive idle backoff."""
    current_interval = interval_seconds
    while True:
        try:
            new_records = await asyncio.to_thread(collect_local_coding_tools_activity, db_path=db_path)
            if new_records and new_records > 0:
                current_interval = max(30.0, interval_seconds)
            else:
                current_interval = min(300.0, current_interval * 1.5)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug("Collector loop iteration notice: %s", e)
            current_interval = 60.0
        await asyncio.sleep(current_interval)

