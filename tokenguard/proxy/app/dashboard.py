"""TokenGuard Interactive Visual Dashboard Router with Multi-Tool & Project-Level Cost Intelligence."""

import asyncio
import json
import os
import sqlite3
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Response, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter(tags=["dashboard"])


def _get_store():
    try:
        from tokenguard.storage import UsageStore
        return UsageStore()
    except Exception:
        try:
            from ...storage import UsageStore
            return UsageStore()
        except Exception:
            return None


def _get_config():
    try:
        from tokenguard import config
        return config
    except Exception:
        try:
            from ... import config
            return config
        except Exception:
            return None


def _compute_dashboard_sync(store, days: int, selected_project: Optional[str], daily_budget: float) -> dict:
    days_val = None if days == 0 else days
    stats = store.get_stats(days=days_val, project=selected_project)
    top_models = store.get_top_models(days=days_val, limit=10, project=selected_project)
    recent = store.get_live_feed(limit=50, project=selected_project)
    daily = store.get_daily_totals(days=days_val or 30, project=selected_project)
    # Project attribution is strictly all-time from project inception
    projects_data = store.get_project_stats(days=None)

    # Calculate today's metrics strictly based on local time
    now = time.time()
    local_now = datetime.fromtimestamp(now)
    start_of_day_local = datetime(local_now.year, local_now.month, local_now.day, 0, 0, 0)
    today_start_ts = start_of_day_local.timestamp()

    conn = store._get_conn()

    today_query = """SELECT 
                       COALESCE(SUM(cost_usd), 0) as spent,
                       COALESCE(SUM(input_tokens + output_tokens), 0) as tokens,
                       COALESCE(SUM(input_tokens), 0) as in_tokens,
                       COALESCE(SUM(output_tokens), 0) as out_tokens,
                       COUNT(*) as requests,
                       COALESCE(MAX(context_usage_pct), 0) as max_context_pct
                     FROM usage_records 
                     WHERE started_at >= ?"""
    today_params = [today_start_ts]
    if selected_project:
        today_query += " AND project_name = ?"
        today_params.append(selected_project)

    today_row = conn.execute(today_query, tuple(today_params)).fetchone()

    # Real-time token velocity (TPM over last 5 minutes)
    five_min_ago = now - 300
    vel_query = """SELECT COALESCE(SUM(input_tokens + output_tokens), 0) as recent_tokens 
                   FROM usage_records 
                   WHERE started_at >= ?"""
    vel_params = [five_min_ago]
    if selected_project:
        vel_query += " AND project_name = ?"
        vel_params.append(selected_project)
    vel_row = conn.execute(vel_query, tuple(vel_params)).fetchone()

    # Precision 4-Tool Matrix: Claude Code, Antigravity, ChatGPT, DeepSeek
    tool_predicates = {
        "claude_code": "(provider = 'anthropic' AND lower(model_name) NOT LIKE '%deepseek%') OR lower(model_name) LIKE '%claude%' OR lower(model_name) LIKE '%agnes%'",
        "antigravity": "provider = 'gemini' OR lower(model_name) LIKE '%gemini%'",
        "chatgpt": "provider = 'openai' OR lower(model_name) LIKE '%gpt%'",
        "deepseek": "provider = 'deepseek' OR lower(model_name) LIKE '%deepseek%'",
    }

    tool_matrix = {}
    tool_meta = {
        "claude_code": {"name": "Claude Code", "tag": "Claude Code CLI", "provider": "anthropic", "color": "#8B5CF6", "optimize_action": "Run /compact or /clear"},
        "antigravity": {"name": "Antigravity", "tag": "Antigravity (Gemini 3.7)", "provider": "gemini", "color": "#10B981", "optimize_action": "Start New Session"},
        "chatgpt": {"name": "ChatGPT / Codex", "tag": "ChatGPT (GPT-5.6 Sol)", "provider": "openai", "color": "#38BDF8", "optimize_action": "Open New Thread"},
        "deepseek": {"name": "DeepSeek", "tag": "DeepSeek (V4-Flash / R1)", "provider": "deepseek", "color": "#F59E0B", "optimize_action": "Clear History"},
    }

    for tool_key, pred in tool_predicates.items():
        base_query = f"SELECT COUNT(*) as requests, COALESCE(SUM(input_tokens + output_tokens), 0) as tokens, COALESCE(SUM(cost_usd), 0) as spent, COALESCE(MAX(context_usage_pct), 0) as max_context_pct FROM usage_records WHERE ({pred})"
        params = []
        if days_val:
            base_query += " AND started_at >= ?"
            params.append(now - (days_val * 86400))
        if selected_project:
            base_query += " AND project_name = ?"
            params.append(selected_project)

        row = conn.execute(base_query, tuple(params)).fetchone()

        # Latest context stress query for this tool
        l_query = f"SELECT context_usage_pct, model_name FROM usage_records WHERE ({pred})"
        l_params = []
        if selected_project:
            l_query += " AND project_name = ?"
            l_params.append(selected_project)
        l_query += " ORDER BY started_at DESC LIMIT 1"
        l_row = conn.execute(l_query, tuple(l_params)).fetchone()

        meta = tool_meta[tool_key]
        tool_matrix[tool_key] = {
            "name": meta["name"],
            "provider": meta["provider"],
            "tag": meta["tag"],
            "tokens": row["tokens"] if row else 0,
            "spent": round(row["spent"] if row else 0.0, 4),
            "requests": row["requests"] if row else 0,
            "context_stress_pct": round((l_row["context_usage_pct"] or 0.0) * 100, 1) if l_row else 0.0,
            "peak_context_pct": round((row["max_context_pct"] or 0.0) * 100, 1) if row else 0.0,
            "color": meta["color"],
            "optimize_action": meta["optimize_action"],
        }

    latest_overall_query = """SELECT context_usage_pct FROM usage_records"""
    latest_overall_params = []
    if selected_project:
        latest_overall_query += " WHERE project_name = ?"
        latest_overall_params.append(selected_project)
    latest_overall_query += " ORDER BY started_at DESC LIMIT 1"

    latest_overall_row = conn.execute(latest_overall_query, tuple(latest_overall_params)).fetchone()
    current_overall_pct = round(latest_overall_row["context_usage_pct"] or 0.0, 4) if latest_overall_row else 0.0

    conn.close()

    recent_tokens = vel_row["recent_tokens"] if vel_row else 0
    tpm = int(recent_tokens / 5) if recent_tokens else 0

    return {
        "summary": stats,
        "daily_budget": daily_budget,
        "selected_project": selected_project or "all",
        "timeframe_days": days,
        "projects": projects_data,
        "today": {
            "spent": round(today_row["spent"], 4) if today_row else 0.0,
            "tokens": today_row["tokens"] if today_row else 0,
            "input_tokens": today_row["in_tokens"] if today_row else 0,
            "output_tokens": today_row["out_tokens"] if today_row else 0,
            "requests": today_row["requests"] if today_row else 0,
            "max_context_pct": round(today_row["max_context_pct"], 4) if today_row else 0.0,
            "current_context_pct": current_overall_pct,
            "today_date": local_now.strftime("%Y-%m-%d"),
        },
        "velocity_tpm": tpm,
        "tool_matrix": tool_matrix,
        "top_models": top_models,
        "recent_requests": recent,
        "daily_trends": daily,
        "timestamp": time.time(),
    }


@router.get("/api/dashboard/data")
async def get_dashboard_data(days: int = 7, project: Optional[str] = Query(None)):
    """API endpoint providing aggregated metrics for the visual dashboard with project attribution."""
    store = _get_store()
    if not store:
        return JSONResponse({"error": "Storage engine unavailable"}, status_code=500)

    selected_project = project if project and project != "all" else None

    # Get configured daily budget
    cfg = _get_config()
    daily_budget = 50.0
    if cfg:
        try:
            val = cfg.get("daily_budget")
            if val is not None:
                daily_budget = float(val)
        except Exception:
            pass

    # Execute all SQL aggregation synchronously inside worker threadpool for 0ms event loop lag
    return await asyncio.to_thread(_compute_dashboard_sync, store, days, selected_project, daily_budget)


@router.post("/api/dashboard/budget")
async def update_daily_budget(request: Request):
    """Update custom daily budget setting in USD."""
    try:
        body = await request.json()
        budget = float(body.get("budget", 50.0))
        if budget <= 0:
            budget = 1.0
        cfg = _get_config()
        if cfg:
            cfg.set("daily_budget", budget)
        return {"status": "ok", "daily_budget": budget}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.post("/api/dashboard/clear")
async def clear_dashboard_data():
    """Clear usage database records."""
    store = _get_store()
    if not store:
        return JSONResponse({"error": "Storage engine unavailable"}, status_code=500)
    
    conn = store._get_conn()
    conn.execute("DELETE FROM usage_records")
    conn.commit()
    conn.close()
    return {"status": "cleared", "message": "All usage records reset successfully"}


@router.get("/dashboard", response_class=HTMLResponse)
@router.get("/ui", response_class=HTMLResponse)
async def dashboard_page():
    """Serve the complete TokenGuard Visual Dashboard single-page application."""
    return HTMLResponse(content=DASHBOARD_HTML)


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>TokenGuard | AI Cost & Context Intelligence</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Geist+Mono:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-base: #08090E;
      --bg-surface: rgba(16, 20, 31, 0.75);
      --bg-surface-elevated: rgba(22, 28, 45, 0.85);
      --bg-surface-active: rgba(30, 41, 68, 0.95);
      --border-subtle: rgba(255, 255, 255, 0.08);
      --border-medium: rgba(255, 255, 255, 0.14);
      --border-glow: rgba(99, 102, 241, 0.35);
      --text-primary: #F8FAFC;
      --text-secondary: #94A3B8;
      --text-tertiary: #64748B;
      --accent-indigo: #6366F1;
      --accent-cyan: #06B6D4;
      --accent-emerald: #10B981;
      --accent-violet: #8B5CF6;
      --accent-amber: #F59E0B;
      --accent-rose: #F43F5E;
      --radius-sm: 8px;
      --radius-md: 12px;
      --radius-lg: 18px;
      --radius-xl: 24px;
      --font-ui: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      --font-mono: 'Geist Mono', 'JetBrains Mono', monospace;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background-color: var(--bg-base);
      background-image: 
        radial-gradient(circle at 50% 0%, rgba(99, 102, 241, 0.14) 0%, transparent 50%),
        radial-gradient(circle at 85% 10%, rgba(6, 182, 212, 0.09) 0%, transparent 40%),
        radial-gradient(circle at 15% 30%, rgba(139, 92, 246, 0.07) 0%, transparent 45%);
      background-attachment: fixed;
      color: var(--text-primary);
      font-family: var(--font-ui);
      min-height: 100vh;
      overflow-x: hidden;
      padding-bottom: 60px;
      -webkit-font-smoothing: antialiased;
    }

    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.15); border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.25); }

    /* Top Navigation Bar */
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 14px 32px;
      border-bottom: 1px solid var(--border-subtle);
      backdrop-filter: blur(24px);
      -webkit-backdrop-filter: blur(24px);
      background: rgba(8, 9, 14, 0.85);
      position: sticky;
      top: 0;
      z-index: 100;
    }

    .brand-cluster {
      display: flex;
      align-items: center;
      gap: 16px;
    }

    .brand-logo-wrap {
      display: flex;
      align-items: center;
      gap: 12px;
      text-decoration: none;
    }

    .brand-icon {
      width: 36px;
      height: 36px;
      background: linear-gradient(135deg, #6366F1, #06B6D4);
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 0 20px rgba(99, 102, 241, 0.4);
      position: relative;
      overflow: hidden;
    }

    .brand-icon svg { width: 20px; height: 20px; color: white; }

    .brand-name {
      font-size: 19px;
      font-weight: 800;
      letter-spacing: -0.6px;
      background: linear-gradient(120deg, #FFFFFF 30%, #94A3B8 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .brand-tag {
      font-size: 10px;
      font-family: var(--font-mono);
      font-weight: 700;
      text-transform: uppercase;
      padding: 3px 8px;
      border-radius: 20px;
      background: rgba(99, 102, 241, 0.12);
      color: #818CF8;
      border: 1px solid rgba(99, 102, 241, 0.28);
      letter-spacing: 0.8px;
    }

    .daemon-indicator {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 11px;
      font-family: var(--font-mono);
      color: var(--accent-emerald);
      background: rgba(16, 185, 129, 0.1);
      border: 1px solid rgba(16, 185, 129, 0.22);
      padding: 4px 10px;
      border-radius: 20px;
    }

    .pulse-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--accent-emerald);
      box-shadow: 0 0 10px var(--accent-emerald);
      animation: pulse 2s infinite cubic-bezier(0.4, 0, 0.6, 1);
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(0.85); }
    }

    /* Central Segmented Tabs */
    .tab-pills {
      display: flex;
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 4px;
      gap: 4px;
    }

    .tab-pill-btn {
      background: transparent;
      border: none;
      color: var(--text-secondary);
      padding: 7px 16px;
      border-radius: 8px;
      font-family: var(--font-ui);
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 7px;
      transition: all 0.2s ease;
    }

    .tab-pill-btn:hover {
      color: var(--text-primary);
      background: rgba(255, 255, 255, 0.05);
    }

    .tab-pill-btn.active {
      background: rgba(99, 102, 241, 0.2);
      color: #FFFFFF;
      border: 1px solid rgba(99, 102, 241, 0.45);
      box-shadow: 0 2px 10px rgba(99, 102, 241, 0.2);
    }

    .tab-badge {
      font-size: 10px;
      font-family: var(--font-mono);
      padding: 1px 6px;
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.08);
      color: var(--text-secondary);
    }

    .tab-pill-btn.active .tab-badge {
      background: rgba(99, 102, 241, 0.35);
      color: #C7D2FE;
    }

    /* Right Action Bar */
    .header-actions {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .timeframe-pills {
      display: flex;
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 3px;
      gap: 3px;
    }

    .tf-btn {
      background: transparent;
      border: none;
      color: var(--text-secondary);
      padding: 5px 12px;
      border-radius: 6px;
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s ease;
    }

    .tf-btn:hover { color: var(--text-primary); }
    .tf-btn.active {
      background: #6366F1;
      color: #FFFFFF;
      box-shadow: 0 0 12px rgba(99, 102, 241, 0.4);
    }

    .icon-btn {
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border-subtle);
      color: var(--text-secondary);
      padding: 7px 12px;
      border-radius: var(--radius-md);
      font-family: var(--font-ui);
      font-size: 12px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 6px;
      cursor: pointer;
      transition: all 0.2s ease;
    }

    .icon-btn:hover {
      background: rgba(255, 255, 255, 0.09);
      color: var(--text-primary);
      border-color: var(--border-medium);
    }

    .icon-btn svg { width: 14px; height: 14px; }

    /* Main Container */
    .main-wrap {
      max-width: 1440px;
      margin: 0 auto;
      padding: 24px 32px 0 32px;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }

    /* Timeframe Notice Banner */
    .timeframe-alert {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 10px 18px;
      border-radius: var(--radius-md);
      background: rgba(99, 102, 241, 0.08);
      border: 1px solid rgba(99, 102, 241, 0.22);
      font-size: 12px;
    }

    .tf-left {
      display: flex;
      align-items: center;
      gap: 10px;
      color: #E2E8F0;
    }

    .tf-badge-pill {
      font-family: var(--font-mono);
      font-weight: 700;
      font-size: 10px;
      text-transform: uppercase;
      padding: 2px 8px;
      border-radius: 10px;
      background: #6366F1;
      color: white;
    }

    .tf-right {
      display: flex;
      align-items: center;
      gap: 12px;
      font-family: var(--font-mono);
      color: var(--text-tertiary);
      font-size: 11px;
    }

    /* KPI Hero Cards Grid */
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
    }

    .kpi-card {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-lg);
      padding: 20px;
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      position: relative;
      overflow: hidden;
      transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    }

    .kpi-card:hover {
      transform: translateY(-2px);
      border-color: rgba(99, 102, 241, 0.3);
      box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
    }

    .kpi-card::before {
      content: '';
      position: absolute;
      top: 0; left: 0; right: 0; height: 2px;
      background: linear-gradient(90deg, transparent, var(--card-accent, #6366F1), transparent);
      opacity: 0.6;
    }

    .kpi-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }

    .kpi-title {
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      color: var(--text-secondary);
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .kpi-icon-wrap {
      width: 28px;
      height: 28px;
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.05);
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--card-accent, #6366F1);
    }

    .kpi-icon-wrap svg { width: 15px; height: 15px; }

    .kpi-val {
      font-size: 32px;
      font-weight: 800;
      letter-spacing: -1px;
      font-family: var(--font-mono);
      color: var(--text-primary);
      margin-bottom: 8px;
      display: flex;
      align-items: baseline;
      gap: 4px;
    }

    .kpi-sub-val {
      font-size: 14px;
      color: var(--text-tertiary);
      font-weight: 500;
    }

    .kpi-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 11px;
      color: var(--text-secondary);
      padding-top: 10px;
      border-top: 1px solid rgba(255, 255, 255, 0.05);
    }

    .kpi-tag {
      font-family: var(--font-mono);
      font-weight: 600;
      padding: 2px 7px;
      border-radius: 6px;
      background: rgba(255, 255, 255, 0.05);
      color: var(--text-secondary);
    }

    .kpi-tag.success { background: rgba(16, 185, 129, 0.12); color: var(--accent-emerald); }
    .kpi-tag.warning { background: rgba(245, 158, 11, 0.12); color: var(--accent-amber); }
    .kpi-tag.danger { background: rgba(244, 63, 94, 0.12); color: var(--accent-rose); }

    /* AI Tools Matrix HUD */
    .section-head {
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      margin-bottom: 14px;
    }

    .section-title-wrap h2 {
      font-size: 16px;
      font-weight: 700;
      letter-spacing: -0.3px;
      color: var(--text-primary);
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .section-title-wrap p {
      font-size: 12px;
      color: var(--text-tertiary);
      margin-top: 2px;
    }

    .tools-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
    }

    .tool-card {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-lg);
      padding: 20px;
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      gap: 14px;
      position: relative;
      transition: all 0.2s ease;
    }

    .tool-card:hover {
      border-color: var(--tool-color, #6366F1);
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.6), 0 0 20px -5px var(--tool-glow, rgba(99, 102, 241, 0.2));
      transform: translateY(-2px);
    }

    .tool-card-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .tool-info {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .tool-icon {
      width: 32px;
      height: 32px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--tool-bg, rgba(99, 102, 241, 0.15));
      color: var(--tool-color, #818CF8);
    }

    .tool-icon svg { width: 18px; height: 18px; }

    .tool-name-box h3 {
      font-size: 14px;
      font-weight: 700;
      color: var(--text-primary);
    }

    .tool-name-box span {
      font-size: 10px;
      font-family: var(--font-mono);
      color: var(--text-tertiary);
    }

    .tool-metrics-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      padding: 10px 12px;
      background: rgba(0, 0, 0, 0.25);
      border-radius: var(--radius-md);
      border: 1px solid rgba(255, 255, 255, 0.04);
    }

    .tool-metric-item {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .tool-metric-item .t-label {
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--text-tertiary);
    }

    .tool-metric-item .t-val {
      font-size: 15px;
      font-weight: 700;
      font-family: var(--font-mono);
      color: var(--text-primary);
    }

    .context-gauge-wrap {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .gauge-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 11px;
    }

    .gauge-title {
      color: var(--text-secondary);
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 4px;
    }

    .gauge-pct {
      font-family: var(--font-mono);
      font-weight: 700;
    }

    .gauge-bar-track {
      height: 6px;
      width: 100%;
      background: rgba(255, 255, 255, 0.08);
      border-radius: 10px;
      overflow: hidden;
      position: relative;
    }

    .gauge-bar-fill {
      height: 100%;
      border-radius: 10px;
      transition: width 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
    }

    /* Dual Analytics Columns */
    .analytics-grid {
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 20px;
    }

    .panel-card {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-lg);
      padding: 22px;
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      display: flex;
      flex-direction: column;
    }

    .panel-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 18px;
    }

    .panel-head h3 {
      font-size: 14px;
      font-weight: 700;
      color: var(--text-primary);
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .chart-container {
      width: 100%;
      height: 220px;
      position: relative;
    }

    .svg-chart {
      width: 100%;
      height: 100%;
      overflow: visible;
    }

    .chart-grid-line {
      stroke: rgba(255, 255, 255, 0.05);
      stroke-dasharray: 4 4;
    }

    .chart-area {
      fill: url(#areaGradient);
    }

    .chart-line {
      fill: none;
      stroke: #6366F1;
      stroke-width: 2.5;
      stroke-linecap: round;
      stroke-linejoin: round;
      filter: drop-shadow(0 4px 10px rgba(99, 102, 241, 0.5));
    }

    .chart-dot {
      fill: #08090E;
      stroke: #6366F1;
      stroke-width: 2.5;
      cursor: pointer;
      transition: r 0.2s ease, stroke-width 0.2s ease;
    }

    .chart-dot:hover {
      r: 6;
      stroke: #FFFFFF;
      stroke-width: 3;
    }

    .chart-tooltip {
      position: absolute;
      background: rgba(15, 23, 42, 0.95);
      border: 1px solid rgba(99, 102, 241, 0.4);
      padding: 8px 12px;
      border-radius: 8px;
      font-size: 11px;
      font-family: var(--font-mono);
      pointer-events: none;
      opacity: 0;
      transition: opacity 0.15s ease, transform 0.15s ease;
      box-shadow: 0 8px 20px rgba(0, 0, 0, 0.6);
      z-index: 10;
      transform: translate(-50%, -110%);
    }

    /* Model Cost Rankings */
    .model-ranks-list {
      display: flex;
      flex-direction: column;
      gap: 10px;
      overflow-y: auto;
      max-height: 220px;
      padding-right: 4px;
    }

    .model-rank-item {
      display: flex;
      flex-direction: column;
      gap: 5px;
      padding: 8px 12px;
      border-radius: var(--radius-sm);
      background: rgba(255, 255, 255, 0.025);
      border: 1px solid rgba(255, 255, 255, 0.04);
      transition: all 0.15s ease;
    }

    .model-rank-item:hover {
      background: rgba(255, 255, 255, 0.05);
      border-color: rgba(255, 255, 255, 0.08);
    }

    .m-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 12px;
    }

    .m-name {
      font-weight: 600;
      color: var(--text-primary);
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .provider-pill {
      font-size: 9px;
      font-family: var(--font-mono);
      text-transform: uppercase;
      padding: 1px 5px;
      border-radius: 4px;
      font-weight: 700;
    }

    .provider-pill.anthropic { background: rgba(139, 92, 246, 0.15); color: #C4B5FD; }
    .provider-pill.gemini { background: rgba(16, 185, 129, 0.15); color: #6EE7B7; }
    .provider-pill.openai { background: rgba(56, 189, 248, 0.15); color: #7DD3FC; }
    .provider-pill.deepseek { background: rgba(245, 158, 11, 0.15); color: #FCD34D; }

    .m-cost {
      font-family: var(--font-mono);
      font-weight: 700;
      color: var(--text-primary);
    }

    .m-bar-bg {
      height: 4px;
      background: rgba(255, 255, 255, 0.06);
      border-radius: 4px;
      overflow: hidden;
    }

    .m-bar-fg {
      height: 100%;
      background: linear-gradient(90deg, #6366F1, #06B6D4);
      border-radius: 4px;
    }

    /* Projects Table */
    .projects-table-wrap { overflow-x: auto; }

    table.styled-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }

    table.styled-table th {
      text-align: left;
      padding: 12px 16px;
      color: var(--text-tertiary);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      font-weight: 600;
      border-bottom: 1px solid var(--border-subtle);
    }

    table.styled-table td {
      padding: 14px 16px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
      color: var(--text-secondary);
    }

    table.styled-table tr:hover td {
      background: rgba(255, 255, 255, 0.02);
      color: var(--text-primary);
    }

    .project-name-cell {
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 700;
      color: var(--text-primary);
    }

    .proj-icon {
      width: 24px;
      height: 24px;
      border-radius: 6px;
      background: rgba(99, 102, 241, 0.15);
      color: #818CF8;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .proj-icon svg { width: 14px; height: 14px; }

    .filter-btn-pill {
      background: transparent;
      border: 1px solid var(--border-subtle);
      color: var(--text-secondary);
      padding: 3px 8px;
      border-radius: 12px;
      font-size: 11px;
      cursor: pointer;
      transition: all 0.15s ease;
    }

    .filter-btn-pill:hover, .filter-btn-pill.active {
      background: #6366F1;
      color: white;
      border-color: #6366F1;
    }

    /* Live Requests Feed Stream Table */
    .stream-filter-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
      gap: 16px;
    }

    .search-input-wrap {
      display: flex;
      align-items: center;
      background: rgba(0, 0, 0, 0.25);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 6px 12px;
      gap: 8px;
      width: 320px;
    }

    .search-input-wrap svg { width: 14px; height: 14px; color: var(--text-tertiary); }
    .search-input-wrap input {
      background: transparent;
      border: none;
      color: var(--text-primary);
      font-size: 12px;
      font-family: var(--font-ui);
      width: 100%;
      outline: none;
    }

    .feed-mono-table {
      width: 100%;
      border-collapse: collapse;
      font-family: var(--font-mono);
      font-size: 12px;
    }

    .feed-mono-table th {
      text-align: left;
      padding: 10px 14px;
      color: var(--text-tertiary);
      font-size: 10px;
      text-transform: uppercase;
      border-bottom: 1px solid var(--border-subtle);
    }

    .feed-mono-table td {
      padding: 10px 14px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.03);
      color: #CBD5E1;
    }

    .token-flow-badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      font-family: var(--font-mono);
      color: var(--text-primary);
    }

    .token-flow-badge .arrow { color: var(--accent-cyan); }

    /* Modals */
    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.75);
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 999;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.2s ease;
    }

    .modal-backdrop.open { opacity: 1; pointer-events: auto; }

    .modal-card {
      background: #0E1322;
      border: 1px solid var(--border-medium);
      border-radius: var(--radius-xl);
      width: 520px;
      max-width: 90vw;
      padding: 28px;
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.8), 0 0 30px rgba(99, 102, 241, 0.2);
      transform: scale(0.95);
      transition: transform 0.2s ease;
    }

    .modal-backdrop.open .modal-card { transform: scale(1); }

    .modal-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }

    .modal-head h3 { font-size: 18px; font-weight: 700; color: var(--text-primary); }
    .modal-close-btn { background: transparent; border: none; color: var(--text-tertiary); cursor: pointer; }
    .modal-close-btn:hover { color: var(--text-primary); }
    .modal-desc { font-size: 13px; color: var(--text-secondary); line-height: 1.5; margin-bottom: 20px; }

    .code-box {
      background: rgba(0, 0, 0, 0.4);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: var(--radius-md);
      padding: 12px 14px;
      font-family: var(--font-mono);
      font-size: 12px;
      color: #A5B4FC;
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }

    .copy-chip-btn {
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.1);
      color: white;
      font-size: 11px;
      font-weight: 600;
      padding: 4px 8px;
      border-radius: 6px;
      cursor: pointer;
    }

    .copy-chip-btn:hover { background: #6366F1; }

    .input-field-wrap { margin-bottom: 16px; }
    .input-field-wrap label { display: block; font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 6px; }
    .input-field-wrap input {
      width: 100%;
      background: rgba(0, 0, 0, 0.3);
      border: 1px solid var(--border-medium);
      border-radius: var(--radius-md);
      padding: 10px 14px;
      color: var(--text-primary);
      font-family: var(--font-mono);
      font-size: 14px;
      outline: none;
    }
    .input-field-wrap input:focus { border-color: #6366F1; box-shadow: 0 0 15px rgba(99, 102, 241, 0.3); }

    .preset-chips-row { display: flex; gap: 8px; margin-bottom: 24px; }
    .preset-chip {
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border-subtle);
      color: var(--text-secondary);
      padding: 6px 14px;
      border-radius: var(--radius-sm);
      font-family: var(--font-mono);
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
    }
    .preset-chip:hover { background: rgba(255, 255, 255, 0.1); color: var(--text-primary); }

    .modal-foot { display: flex; justify-content: flex-end; gap: 10px; }
    .btn-secondary {
      background: transparent;
      border: 1px solid var(--border-subtle);
      color: var(--text-secondary);
      padding: 8px 16px;
      border-radius: var(--radius-md);
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
    }

    .btn-primary {
      background: #6366F1;
      border: none;
      color: white;
      padding: 8px 20px;
      border-radius: var(--radius-md);
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      box-shadow: 0 0 15px rgba(99, 102, 241, 0.4);
    }
    .btn-primary:hover { background: #4F46E5; }

    @media (max-width: 1100px) {
      .kpi-grid, .tools-grid { grid-template-columns: repeat(2, 1fr); }
      .analytics-grid { grid-template-columns: 1fr; }
    }

    @media (max-width: 768px) {
      header { flex-direction: column; gap: 12px; padding: 12px 16px; }
      .main-wrap { padding: 16px; }
      .kpi-grid, .tools-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>

  <!-- Top Navigation Header -->
  <header>
    <div class="brand-cluster">
      <a class="brand-logo-wrap" href="/dashboard">
        <div class="brand-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
        </div>
        <div class="brand-name">
          TokenGuard
          <span class="brand-tag"><span data-i18n="tag_arch">ENTERPRISE</span></span>
        </div>
      </a>
      <div class="daemon-indicator">
        <div class="pulse-dot"></div>
        <span><span data-i18n="proxy_live">PORT 8001 · FAIL-OPEN ACTIVE</span></span>
      </div>
    </div>

    <!-- Segmented Tab Navigation -->
    <div class="tab-pills">
      <button class="tab-pill-btn active" onclick="switchTab('overview')" id="tabBtnOverview">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/></svg>
        <span><span data-i18n="tab_overview">Telemetry & Tools</span></span>
      </button>
      <button class="tab-pill-btn" onclick="switchTab('projects')" id="tabBtnProjects">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
        <span><span data-i18n="tab_projects">Project Attribution</span></span>
        <span class="tab-badge" id="navProjectCountBadge">0</span>
      </button>
      <button class="tab-pill-btn" onclick="switchTab('audit')" id="tabBtnAudit">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
        <span><span data-i18n="tab_audit">Request Trace</span></span>
      </button>
    </div>

    <!-- Right Controls -->
    <div class="header-actions">
      <!-- Timeframe Switcher -->
      <div class="timeframe-pills">
        <button class="tf-btn" onclick="switchTimeframe(1)" id="tf1" title="Today">1D</button>
        <button class="tf-btn active" onclick="switchTimeframe(7)" id="tf7" title="Last 7 Days">7D</button>
        <button class="tf-btn" onclick="switchTimeframe(30)" id="tf30" title="Last 30 Days">30D</button>
        <button class="tf-btn" onclick="switchTimeframe(0)" id="tf0" title="All-Time Cumulative"><span data-i18n="tf_all_short">All</span></button>
      </div>

      <!-- Quick Integration Snippets -->
      <button class="icon-btn" onclick="openSetupModal()" title="Quick Setup Guide">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
        <span><span data-i18n="btn_setup">Config</span></span>
      </button>

      <!-- Daily Budget Trigger -->
      <button class="icon-btn" onclick="openBudgetModal()" title="Adjust Budget">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/><path d="M12 6v2"/><path d="M12 16v2"/></svg>
        <span><span data-i18n="btn_budget">Budget</span></span>
      </button>

      <!-- Language Toggle -->
      <button class="icon-btn" onclick="toggleLang()" id="langBtn" title="Toggle Language">
        <span>EN / 中</span>
      </button>
    </div>
  </header>

  <!-- Main View Area -->
  <main class="main-wrap">

    <!-- Active Timeframe & Project Attribution Notice -->
    <div class="timeframe-alert">
      <div class="tf-left">
        <span class="tf-badge-pill" id="currentTimeframeBadge">7-Day Window</span>
        <span id="timeframeNoticeText"><span data-i18n="timeframe_notice">Displaying AI spending and token consumption for the selected timeframe.</span></span>
      </div>
      <div class="tf-right">
        <span id="selectedProjectTag">Project: ALL</span>
        <span>·</span>
        <span id="lastRefreshTime">Updated just now</span>
      </div>
    </div>

    <!-- TAB 1: OVERVIEW & TELEMETRY -->
    <div id="viewOverview">

      <!-- Hero KPI Metrics -->
      <section class="kpi-grid">
        <!-- KPI 1: Spend & Budget -->
        <div class="kpi-card" style="--card-accent: #6366F1;">
          <div class="kpi-header">
            <div class="kpi-title"><span data-i18n="kpi_spent">Period Expenditure</span></div>
            <div class="kpi-icon-wrap">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
            </div>
          </div>
          <div class="kpi-val" id="kpiSpentVal">$0.00</div>
          <div class="kpi-footer">
            <span><span data-i18n="kpi_today_spent">Today's Spend:</span> <strong id="kpiTodaySpent" style="color:var(--text-primary);">$0.00</strong></span>
            <span class="kpi-tag" id="kpiBudgetStatusTag">ON TRACK</span>
          </div>
        </div>

        <!-- KPI 2: Total Tokens -->
        <div class="kpi-card" style="--card-accent: #06B6D4;">
          <div class="kpi-header">
            <div class="kpi-title"><span data-i18n="kpi_tokens">Total Tokens</span></div>
            <div class="kpi-icon-wrap">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
            </div>
          </div>
          <div class="kpi-val" id="kpiTokensVal">0 <span class="kpi-sub-val">tok</span></div>
          <div class="kpi-footer">
            <span><span data-i18n="kpi_today_tokens">Today:</span> <strong id="kpiTodayTokens" style="color:var(--text-primary);">0</strong></span>
            <span class="kpi-tag success">O(1) SNIFFER</span>
          </div>
        </div>

        <!-- KPI 3: Total Requests -->
        <div class="kpi-card" style="--card-accent: #10B981;">
          <div class="kpi-header">
            <div class="kpi-title"><span data-i18n="kpi_calls">Intercepted Calls</span></div>
            <div class="kpi-icon-wrap">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
            </div>
          </div>
          <div class="kpi-val" id="kpiCallsVal">0</div>
          <div class="kpi-footer">
            <span><span data-i18n="kpi_avg_cost">Avg Cost/Req:</span> <strong id="kpiAvgCost" style="color:var(--text-primary);">$0.00</strong></span>
            <span class="kpi-tag success">0% DROPPED</span>
          </div>
        </div>

        <!-- KPI 4: Realtime Velocity & Context Load -->
        <div class="kpi-card" style="--card-accent: #8B5CF6;">
          <div class="kpi-header">
            <div class="kpi-title"><span data-i18n="kpi_velocity">Velocity & Stress</span></div>
            <div class="kpi-icon-wrap">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
            </div>
          </div>
          <div class="kpi-val" id="kpiVelocityVal">0 <span class="kpi-sub-val">TPM</span></div>
          <div class="kpi-footer">
            <span><span data-i18n="kpi_context_load">Live Context:</span> <strong id="kpiContextLoad" style="color:var(--text-primary);">0%</strong></span>
            <span class="kpi-tag success" id="kpiHealthTag">HEALTHY</span>
          </div>
        </div>
      </section>

      <!-- Connected AI Coding Tools Matrix -->
      <section style="margin-top: 24px;">
        <div class="section-head">
          <div class="section-title-wrap">
            <h2><span data-i18n="tools_head">Connected AI Coding Tools & Workspaces</span></h2>
            <p><span data-i18n="tools_desc">Real-time live telemetry, context window pressure, and cost attribution per client tool.</span></p>
          </div>
        </div>

        <div class="tools-grid" id="toolsGrid">
          <!-- Dynamically Rendered via renderToolMatrix() -->
        </div>
      </section>

      <!-- Charts & Model Cost Share -->
      <section class="analytics-grid" style="margin-top: 24px;">
        <!-- Left: Daily Spend & Token Trend Area Chart -->
        <div class="panel-card">
          <div class="panel-head">
            <h3>
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/></svg>
              <span data-i18n="chart_trend_title">Daily Expenditure & Token Trajectory</span>
            </h3>
            <span style="font-size:11px; font-family:var(--font-mono); color:var(--text-tertiary);"><span data-i18n="chart_granularity">30-Day Timeline</span></span>
          </div>
          <div class="chart-container" id="trendChartContainer">
            <svg class="svg-chart" id="trendSvg" viewBox="0 0 700 200" preserveAspectRatio="none">
              <defs>
                <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#6366F1" stop-opacity="0.35"/>
                  <stop offset="100%" stop-color="#6366F1" stop-opacity="0.0"/>
                </linearGradient>
              </defs>
              <g id="chartGrid"></g>
              <path class="chart-area" id="chartAreaPath" d=""></path>
              <path class="chart-line" id="chartLinePath" d=""></path>
              <g id="chartDots"></g>
            </svg>
            <div class="chart-tooltip" id="chartTooltip"></div>
          </div>
        </div>

        <!-- Right: Top Models Cost Share -->
        <div class="panel-card">
          <div class="panel-head">
            <h3>
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>
              <span data-i18n="models_head">Top Models by Expenditure</span>
            </h3>
          </div>
          <div class="model-ranks-list" id="modelsRankList">
            <!-- Dynamically populated -->
          </div>
        </div>
      </section>

      <!-- Recent Live Stream Preview -->
      <section style="margin-top: 24px;">
        <div class="section-head">
          <div class="section-title-wrap">
            <h2><span data-i18n="feed_head">Real-time Stream Telemetry</span></h2>
            <p><span data-i18n="feed_desc">Recent intercepted API calls with token usage, input/output ratio, and cost.</span></p>
          </div>
          <button class="icon-btn" onclick="switchTab('audit')">
            <span data-i18n="btn_view_full_audit">View Full Audit Log</span> →
          </button>
        </div>

        <div class="panel-card" style="padding:0; overflow:hidden;">
          <table class="feed-mono-table" id="previewFeedTable">
            <thead>
              <tr>
                <th><span data-i18n="th_time">Time</span></th>
                <th><span data-i18n="th_project">Project</span></th>
                <th><span data-i18n="th_model">Model / Provider</span></th>
                <th><span data-i18n="th_tokens">Tokens (In → Out)</span></th>
                <th><span data-i18n="th_cost">Cost</span></th>
              </tr>
            </thead>
            <tbody id="previewFeedBody">
              <!-- Dynamically populated -->
            </tbody>
          </table>
        </div>
      </section>

    </div>

    <!-- TAB 2: PROJECTS COST ATTRIBUTION -->
    <div id="viewProjects" style="display: none;">
      <section>
        <div class="section-head">
          <div class="section-title-wrap">
            <h2><span data-i18n="proj_head">Projects & Workspaces Cost Center</span></h2>
            <p><span data-i18n="proj_desc">All-time lifetime token consumption and cost attribution from project inception.</span></p>
          </div>
        </div>

        <div class="panel-card" style="padding:0; overflow:hidden;">
          <div class="projects-table-wrap">
            <table class="styled-table" id="projectsFullTable">
              <thead>
                <tr>
                  <th><span data-i18n="th_project">Project / Workspace</span></th>
                  <th><span data-i18n="th_calls">Total Calls</span></th>
                  <th><span data-i18n="th_tokens">Total Tokens</span></th>
                  <th><span data-i18n="th_spent">Total Spent</span></th>
                  <th><span data-i18n="th_share">Cost Share</span></th>
                  <th><span data-i18n="th_last_active">Last Active</span></th>
                  <th></th>
                </tr>
              </thead>
              <tbody id="projectsTableBody">
                <!-- Dynamically populated -->
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>

    <!-- TAB 3: FULL AUDIT TRACE LOG -->
    <div id="viewAudit" style="display: none;">
      <section>
        <div class="section-head">
          <div class="section-title-wrap">
            <h2><span data-i18n="audit_head">Complete Intercepted Request Audit Stream</span></h2>
            <p><span data-i18n="audit_desc">Detailed granular audit log of every LLM request processed through the TokenGuard proxy.</span></p>
          </div>
        </div>

        <div class="panel-card" style="padding: 16px;">
          <div class="stream-filter-bar">
            <div class="search-input-wrap">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
              <input type="text" id="streamSearchInput" placeholder="Filter by project, model, or keywords..." oninput="filterStreamTable()">
            </div>
            <div style="font-size:12px; font-family:var(--font-mono); color:var(--text-tertiary);">
              <span id="filteredStreamCount">50</span> <span><span data-i18n="records_shown">records shown</span></span>
            </div>
          </div>

          <div style="overflow-x: auto;">
            <table class="feed-mono-table" id="fullFeedTable">
              <thead>
                <tr>
                  <th><span data-i18n="th_time">Time</span></th>
                  <th><span data-i18n="th_project">Project</span></th>
                  <th><span data-i18n="th_model">Model / Provider</span></th>
                  <th><span data-i18n="th_tokens">Tokens (In → Out)</span></th>
                  <th><span data-i18n="th_cost">Cost</span></th>
                </tr>
              </thead>
              <tbody id="fullFeedBody">
                <!-- Dynamically populated -->
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>

  </main>

  <!-- Setup & Configuration Modal -->
  <div class="modal-backdrop" id="setupModal" onclick="if(event.target===this) closeSetupModal()">
    <div class="modal-card">
      <div class="modal-head">
        <h3><span data-i18n="setup_modal_title">Quick Developer Configuration</span></h3>
        <button class="modal-close-btn" onclick="closeSetupModal()">✕</button>
      </div>
      <p class="modal-desc"><span data-i18n="setup_modal_desc">Configure your development tools to route through TokenGuard (Port 8001) for automated zero-lag billing, fail-open resilience, and context stress monitoring.</span></p>
      
      <div style="margin-bottom: 12px; font-size: 12px; font-weight: 700; color: #818CF8;">Claude Code CLI (.zshrc / .bashrc)</div>
      <div class="code-box">
        <code>export ANTHROPIC_BASE_URL="http://localhost:8001"</code>
        <button class="copy-chip-btn" onclick="copySnippet('export ANTHROPIC_BASE_URL=\"http://localhost:8001\"')">Copy</button>
      </div>

      <div style="margin-bottom: 12px; font-size: 12px; font-weight: 700; color: #38BDF8;">OpenAI / Cursor Base URL</div>
      <div class="code-box">
        <code>http://localhost:8001/openai/v1</code>
        <button class="copy-chip-btn" onclick="copySnippet('http://localhost:8001/openai/v1')">Copy</button>
      </div>

      <div style="margin-bottom: 12px; font-size: 12px; font-weight: 700; color: #10B981;">Gemini Base URL</div>
      <div class="code-box">
        <code>http://localhost:8001/gemini</code>
        <button class="copy-chip-btn" onclick="copySnippet('http://localhost:8001/gemini')">Copy</button>
      </div>

      <div class="modal-foot" style="margin-top: 20px;">
        <button class="btn-primary" onclick="closeSetupModal()">Done</button>
      </div>
    </div>
  </div>

  <!-- Daily Budget Modal -->
  <div class="modal-backdrop" id="budgetModal" onclick="if(event.target===this) closeBudgetModal()">
    <div class="modal-card">
      <div class="modal-head">
        <h3><span data-i18n="budget_modal_title">Set Daily Spending Target</span></h3>
        <button class="modal-close-btn" onclick="closeBudgetModal()">✕</button>
      </div>
      <p class="modal-desc"><span data-i18n="budget_modal_desc">Set your daily target AI spend threshold. TokenGuard will calculate progress metrics and display visual safety alerts.</span></p>
      
      <div class="input-field-wrap">
        <label><span data-i18n="budget_label">Daily Budget (USD)</span></label>
        <input type="number" id="budgetInput" min="1" step="5" value="50">
      </div>

      <div class="preset-chips-row">
        <button class="preset-chip" onclick="setBudgetPreset(20)">$20</button>
        <button class="preset-chip" onclick="setBudgetPreset(50)">$50</button>
        <button class="preset-chip" onclick="setBudgetPreset(100)">$100</button>
        <button class="preset-chip" onclick="setBudgetPreset(200)">$200</button>
      </div>

      <div class="modal-foot">
        <button class="btn-secondary" onclick="closeBudgetModal()"><span data-i18n="btn_cancel">Cancel</span></button>
        <button class="btn-primary" onclick="saveBudget()"><span data-i18n="btn_save">Save Budget</span></button>
      </div>
    </div>
  </div>

  <script>
    let currentLang = localStorage.getItem('tg_lang') || 'zh';
    let currentTimeframeDays = 7;
    let selectedProjectFilter = 'all';
    let userDailyBudget = 50.0;
    let currentRawData = null;
    let autoRefreshTimer = null;

    const I18N = {
      en: {
        tag_arch: "ENTERPRISE",
        proxy_live: "PORT 8001 · FAIL-OPEN ACTIVE",
        tab_overview: "Telemetry & Tools",
        tab_projects: "Project Attribution",
        tab_audit: "Request Trace",
        btn_setup: "Config",
        btn_budget: "Budget",
        tf_all_short: "All",
        timeframe_notice: "Displaying AI spending and token consumption for the selected timeframe.",
        kpi_spent: "Period Expenditure",
        kpi_today_spent: "Today's Spend:",
        kpi_tokens: "Total Tokens",
        kpi_today_tokens: "Today:",
        kpi_calls: "Intercepted Calls",
        kpi_avg_cost: "Avg Cost/Req:",
        kpi_velocity: "Velocity & Stress",
        kpi_context_load: "Live Context:",
        tools_head: "Connected AI Coding Tools & Workspaces",
        tools_desc: "Real-time live telemetry, context window pressure, and cost attribution per client tool.",
        chart_trend_title: "Daily Expenditure & Token Trajectory",
        chart_granularity: "30-Day Timeline",
        models_head: "Top Models by Expenditure",
        feed_head: "Real-time Stream Telemetry",
        feed_desc: "Recent intercepted API calls with token usage, input/output ratio, and cost.",
        btn_view_full_audit: "View Full Audit Log",
        proj_head: "Projects & Workspaces Cost Center",
        proj_desc: "All-time lifetime token consumption and cost attribution from project inception.",
        audit_head: "Complete Intercepted Request Audit Stream",
        audit_desc: "Detailed granular audit log of every LLM request processed through the TokenGuard proxy.",
        th_time: "Time",
        th_project: "Project",
        th_model: "Model / Provider",
        th_tokens: "Tokens (In → Out)",
        th_cost: "Cost",
        th_calls: "Total Calls",
        th_spent: "Total Spent",
        th_share: "Cost Share",
        th_last_active: "Last Active",
        records_shown: "records shown",
        setup_modal_title: "Quick Developer Configuration",
        setup_modal_desc: "Configure your development tools to route through TokenGuard (Port 8001) for automated zero-lag billing, fail-open resilience, and context stress monitoring.",
        budget_modal_title: "Set Daily Spending Target",
        budget_modal_desc: "Set your daily target AI spend threshold. TokenGuard will calculate progress metrics and display visual safety alerts.",
        budget_label: "Daily Budget (USD)",
        btn_cancel: "Cancel",
        btn_save: "Save Budget",
        status_on_track: "ON TRACK",
        status_near_limit: "⚠️ NEAR LIMIT",
        status_over_budget: "🚨 OVER BUDGET",
        filter_all_badge: "Displaying all projects",
        filter_single_badge: "Filtered by project:"
      },
      zh: {
        tag_arch: "工业级架构",
        proxy_live: "端口 8001 · 零阻塞高可用就绪",
        tab_overview: "实时指标与工具矩阵",
        tab_projects: "研发项目归集",
        tab_audit: "审计调用流",
        btn_setup: "配置接入",
        btn_budget: "设置预算",
        tf_all_short: "全周期",
        timeframe_notice: "当前展示所选时间维度的 AI 消费与 Token 吞吐分析。",
        kpi_spent: "统计期总花费",
        kpi_today_spent: "今日已用:",
        kpi_tokens: "Token 吞吐量",
        kpi_today_tokens: "今日 Token:",
        kpi_calls: "累计拦截请求",
        kpi_avg_cost: "次均成本:",
        kpi_velocity: "实时流速与负荷",
        kpi_context_load: "当前窗口负载:",
        tools_head: "AI 编程软件专属监控矩阵",
        tools_desc: "实时长连接遥测、上下文窗口压力负荷与各客户端独立计费归集。",
        chart_trend_title: "每日消费趋势与 Token 轨迹",
        chart_granularity: "30 天周期视图",
        models_head: "热门模型花费分布",
        feed_head: "实时请求拦截遥测",
        feed_desc: "最近流经代理的 LLM 调用明细、输入输出比例与单次成本。",
        btn_view_full_audit: "查看完整审计流水",
        proj_head: "研发项目与代码仓库成本归集",
        proj_desc: "从项目立项第一天起的全生命周期 Token 消耗与成本归集分析。",
        audit_head: "全量拦截请求审计流水",
        audit_desc: "经由 TokenGuard 代理转发生命周期的完整请求审计明细。",
        th_time: "时间",
        th_project: "所属项目",
        th_model: "模型 / 提供商",
        th_tokens: "Token 流向 (入 → 出)",
        th_cost: "单次花费",
        th_calls: "累计调用",
        th_spent: "累计花费",
        th_share: "占比",
        th_last_active: "最近活跃",
        records_shown: "条明细记录",
        setup_modal_title: "开发者快速接入配置",
        setup_modal_desc: "将开发工具的 Base URL 指向 TokenGuard (8001端口)，享受零阻塞计量、Fail-Open 容灾与上下文过载预警。",
        budget_modal_title: "设置每日消费预算",
        budget_modal_desc: "配置每日最高期望 AI 消费限额。系统会自动计算消耗进度并进行视觉预警。",
        budget_label: "每日预算 (USD)",
        btn_cancel: "取消",
        btn_save: "保存设置",
        status_on_track: "运行平稳",
        status_near_limit: "⚠️ 接近限额",
        status_over_budget: "🚨 超出预算",
        filter_all_badge: "当前展示全量项目",
        filter_single_badge: "已过滤当前项目:"
      }
    };

    function formatNumber(num) {
      if (num === null || num === undefined || isNaN(num)) return '0';
      num = Number(num);
      if (num >= 1e9) return (num / 1e9).toFixed(2) + ' B';
      if (num >= 1e6) return (num / 1e6).toFixed(2) + ' M';
      if (num >= 1e3) return (num / 1e3).toFixed(1) + ' k';
      return num.toLocaleString();
    }

    function formatCurrency(num) {
      if (!num && num !== 0 || isNaN(num)) return '$0.00';
      return '$' + Number(num).toFixed(2);
    }

    function applyI18n() {
      const t = I18N[currentLang] || I18N.zh;
      document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (t[key]) el.textContent = t[key];
      });
      const langBtn = document.getElementById('langBtn');
      if (langBtn) langBtn.textContent = currentLang === 'zh' ? '中 / EN' : 'EN / 中';
    }

    function toggleLang() {
      currentLang = currentLang === 'zh' ? 'en' : 'zh';
      localStorage.setItem('tg_lang', currentLang);
      applyI18n();
      if (currentRawData) renderDashboard(currentRawData);
    }

    function switchTab(tabId) {
      const viewOverview = document.getElementById('viewOverview');
      const viewProjects = document.getElementById('viewProjects');
      const viewAudit = document.getElementById('viewAudit');
      if (viewOverview) viewOverview.style.display = tabId === 'overview' ? 'block' : 'none';
      if (viewProjects) viewProjects.style.display = tabId === 'projects' ? 'block' : 'none';
      if (viewAudit) viewAudit.style.display = tabId === 'audit' ? 'block' : 'none';

      document.getElementById('tabBtnOverview')?.classList.toggle('active', tabId === 'overview');
      document.getElementById('tabBtnProjects')?.classList.toggle('active', tabId === 'projects');
      document.getElementById('tabBtnAudit')?.classList.toggle('active', tabId === 'audit');
    }

    function switchTimeframe(days) {
      currentTimeframeDays = days;
      document.querySelectorAll('.tf-btn').forEach(btn => btn.classList.remove('active'));
      if (days === 1) document.getElementById('tf1')?.classList.add('active');
      else if (days === 7) document.getElementById('tf7')?.classList.add('active');
      else if (days === 30) document.getElementById('tf30')?.classList.add('active');
      else if (days === 0) document.getElementById('tf0')?.classList.add('active');
      
      const badge = document.getElementById('currentTimeframeBadge');
      if (badge) {
        if (days === 0) badge.textContent = currentLang === 'zh' ? '全生命周期历史' : 'All-Time Cumulative';
        else if (days === 1) badge.textContent = currentLang === 'zh' ? '今日 24 小时' : 'Today (24h)';
        else if (days === 7) badge.textContent = currentLang === 'zh' ? '最近 7 天' : 'Last 7 Days';
        else if (days === 30) badge.textContent = currentLang === 'zh' ? '最近 30 天' : 'Last 30 Days';
      }

      fetchDashboardData();
    }

    function setProjectFilter(proj) {
      selectedProjectFilter = proj;
      fetchDashboardData();
    }

    async function fetchDashboardData() {
      try {
        const url = `/api/dashboard/data?days=${currentTimeframeDays}&project=${selectedProjectFilter}`;
        const res = await fetch(url);
        if (!res.ok) return;
        const data = await res.json();
        currentRawData = data;
        renderDashboard(data);
      } catch (e) {
        console.error("Dashboard fetch error:", e);
      }
    }

    function renderDashboard(data) {
      if (!data) return;
      const t = I18N[currentLang] || I18N.zh;

      // Summary
      const sum = data.summary || {};
      const elSpent = document.getElementById('kpiSpentVal');
      if (elSpent) elSpent.textContent = formatCurrency(sum.total_spent || 0);

      const elTokens = document.getElementById('kpiTokensVal');
      if (elTokens) elTokens.innerHTML = `${formatNumber(sum.total_tokens || 0)} <span class="kpi-sub-val">tok</span>`;

      const elCalls = document.getElementById('kpiCallsVal');
      if (elCalls) elCalls.textContent = (sum.total_requests || 0).toLocaleString();

      const elAvgCost = document.getElementById('kpiAvgCost');
      if (elAvgCost) elAvgCost.textContent = formatCurrency(sum.avg_cost_per_req || 0);

      // Today
      const today = data.today || {};
      const elTodaySpent = document.getElementById('kpiTodaySpent');
      if (elTodaySpent) elTodaySpent.textContent = formatCurrency(today.spent || 0);

      const elTodayTokens = document.getElementById('kpiTodayTokens');
      if (elTodayTokens) elTodayTokens.textContent = formatNumber(today.tokens || 0);

      // Velocity & Context Load
      const tpm = data.velocity_tpm || 0;
      const elVelocity = document.getElementById('kpiVelocityVal');
      if (elVelocity) elVelocity.innerHTML = `${formatNumber(tpm)} <span class="kpi-sub-val">TPM</span>`;

      const currentStress = ((today.current_context_pct || 0) * 100);
      const elContext = document.getElementById('kpiContextLoad');
      if (elContext) elContext.textContent = `${currentStress.toFixed(1)}%`;

      // Budget Status Tag
      userDailyBudget = data.daily_budget || 50.0;
      const budgetPct = userDailyBudget > 0 ? ((today.spent || 0) / userDailyBudget) * 100 : 0;
      const budgetTag = document.getElementById('kpiBudgetStatusTag');
      if (budgetTag) {
        if (budgetPct >= 100) {
          budgetTag.className = 'kpi-tag danger';
          budgetTag.textContent = t.status_over_budget;
        } else if (budgetPct >= 80) {
          budgetTag.className = 'kpi-tag warning';
          budgetTag.textContent = t.status_near_limit;
        } else {
          budgetTag.className = 'kpi-tag success';
          budgetTag.textContent = t.status_on_track;
        }
      }

      // Project filter tag
      const projTag = document.getElementById('selectedProjectTag');
      if (projTag) {
        projTag.textContent = selectedProjectFilter === 'all' 
          ? (currentLang === 'zh' ? '项目: 全部' : 'Project: ALL')
          : `Project: ${selectedProjectFilter}`;
      }

      const refreshEl = document.getElementById('lastRefreshTime');
      if (refreshEl) refreshEl.textContent = new Date().toLocaleTimeString();

      // Render Sub-components safely
      try { renderToolMatrix(data.tool_matrix || {}); } catch(e) { console.error("renderToolMatrix error:", e); }
      try { renderTrendChart(data.daily_trends || []); } catch(e) { console.error("renderTrendChart error:", e); }
      try { renderTopModels(data.top_models || []); } catch(e) { console.error("renderTopModels error:", e); }
      try { renderRecentFeed(data.recent_requests || []); } catch(e) { console.error("renderRecentFeed error:", e); }
      try { renderProjectsTable(data.projects || []); } catch(e) { console.error("renderProjectsTable error:", e); }
    }

    function renderToolMatrix(matrix) {
      const container = document.getElementById('toolsGrid');
      if (!container) return;
      container.innerHTML = '';

      const toolKeys = ['claude_code', 'antigravity', 'chatgpt', 'deepseek'];
      toolKeys.forEach(k => {
        const item = matrix[k] || { 
          name: k, 
          spent: 0, 
          tokens: 0, 
          requests: 0, 
          context_stress_pct: 0, 
          peak_context_pct: 0,
          color: '#6366F1' 
        };
        
        let stress = Number(item.context_stress_pct || 0);
        let stressColor = '#10B981';
        let stressStatus = currentLang === 'zh' ? '安全' : 'Safe';
        if (stress >= 80) { stressColor = '#F43F5E'; stressStatus = currentLang === 'zh' ? '过载' : 'High'; }
        else if (stress >= 50) { stressColor = '#F59E0B'; stressStatus = currentLang === 'zh' ? '注意' : 'Moderate'; }

        const card = document.createElement('div');
        card.className = 'tool-card';
        card.style.setProperty('--tool-color', item.color || '#6366F1');
        card.style.setProperty('--tool-bg', `${item.color || '#6366F1'}22`);
        card.style.setProperty('--tool-glow', `${item.color || '#6366F1'}40`);

        card.innerHTML = `
          <div>
            <div class="tool-card-head">
              <div class="tool-info">
                <div class="tool-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
                </div>
                <div class="tool-name-box">
                  <h3>${item.name}</h3>
                  <span>${item.tag || item.provider || ''}</span>
                </div>
              </div>
              <span class="kpi-tag" style="background:${stressColor}18; color:${stressColor}; font-weight:700;">${stressStatus}</span>
            </div>

            <div class="tool-metrics-row" style="margin-top: 14px;">
              <div class="tool-metric-item">
                <span class="t-label">${currentLang === 'zh' ? '花费' : 'Spent'}</span>
                <span class="t-val">${formatCurrency(item.spent)}</span>
              </div>
              <div class="tool-metric-item">
                <span class="t-label">Token</span>
                <span class="t-val">${formatNumber(item.tokens)}</span>
              </div>
            </div>
          </div>

          <div>
            <div class="context-gauge-wrap">
              <div class="gauge-top">
                <span class="gauge-title">${currentLang === 'zh' ? '上下文负荷' : 'Context Load'}</span>
                <span class="gauge-pct" style="color:${stressColor};">${stress.toFixed(1)}%</span>
              </div>
              <div class="gauge-bar-track">
                <div class="gauge-bar-fill" style="width:${Math.min(100, Math.max(0, stress))}%; background:${stressColor};"></div>
              </div>
            </div>

            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px; font-size:11px; font-family:var(--font-mono); color:var(--text-tertiary);">
              <span>${Number(item.requests || 0).toLocaleString()} ${currentLang === 'zh' ? '次调用' : 'calls'}</span>
              <span>${currentLang === 'zh' ? '峰值' : 'Peak'} ${item.peak_context_pct || 0}%</span>
            </div>
          </div>
        `;
        container.appendChild(card);
      });
    }

    function renderTrendChart(dailyData) {
      const svg = document.getElementById('trendSvg');
      const grid = document.getElementById('chartGrid');
      const dots = document.getElementById('chartDots');
      if (!svg || !grid || !dots) return;
      grid.innerHTML = '';
      dots.innerHTML = '';

      if (!dailyData || dailyData.length === 0) return;

      const width = 700;
      const height = 200;
      const padLeft = 40;
      const padRight = 20;
      const padTop = 20;
      const padBottom = 30;

      const innerWidth = width - padLeft - padRight;
      const innerHeight = height - padTop - padBottom;

      const maxSpent = Math.max(...dailyData.map(d => Number(d.spent || d.total_spent || 0)), 5.0);
      const points = [];

      dailyData.forEach((d, idx) => {
        const valSpent = Number(d.spent || d.total_spent || 0);
        const valTokens = Number(d.tokens || d.total_tokens || 0);
        const x = padLeft + (idx / Math.max(1, dailyData.length - 1)) * innerWidth;
        const y = padTop + innerHeight - (valSpent / maxSpent) * innerHeight;
        points.push({ x, y, data: { day: d.day, spent: valSpent, tokens: valTokens } });
      });

      // Grid lines
      for (let i = 0; i <= 3; i++) {
        const gy = padTop + (i / 3) * innerHeight;
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', padLeft);
        line.setAttribute('x2', width - padRight);
        line.setAttribute('y1', gy);
        line.setAttribute('y2', gy);
        line.setAttribute('class', 'chart-grid-line');
        grid.appendChild(line);

        const val = maxSpent * (1 - i / 3);
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', padLeft - 6);
        text.setAttribute('y', gy + 3);
        text.setAttribute('text-anchor', 'end');
        text.setAttribute('fill', '#64748B');
        text.setAttribute('font-size', '9');
        text.setAttribute('font-family', 'var(--font-mono)');
        text.textContent = `$${val.toFixed(0)}`;
        grid.appendChild(text);
      }

      if (points.length < 2) return;

      let lineD = `M ${points[0].x} ${points[0].y}`;
      for (let i = 1; i < points.length; i++) {
        lineD += ` L ${points[i].x} ${points[i].y}`;
      }

      const areaD = `${lineD} L ${points[points.length - 1].x} ${padTop + innerHeight} L ${points[0].x} ${padTop + innerHeight} Z`;

      document.getElementById('chartLinePath')?.setAttribute('d', lineD);
      document.getElementById('chartAreaPath')?.setAttribute('d', areaD);

      const tooltip = document.getElementById('chartTooltip');

      points.forEach(p => {
        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('cx', p.x);
        circle.setAttribute('cy', p.y);
        circle.setAttribute('r', '4');
        circle.setAttribute('class', 'chart-dot');

        circle.addEventListener('mouseenter', () => {
          if (!tooltip) return;
          tooltip.style.opacity = '1';
          tooltip.style.left = `${(p.x / width) * 100}%`;
          tooltip.style.top = `${(p.y / height) * 100}%`;
          tooltip.innerHTML = `<strong>${p.data.day}</strong><br/>Spend: <span style="color:#818CF8;">$${Number(p.data.spent).toFixed(2)}</span><br/>Tokens: ${formatNumber(p.data.tokens || 0)}`;
        });

        circle.addEventListener('mouseleave', () => {
          if (tooltip) tooltip.style.opacity = '0';
        });

        dots.appendChild(circle);
      });
    }

    function renderTopModels(models) {
      const container = document.getElementById('modelsRankList');
      if (!container) return;
      container.innerHTML = '';

      if (!models || models.length === 0) {
        container.innerHTML = `<div style="text-align:center; padding:30px; color:var(--text-tertiary); font-size:12px;">${currentLang === 'zh' ? '暂无模型调用数据' : 'No model calls recorded'}</div>`;
        return;
      }

      const maxSpent = Math.max(...models.map(m => Number(m.spent || m.total_spent || 0)), 1.0);

      models.forEach(m => {
        const spent = Number(m.spent || m.total_spent || 0);
        const tokens = Number(m.tokens || m.total_tokens || 0);
        const pct = maxSpent > 0 ? ((spent / maxSpent) * 100).toFixed(0) : 0;
        
        const item = document.createElement('div');
        item.className = 'model-rank-item';
        item.innerHTML = `
          <div class="m-top">
            <span class="m-name">
              <span class="provider-pill ${m.provider || 'anthropic'}">${m.provider || 'AI'}</span>
              ${m.model_name || 'unknown'}
            </span>
            <span class="m-cost">${formatCurrency(spent)}</span>
          </div>
          <div class="m-bar-bg">
            <div class="m-bar-fg" style="width: ${pct}%;"></div>
          </div>
          <div style="display:flex; justify-content:space-between; font-size:10px; font-family:var(--font-mono); color:var(--text-tertiary);">
            <span>${Number(m.requests || 0).toLocaleString()} calls</span>
            <span>${formatNumber(tokens)} tok</span>
          </div>
        `;
        container.appendChild(item);
      });
    }

    function renderRecentFeed(feed) {
      const previewBody = document.getElementById('previewFeedBody');
      const fullBody = document.getElementById('fullFeedBody');
      if (previewBody) previewBody.innerHTML = '';
      if (fullBody) fullBody.innerHTML = '';

      if (!feed || feed.length === 0) {
        const emptyRow = `<tr><td colspan="5" style="text-align:center; padding:24px; color:var(--text-tertiary);">${currentLang === 'zh' ? '等待调用流入...' : 'Waiting for incoming requests...'}</td></tr>`;
        if (previewBody) previewBody.innerHTML = emptyRow;
        if (fullBody) fullBody.innerHTML = emptyRow;
        return;
      }

      feed.slice(0, 10).forEach(item => {
        if (previewBody) previewBody.appendChild(createFeedRow(item));
      });

      feed.forEach(item => {
        if (fullBody) fullBody.appendChild(createFeedRow(item));
      });

      const countEl = document.getElementById('filteredStreamCount');
      if (countEl) countEl.textContent = feed.length;
    }

    function createFeedRow(item) {
      const tr = document.createElement('tr');
      const timeStr = item.started_at ? new Date(item.started_at * 1000).toLocaleTimeString() : '--:--:--';
      
      tr.innerHTML = `
        <td style="color:var(--text-tertiary);">${timeStr}</td>
        <td><span class="kpi-tag" style="background:rgba(255,255,255,0.06); font-family:var(--font-mono);">${item.project_name || 'General'}</span></td>
        <td>
          <div style="display:flex; align-items:center; gap:6px;">
            <span class="provider-pill ${item.provider || 'anthropic'}">${item.provider || 'AI'}</span>
            <span>${item.model_name || 'unknown'}</span>
          </div>
        </td>
        <td>
          <span class="token-flow-badge">
            ${Number(item.input_tokens || 0).toLocaleString()} <span class="arrow">→</span> ${Number(item.output_tokens || 0).toLocaleString()}
          </span>
        </td>
        <td style="font-weight:700; color:var(--text-primary);">${formatCurrency(item.cost_usd || 0)}</td>
      `;
      return tr;
    }

    function renderProjectsTable(projects) {
      const tbody = document.getElementById('projectsTableBody');
      if (!tbody) return;
      tbody.innerHTML = '';
      const badge = document.getElementById('navProjectCountBadge');
      if (badge) badge.textContent = projects ? projects.length : 0;

      if (!projects || projects.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:30px; color:var(--text-tertiary);">${currentLang === 'zh' ? '暂无项目归集数据' : 'No projects recorded'}</td></tr>`;
        return;
      }

      projects.forEach(p => {
        const tr = document.createElement('tr');
        const lastActive = p.last_active ? new Date(p.last_active * 1000).toLocaleDateString() : '--';
        const isSelected = selectedProjectFilter === p.project_name;

        tr.innerHTML = `
          <td>
            <div class="project-name-cell">
              <div class="proj-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
              </div>
              <span>${p.project_name}</span>
            </div>
          </td>
          <td style="font-family:var(--font-mono);">${Number(p.requests || 0).toLocaleString()}</td>
          <td style="font-family:var(--font-mono);">${formatNumber(p.tokens || 0)}</td>
          <td style="font-family:var(--font-mono); font-weight:700; color:var(--text-primary);">${formatCurrency(p.spent || 0)}</td>
          <td>
            <div style="display:flex; align-items:center; gap:8px;">
              <div style="width:60px; height:4px; background:rgba(255,255,255,0.06); border-radius:4px; overflow:hidden;">
                <div style="width:${p.cost_pct || 0}%; height:100%; background:#6366F1;"></div>
              </div>
              <span style="font-family:var(--font-mono); font-size:11px;">${p.cost_pct || 0}%</span>
            </div>
          </td>
          <td style="font-family:var(--font-mono); color:var(--text-tertiary);">${lastActive}</td>
          <td>
            <button class="filter-btn-pill ${isSelected ? 'active' : ''}" onclick="setProjectFilter('${isSelected ? 'all' : p.project_name}')">
              ${isSelected ? (currentLang === 'zh' ? '取消筛选' : 'Clear Filter') : (currentLang === 'zh' ? '仅看此项目' : 'Filter')}
            </button>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }

    function filterStreamTable() {
      const q = (document.getElementById('streamSearchInput')?.value || '').toLowerCase();
      const rows = document.querySelectorAll('#fullFeedBody tr');
      let visible = 0;
      rows.forEach(r => {
        const text = r.textContent.toLowerCase();
        if (!q || text.includes(q)) {
          r.style.display = '';
          visible++;
        } else {
          r.style.display = 'none';
        }
      });
      const countEl = document.getElementById('filteredStreamCount');
      if (countEl) countEl.textContent = visible;
    }

    function openSetupModal() { document.getElementById('setupModal')?.classList.add('open'); }
    function closeSetupModal() { document.getElementById('setupModal')?.classList.remove('open'); }
    function openBudgetModal() {
      const input = document.getElementById('budgetInput');
      if (input) input.value = userDailyBudget;
      document.getElementById('budgetModal')?.classList.add('open');
    }
    function closeBudgetModal() { document.getElementById('budgetModal')?.classList.remove('open'); }
    function setBudgetPreset(amt) { 
      const input = document.getElementById('budgetInput');
      if (input) input.value = amt; 
    }

    async function saveBudget() {
      const budget = parseFloat(document.getElementById('budgetInput')?.value) || 50.0;
      try {
        await fetch('/api/dashboard/budget', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ budget })
        });
        closeBudgetModal();
        fetchDashboardData();
      } catch (e) {
        console.error("Failed to save budget:", e);
      }
    }

    function copySnippet(text) {
      navigator.clipboard.writeText(text);
      alert(currentLang === 'zh' ? '已复制到剪贴板!' : 'Copied to clipboard!');
    }

    // Initialize
    applyI18n();
    fetchDashboardData();
    autoRefreshTimer = setInterval(fetchDashboardData, 3000);
  </script>
</body>
</html>
"""
