"""TokenGuard Interactive Visual Dashboard Router with Multi-Tool & Project-Level Cost Attribution."""
import json
import time
from datetime import datetime
from fastapi import APIRouter, Response, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Optional

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


@router.get("/api/dashboard/data")
async def get_dashboard_data(days: int = 7, project: Optional[str] = Query(None)):
    """API endpoint providing aggregated metrics for the visual dashboard with project attribution."""
    store = _get_store()
    if not store:
        return JSONResponse({"error": "Storage engine unavailable"}, status_code=500)

    selected_project = project if project and project != "all" else None

    stats = store.get_stats(days=days, project=selected_project)
    top_models = store.get_top_models(days=days, limit=10, project=selected_project)
    recent = store.get_live_feed(limit=50, project=selected_project)
    daily = store.get_daily_totals(days=days, project=selected_project)
    # Project attribution is strictly all-time from project inception
    projects_data = store.get_project_stats(days=None)

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

    # Calculate today's metrics strictly based on the user's computer local time (from 00:00:00 local time today)
    now = time.time()
    local_now = datetime.now()
    local_today_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start = local_today_midnight.timestamp()
    cutoff = now - days * 86400
    conn = store._get_conn()

    today_query = """SELECT COUNT(*) as requests,
                      COALESCE(SUM(cost_usd), 0) as spent,
                      COALESCE(SUM(input_tokens), 0) as in_tokens,
                      COALESCE(SUM(output_tokens), 0) as out_tokens,
                      COALESCE(SUM(input_tokens + output_tokens), 0) as tokens,
                      COALESCE(MAX(context_usage_pct), 0) as max_context_pct
               FROM usage_records WHERE started_at >= ?"""
    today_params = [today_start]
    if selected_project:
        today_query += " AND project_name = ?"
        today_params.append(selected_project)

    today_row = conn.execute(today_query, tuple(today_params)).fetchone()

    # Calculate velocity (Tokens in the last 5 minutes -> tokens per minute)
    five_min_ago = now - 300
    vel_query = """SELECT COALESCE(SUM(input_tokens + output_tokens), 0) as recent_tokens,
                      COUNT(*) as recent_reqs
               FROM usage_records WHERE started_at >= ?"""
    vel_params = [five_min_ago]
    if selected_project:
        vel_query += " AND project_name = ?"
        vel_params.append(selected_project)

    vel_row = conn.execute(vel_query, tuple(vel_params)).fetchone()

    # Tool / Provider breakdown with separate context stress
    provider_query = """SELECT provider,
                      COUNT(*) as requests,
                      COALESCE(SUM(input_tokens + output_tokens), 0) as tokens,
                      COALESCE(SUM(cost_usd), 0) as spent,
                      COALESCE(MAX(context_usage_pct), 0) as max_context_pct
               FROM usage_records WHERE started_at >= ?"""
    provider_params = [cutoff]
    if selected_project:
        provider_query += " AND project_name = ?"
        provider_params.append(selected_project)
    provider_query += " GROUP BY provider"

    provider_rows = conn.execute(provider_query, tuple(provider_params)).fetchall()

    latest_context_map = {}
    for p in ["anthropic", "gemini", "openai", "deepseek"]:
        l_query = """SELECT context_usage_pct, input_tokens, output_tokens, model_name 
                   FROM usage_records 
                   WHERE provider = ?"""
        l_params = [p]
        if selected_project:
            l_query += " AND project_name = ?"
            l_params.append(selected_project)
        l_query += " ORDER BY started_at DESC LIMIT 1"

        row = conn.execute(l_query, tuple(l_params)).fetchone()
        if row:
            latest_context_map[p] = {
                "current_pct": round(row["context_usage_pct"] or 0.0, 3),
                "latest_tokens": (row["input_tokens"] or 0) + (row["output_tokens"] or 0),
                "model_name": row["model_name"] or "",
            }
        else:
            latest_context_map[p] = {"current_pct": 0.0, "latest_tokens": 0, "model_name": ""}
    
    # Overall latest request to get real-time current context load
    latest_overall_query = """SELECT context_usage_pct FROM usage_records"""
    latest_overall_params = []
    if selected_project:
        latest_overall_query += " WHERE project_name = ?"
        latest_overall_params.append(selected_project)
    latest_overall_query += " ORDER BY started_at DESC LIMIT 1"

    latest_overall_row = conn.execute(latest_overall_query, tuple(latest_overall_params)).fetchone()
    current_overall_pct = round(latest_overall_row["context_usage_pct"] or 0.0, 4) if latest_overall_row else 0.0

    conn.close()

    provider_map = {r["provider"]: dict(r) for r in provider_rows}

    # Structured tool matrix with real-time live Context Stress for each tool
    tool_matrix = {
        "claude_code": {
            "name": "Claude Code",
            "provider": "anthropic",
            "tag": "Claude Code CLI",
            "tokens": provider_map.get("anthropic", {}).get("tokens", 0),
            "spent": round(provider_map.get("anthropic", {}).get("spent", 0.0), 4),
            "requests": provider_map.get("anthropic", {}).get("requests", 0),
            "context_stress_pct": round(latest_context_map.get("anthropic", {}).get("current_pct", 0.0) * 100, 1),
            "peak_context_pct": round(provider_map.get("anthropic", {}).get("max_context_pct", 0.0) * 100, 1),
            "color": "#8B5CF6",
            "optimize_action": "Run /compact or /clear in terminal",
        },
        "antigravity": {
            "name": "Antigravity",
            "provider": "gemini",
            "tag": "Antigravity (Gemini 3.7)",
            "tokens": provider_map.get("gemini", {}).get("tokens", 0),
            "spent": round(provider_map.get("gemini", {}).get("spent", 0.0), 4),
            "requests": provider_map.get("gemini", {}).get("requests", 0),
            "context_stress_pct": round(latest_context_map.get("gemini", {}).get("current_pct", 0.0) * 100, 1),
            "peak_context_pct": round(provider_map.get("gemini", {}).get("max_context_pct", 0.0) * 100, 1),
            "color": "#10B981",
            "optimize_action": "Start New Chat / Reset Context",
        },
        "chatgpt": {
            "name": "ChatGPT / Codex",
            "provider": "openai",
            "tag": "ChatGPT (GPT-5.6 Sol)",
            "tokens": provider_map.get("openai", {}).get("tokens", 0),
            "spent": round(provider_map.get("openai", {}).get("spent", 0.0), 4),
            "requests": provider_map.get("openai", {}).get("requests", 0),
            "context_stress_pct": round(latest_context_map.get("openai", {}).get("current_pct", 0.0) * 100, 1),
            "peak_context_pct": round(provider_map.get("openai", {}).get("max_context_pct", 0.0) * 100, 1),
            "color": "#38BDF8",
            "optimize_action": "Open New Thread (Cmd+N)",
        },
        "deepseek": {
            "name": "DeepSeek",
            "provider": "deepseek",
            "tag": "DeepSeek AI",
            "tokens": provider_map.get("deepseek", {}).get("tokens", 0),
            "spent": round(provider_map.get("deepseek", {}).get("spent", 0.0), 4),
            "requests": provider_map.get("deepseek", {}).get("requests", 0),
            "context_stress_pct": round(latest_context_map.get("deepseek", {}).get("current_pct", 0.0) * 100, 1),
            "peak_context_pct": round(provider_map.get("deepseek", {}).get("max_context_pct", 0.0) * 100, 1),
            "color": "#F59E0B",
            "optimize_action": "Clear History",
        },
    }

    recent_tokens = vel_row["recent_tokens"] if vel_row else 0
    tpm = int(recent_tokens / 5) if recent_tokens else 0

    return {
        "summary": stats,
        "daily_budget": daily_budget,
        "selected_project": selected_project or "all",
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
  <title>TokenGuard | Enterprise AI Cost & Context Intelligence</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-canvas: #06080E;
      --bg-surface: rgba(13, 19, 33, 0.72);
      --bg-surface-hover: rgba(20, 30, 52, 0.85);
      --bg-card: rgba(15, 23, 42, 0.65);
      --border-subtle: rgba(255, 255, 255, 0.08);
      --border-glow: rgba(56, 189, 248, 0.35);
      --text-main: #F8FAFC;
      --text-muted: #94A3B8;
      --accent-cyan: #06B6D4;
      --accent-blue: #38BDF8;
      --accent-emerald: #10B981;
      --accent-purple: #8B5CF6;
      --accent-amber: #F59E0B;
      --accent-rose: #F43F5E;
      --font-display: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background-color: var(--bg-canvas);
      background-image: 
        radial-gradient(circle at 50% -20%, rgba(56, 189, 248, 0.12) 0%, transparent 45%),
        radial-gradient(circle at 100% 100%, rgba(139, 92, 246, 0.08) 0%, transparent 40%),
        radial-gradient(circle at 0% 50%, rgba(16, 185, 129, 0.06) 0%, transparent 35%);
      color: var(--text-main);
      font-family: var(--font-display);
      min-height: 100vh;
      overflow-x: hidden;
      padding-bottom: 40px;
    }

    /* Top Navigation Header */
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 36px;
      border-bottom: 1px solid var(--border-subtle);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      background: rgba(6, 8, 14, 0.85);
      position: sticky;
      top: 0;
      z-index: 100;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .brand-logo {
      width: 38px;
      height: 38px;
      background: linear-gradient(135deg, var(--accent-cyan), var(--accent-purple));
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      font-weight: 800;
      color: white;
      box-shadow: 0 0 20px rgba(56, 189, 248, 0.35);
    }

    .brand-title {
      font-size: 20px;
      font-weight: 800;
      letter-spacing: -0.5px;
      background: linear-gradient(90deg, #FFFFFF, #E2E8F0);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .brand-badge {
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 1px;
      padding: 3px 8px;
      border-radius: 20px;
      background: rgba(56, 189, 248, 0.12);
      color: var(--accent-blue);
      border: 1px solid rgba(56, 189, 248, 0.25);
      font-weight: 700;
    }

    /* Segmented Tab Navigation Bar */
    .tab-nav {
      display: flex;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border-subtle);
      border-radius: 12px;
      padding: 4px;
      gap: 4px;
    }

    .tab-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      padding: 8px 18px;
      border-radius: 8px;
      font-family: var(--font-display);
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 8px;
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }

    .tab-btn:hover {
      color: var(--text-main);
      background: rgba(255, 255, 255, 0.06);
    }

    .tab-btn.active {
      background: linear-gradient(135deg, rgba(56, 189, 248, 0.2), rgba(139, 92, 246, 0.2));
      color: #FFFFFF;
      border: 1px solid rgba(56, 189, 248, 0.4);
      box-shadow: 0 4px 14px rgba(56, 189, 248, 0.15);
    }

    .tab-count-badge {
      background: rgba(56, 189, 248, 0.25);
      color: var(--accent-blue);
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 700;
      padding: 2px 7px;
      border-radius: 10px;
    }

    .nav-actions {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .project-select {
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid rgba(56, 189, 248, 0.3);
      color: var(--accent-blue);
      padding: 7px 14px;
      border-radius: 20px;
      font-family: var(--font-mono);
      font-size: 12px;
      font-weight: 700;
      cursor: pointer;
      outline: none;
      transition: all 0.2s;
    }

    .project-select:hover, .project-select:focus {
      background: rgba(56, 189, 248, 0.15);
      border-color: var(--accent-blue);
      box-shadow: 0 0 15px rgba(56, 189, 248, 0.25);
    }

    .project-select option {
      background: #0B1120;
      color: var(--text-main);
    }

    .status-pill {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 6px 14px;
      border-radius: 20px;
      background: rgba(16, 185, 129, 0.12);
      border: 1px solid rgba(16, 185, 129, 0.25);
      color: var(--accent-emerald);
      font-size: 12px;
      font-weight: 600;
    }

    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--accent-emerald);
      box-shadow: 0 0 10px var(--accent-emerald);
      animation: pulse 2s infinite;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(0.85); }
    }

    .lang-switcher {
      display: flex;
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid var(--border-subtle);
      border-radius: 20px;
      padding: 2px;
    }

    .lang-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      padding: 4px 10px;
      border-radius: 16px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s ease;
    }

    .lang-btn.active {
      background: rgba(56, 189, 248, 0.25);
      color: var(--accent-blue);
      box-shadow: 0 0 10px rgba(56, 189, 248, 0.3);
    }

    .btn {
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid var(--border-subtle);
      color: var(--text-main);
      padding: 7px 14px;
      border-radius: 8px;
      font-family: var(--font-display);
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s ease;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }

    .btn:hover {
      background: rgba(255, 255, 255, 0.12);
      border-color: rgba(255, 255, 255, 0.2);
      transform: translateY(-1px);
    }

    .btn-danger {
      color: #F87171;
      border-color: rgba(248, 113, 113, 0.3);
    }

    .btn-danger:hover {
      background: rgba(248, 113, 113, 0.15);
      border-color: rgba(248, 113, 113, 0.5);
    }

    .container {
      max-width: 1400px;
      margin: 24px auto;
      padding: 0 24px;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }

    .view-panel {
      display: flex;
      flex-direction: column;
      gap: 24px;
      animation: fadeIn 0.25s ease-out;
    }

    .view-panel.hidden {
      display: none !important;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(6px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .card {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: 18px;
      padding: 24px;
      backdrop-filter: blur(24px);
      -webkit-backdrop-filter: blur(24px);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08), 0 10px 30px rgba(0, 0, 0, 0.3);
      position: relative;
      overflow: hidden;
      transition: border-color 0.3s, transform 0.2s;
    }

    .card-title {
      font-size: 14px;
      font-weight: 700;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.8px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
    }

    /* Three Dial Gauges Row */
    .dials-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 20px;
    }

    .gauge-wrapper {
      position: relative;
      width: 180px;
      height: 180px;
      margin: 0 auto 10px auto;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .gauge-svg {
      transform: rotate(-90deg);
      overflow: visible;
    }

    .gauge-bg {
      fill: none;
      stroke: rgba(255, 255, 255, 0.05);
      stroke-width: 14;
    }

    .gauge-fill {
      fill: none;
      stroke-width: 14;
      stroke-linecap: round;
      transition: stroke-dashoffset 0.8s cubic-bezier(0.4, 0, 0.2, 1), stroke 0.4s;
    }

    .gauge-center-text {
      position: absolute;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
      pointer-events: none;
    }

    .gauge-value {
      font-size: 26px;
      font-weight: 800;
      color: var(--text-main);
      letter-spacing: -0.5px;
      font-family: var(--font-mono);
    }

    .gauge-label { font-size: 11px; color: var(--text-muted); margin-top: 2px; font-weight: 500; }

    .dial-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 14px;
      padding-top: 12px;
      border-top: 1px solid rgba(255, 255, 255, 0.05);
      font-size: 13px;
      color: var(--text-muted);
    }

    .dial-footer span.highlight {
      color: var(--text-main);
      font-weight: 600;
      font-family: var(--font-mono);
    }

    .budget-pill {
      background: rgba(56, 189, 248, 0.12);
      border: 1px dashed rgba(56, 189, 248, 0.4);
      color: var(--accent-blue);
      padding: 3px 8px;
      border-radius: 6px;
      font-weight: 700;
      font-family: var(--font-mono);
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      transition: all 0.2s ease;
    }

    .budget-pill:hover {
      background: rgba(56, 189, 248, 0.25);
      border-color: var(--accent-blue);
      transform: scale(1.04);
    }

    /* Tool Matrix Cards Row (Claude, Antigravity, ChatGPT) */
    .tool-matrix-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 20px;
    }

    .tool-card {
      padding: 22px;
      border-radius: 18px;
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      position: relative;
      overflow: hidden;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      cursor: pointer;
      display: flex;
      flex-direction: column;
      gap: 14px;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08), 0 10px 30px rgba(0, 0, 0, 0.3);
    }

    .tool-card:hover {
      transform: translateY(-3px);
      border-color: rgba(56, 189, 248, 0.4);
      background: var(--bg-surface-hover);
      box-shadow: 0 15px 35px rgba(0, 0, 0, 0.4), 0 0 20px rgba(56, 189, 248, 0.15);
    }

    .tool-card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .tool-badge-large {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 16px;
      font-weight: 700;
      color: var(--text-main);
    }

    .tool-icon {
      width: 32px;
      height: 32px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 16px;
    }

    .icon-claude { background: rgba(139, 92, 246, 0.2); border: 1px solid rgba(139, 92, 246, 0.4); }
    .icon-antigravity { background: rgba(16, 185, 129, 0.2); border: 1px solid rgba(16, 185, 129, 0.4); }
    .icon-chatgpt { background: rgba(56, 189, 248, 0.2); border: 1px solid rgba(56, 189, 248, 0.4); }

    .tool-status-tag {
      font-size: 10px;
      padding: 3px 8px;
      border-radius: 6px;
      font-weight: 700;
      font-family: var(--font-mono);
      letter-spacing: 0.5px;
    }

    .tag-active { background: rgba(16, 185, 129, 0.15); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.3); }

    .tool-cost-large {
      font-size: 32px;
      font-weight: 800;
      font-family: var(--font-mono);
      letter-spacing: -1px;
    }

    .tool-tokens-text {
      display: flex;
      justify-content: space-between;
      font-size: 13px;
      color: var(--text-muted);
      font-family: var(--font-mono);
    }

    .tool-context-wrapper {
      background: rgba(0, 0, 0, 0.25);
      border-radius: 12px;
      padding: 12px;
      border: 1px solid rgba(255, 255, 255, 0.05);
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .tool-context-header {
      display: flex;
      justify-content: space-between;
      font-size: 12px;
      font-weight: 600;
      color: var(--text-muted);
    }

    .tool-context-pct {
      font-family: var(--font-mono);
      font-weight: 700;
      color: var(--text-main);
    }

    .tool-context-bar-bg {
      height: 8px;
      background: rgba(255, 255, 255, 0.08);
      border-radius: 4px;
      overflow: hidden;
    }

    .tool-context-bar-fill {
      height: 100%;
      border-radius: 4px;
      transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1), background-color 0.4s;
    }

    .tool-opt-tip {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 11px;
      color: var(--text-muted);
      margin-top: 2px;
    }

    /* Multi-tool Context Stress List inside Dial 3 */
    .tool-stress-breakdown {
      display: flex;
      flex-direction: column;
      gap: 10px;
      margin-top: 14px;
      padding-top: 12px;
      border-top: 1px solid rgba(255, 255, 255, 0.05);
    }

    .tool-stress-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 12px;
    }

    .stress-badge {
      font-family: var(--font-mono);
      font-weight: 700;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 11px;
    }

    .stress-safe { background: rgba(16, 185, 129, 0.15); color: #34D399; }
    .stress-mod { background: rgba(245, 158, 11, 0.15); color: #FBBF24; }
    .stress-warn { background: rgba(244, 63, 94, 0.2); color: #FB7185; }

    /* Two Columns Section */
    .two-col-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }

    .model-list { display: flex; flex-direction: column; gap: 14px; margin-top: 8px; }

    .model-item {
      display: flex;
      flex-direction: column;
      gap: 6px;
      padding: 12px 14px;
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid rgba(255, 255, 255, 0.04);
      transition: background 0.2s;
    }

    .model-item:hover { background: rgba(255, 255, 255, 0.06); }
    .model-item-top { display: flex; justify-content: space-between; align-items: center; }

    .model-name { font-weight: 600; font-size: 14px; display: flex; align-items: center; gap: 8px; }
    .provider-pill { font-size: 10px; text-transform: uppercase; padding: 2px 7px; border-radius: 6px; font-weight: 600; font-family: var(--font-mono); }
    .pill-anthropic { background: rgba(139, 92, 246, 0.2); color: #C084FC; }
    .pill-gemini { background: rgba(16, 185, 129, 0.2); color: #6EE7B7; }
    .pill-openai { background: rgba(56, 189, 248, 0.2); color: #7DD3FC; }
    .pill-deepseek { background: rgba(245, 158, 11, 0.2); color: #FCD34D; }

    .model-cost { font-weight: 700; font-size: 15px; font-family: var(--font-mono); color: var(--accent-amber); }

    .model-bar-bg { height: 5px; background: rgba(255, 255, 255, 0.06); border-radius: 3px; overflow: hidden; }
    .model-bar-fill { height: 100%; border-radius: 3px; background: linear-gradient(90deg, var(--accent-blue), var(--accent-purple)); transition: width 0.5s ease; }

    /* Feed Table */
    .feed-header-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
    .filter-pills { display: flex; gap: 6px; }
    .filter-btn { background: rgba(255, 255, 255, 0.04); border: 1px solid var(--border-subtle); color: var(--text-muted); font-size: 11px; padding: 4px 10px; border-radius: 6px; cursor: pointer; font-family: var(--font-mono); transition: all 0.2s; }
    .filter-btn.active, .filter-btn:hover { background: rgba(56, 189, 248, 0.15); color: var(--accent-blue); border-color: rgba(56, 189, 248, 0.4); }

    .table-container { max-height: 380px; overflow-y: auto; }
    table { width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; }
    th { color: var(--text-muted); font-weight: 600; font-size: 11px; text-transform: uppercase; padding: 10px 12px; border-bottom: 1px solid rgba(255, 255, 255, 0.08); position: sticky; top: 0; background: #0B1120; z-index: 2; }
    td { padding: 10px 12px; border-bottom: 1px solid rgba(255, 255, 255, 0.04); font-family: var(--font-mono); }
    tr:hover td { background: rgba(255, 255, 255, 0.03); }

    /* ----------------------------------------------------
       PROJECTS VIEW (ENTERPRISE DEDICATED STUDIO)
       ---------------------------------------------------- */
    .kpi-ribbon {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
    }

    .kpi-card {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: 16px;
      padding: 18px 22px;
      display: flex;
      flex-direction: column;
      gap: 6px;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);
    }

    .kpi-label {
      font-size: 12px;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .kpi-value {
      font-size: 26px;
      font-weight: 800;
      font-family: var(--font-mono);
      color: var(--text-main);
    }

    .projects-toolbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid var(--border-subtle);
      border-radius: 14px;
      padding: 12px 18px;
    }

    .search-input-box {
      display: flex;
      align-items: center;
      gap: 8px;
      background: rgba(0, 0, 0, 0.3);
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
      padding: 6px 12px;
      flex: 1;
      max-width: 360px;
    }

    .search-input {
      background: transparent;
      border: none;
      color: white;
      font-family: var(--font-display);
      font-size: 13px;
      outline: none;
      width: 100%;
    }

    .projects-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 16px;
    }

    .project-card {
      padding: 20px;
      border-radius: 16px;
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
      cursor: pointer;
      display: flex;
      flex-direction: column;
      gap: 12px;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);
    }

    .project-card:hover {
      background: var(--bg-surface-hover);
      border-color: rgba(56, 189, 248, 0.4);
      transform: translateY(-3px);
      box-shadow: 0 12px 30px rgba(0, 0, 0, 0.4), 0 0 20px rgba(56, 189, 248, 0.12);
    }

    .project-card.active-project {
      border-color: var(--accent-blue);
      background: rgba(56, 189, 248, 0.1);
      box-shadow: 0 0 25px rgba(56, 189, 248, 0.2);
    }

    .project-card-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .project-name-badge {
      font-size: 15px;
      font-weight: 700;
      color: var(--text-main);
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .project-spent-text {
      font-size: 22px;
      font-weight: 800;
      font-family: var(--font-mono);
      color: var(--accent-amber);
    }

    .project-bar-bg {
      height: 6px;
      background: rgba(255, 255, 255, 0.06);
      border-radius: 3px;
      overflow: hidden;
    }

    .project-bar-fill {
      height: 100%;
      background: linear-gradient(90deg, var(--accent-blue), var(--accent-purple));
      border-radius: 3px;
      transition: width 0.6s ease;
    }

    .token-split-bar {
      display: flex;
      justify-content: space-between;
      font-size: 11px;
      color: var(--text-muted);
      font-family: var(--font-mono);
      padding: 6px 10px;
      background: rgba(0, 0, 0, 0.25);
      border-radius: 8px;
      border: 1px solid rgba(255, 255, 255, 0.03);
    }

    /* Modal for Editing Budget */
    .modal-overlay {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0, 0, 0, 0.75);
      backdrop-filter: blur(10px);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 1000;
    }

    .modal-overlay.open { display: flex; }

    .modal-card {
      background: #0B1120;
      border: 1px solid var(--border-glow);
      border-radius: 20px;
      padding: 28px;
      max-width: 420px;
      width: 90%;
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.7);
      display: flex;
      flex-direction: column;
      gap: 18px;
    }

    .modal-title { font-size: 18px; font-weight: 700; display: flex; align-items: center; gap: 8px; }
    .budget-input-wrapper { position: relative; display: flex; align-items: center; }
    .budget-input-symbol { position: absolute; left: 14px; font-size: 20px; font-weight: 700; color: var(--accent-blue); font-family: var(--font-mono); }
    .budget-input { width: 100%; background: rgba(255, 255, 255, 0.05); border: 1px solid var(--border-subtle); border-radius: 10px; padding: 12px 14px 12px 34px; font-size: 24px; font-weight: 700; font-family: var(--font-mono); color: white; outline: none; transition: border-color 0.2s; }
    .budget-input:focus { border-color: var(--accent-blue); box-shadow: 0 0 15px rgba(56, 189, 248, 0.25); }

    .preset-pills { display: flex; gap: 8px; flex-wrap: wrap; }
    .preset-btn { background: rgba(255, 255, 255, 0.05); border: 1px solid var(--border-subtle); color: var(--text-muted); padding: 6px 12px; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; font-family: var(--font-mono); transition: all 0.2s; }
    .preset-btn:hover { background: rgba(56, 189, 248, 0.15); color: var(--accent-blue); border-color: rgba(56, 189, 248, 0.4); }

    .modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 8px; }
    .btn-primary { background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple)); color: white; border: none; font-weight: 700; padding: 9px 20px; border-radius: 8px; cursor: pointer; }

    @media (max-width: 1100px) {
      .dials-grid, .tool-matrix-grid, .two-col-grid, .kpi-ribbon { grid-template-columns: 1fr; }
      header { flex-direction: column; gap: 14px; padding: 16px; }
    }
  </style>
</head>
<body>

  <!-- Top Header Navigation -->
  <header>
    <div class="brand">
      <div class="brand-logo">🛡️</div>
      <div>
        <div style="display: flex; align-items: center; gap: 8px;">
          <span class="brand-title">TokenGuard</span>
          <span class="brand-badge" data-i18n="brand_badge">AI ARCHITECTURE</span>
        </div>
      </div>
    </div>

    <!-- Center Tab Navigation -->
    <nav class="tab-nav">
      <button class="tab-btn active" id="tabOverview" onclick="switchTab('overview')">
        <span>⚡</span>
        <span data-i18n="tab_overview">Realtime Dials & Engine</span>
      </button>
      <button class="tab-btn" id="tabProjects" onclick="switchTab('projects')">
        <span>📁</span>
        <span data-i18n="tab_projects">Projects Attribution</span>
        <span class="tab-count-badge" id="tabProjectsCount">0</span>
      </button>
      <button class="tab-btn" id="tabStream" onclick="switchTab('stream')">
        <span>📡</span>
        <span data-i18n="tab_stream">Stream Trace</span>
      </button>
    </nav>

    <!-- Header Actions -->
    <div class="nav-actions">
      <div class="project-selector-wrapper">
        <select id="projectSelect" class="project-select" onchange="onProjectDropdownChange()">
          <option value="all">📁 All Projects (全部项目)</option>
        </select>
      </div>

      <div class="status-pill">
        <div class="status-dot"></div>
        <span data-i18n="proxy_active">Proxy Active (8001)</span>
      </div>

      <button class="btn" onclick="openBudgetModal()">
        <span data-i18n="btn_budget">🎯 Budget</span>
      </button>

      <button class="btn" onclick="fetchDashboardData()">
        <span data-i18n="btn_refresh">🔄 Refresh</span>
      </button>

      <div class="lang-switcher">
        <button class="lang-btn active" id="btnLangEn" onclick="switchLanguage('en')">EN</button>
        <button class="lang-btn" id="btnLangZh" onclick="switchLanguage('zh')">中文</button>
      </div>

      <button class="btn btn-danger" onclick="clearUsageData()">
        <span data-i18n="btn_clear">🗑️ Clear</span>
      </button>
    </div>
  </header>

  <div class="container">

    <!-- ======================================================== -->
    <!-- VIEW 1: REALTIME ENGINE & DIALS (主实时监控表盘)            -->
    <!-- ======================================================== -->
    <div id="viewOverview" class="view-panel">

      <!-- 三大 AI 编程软件监控矩阵 (Dedicated Tool Matrix Cards) -->
      <div>
        <div class="card-title" style="margin-bottom: 12px;">
          <span data-i18n="matrix_title">💻 AI 编程软件专属监控矩阵 (AI Tools Matrix)</span>
          <span style="font-size: 11px; color: var(--accent-blue);" data-i18n="matrix_subtitle">CONNECTED TOOLS & CONTEXT STRESS</span>
        </div>
        <div class="tool-matrix-grid">
          
          <!-- 1. Claude Code CLI -->
          <div class="tool-card" onclick="setFilter('anthropic')">
            <div class="tool-card-header">
              <div class="tool-badge-large">
                <div class="tool-icon icon-claude">🟣</div>
                <div>
                  <div>Claude Code</div>
                  <div style="font-size: 11px; color: var(--text-muted); font-weight: 500;">Anthropic / fcc-server</div>
                </div>
              </div>
              <span class="tool-status-tag tag-active" id="statusClaude">ACTIVE</span>
            </div>
            <div class="tool-cost-large" style="color: #C084FC;" id="costClaude">$0.00</div>
            <div class="tool-tokens-text">
              <span id="tokensClaude">0 Tokens</span>
              <span id="reqsClaude">0 Calls</span>
            </div>
            <div class="tool-context-wrapper">
              <div class="tool-context-header">
                <span>🧠 <span data-i18n="ctx_stress_label">Context Stress</span></span>
                <span class="tool-context-pct" id="ctxPctClaude">0%</span>
              </div>
              <div class="tool-context-bar-bg">
                <div class="tool-context-bar-fill" id="ctxBarClaude" style="width: 0%; background: #34D399;"></div>
              </div>
              <div class="tool-opt-tip">
                <span id="ctxTipClaude" style="color: var(--accent-emerald);">Optimal Safe</span>
                <span style="font-family: var(--font-mono); font-size: 10px;" id="optCmdClaude">/compact</span>
              </div>
            </div>
          </div>

          <!-- 2. Antigravity (Gemini 3.7 Flash) -->
          <div class="tool-card" onclick="setFilter('gemini')">
            <div class="tool-card-header">
              <div class="tool-badge-large">
                <div class="tool-icon icon-antigravity">🟢</div>
                <div>
                  <div>Antigravity</div>
                  <div style="font-size: 11px; color: var(--text-muted); font-weight: 500;">Gemini 3.7 Flash / Agent</div>
                </div>
              </div>
              <span class="tool-status-tag tag-active" id="statusAntigravity">ACTIVE</span>
            </div>
            <div class="tool-cost-large" style="color: #34D399;" id="costAntigravity">$0.00</div>
            <div class="tool-tokens-text">
              <span id="tokensAntigravity">0 Tokens</span>
              <span id="reqsAntigravity">0 Calls</span>
            </div>
            <div class="tool-context-wrapper">
              <div class="tool-context-header">
                <span>🧠 <span data-i18n="ctx_stress_label">Context Stress</span></span>
                <span class="tool-context-pct" id="ctxPctAntigravity">0%</span>
              </div>
              <div class="tool-context-bar-bg">
                <div class="tool-context-bar-fill" id="ctxBarAntigravity" style="width: 0%; background: #34D399;"></div>
              </div>
              <div class="tool-opt-tip">
                <span id="ctxTipAntigravity" style="color: var(--accent-emerald);">Optimal Safe</span>
                <span style="font-family: var(--font-mono); font-size: 10px;" id="optCmdAntigravity">1M Window</span>
              </div>
            </div>
          </div>

          <!-- 3. ChatGPT & OpenAI Codex -->
          <div class="tool-card" onclick="setFilter('openai')">
            <div class="tool-card-header">
              <div class="tool-badge-large">
                <div class="tool-icon icon-chatgpt">🔵</div>
                <div>
                  <div>ChatGPT / Codex</div>
                  <div style="font-size: 11px; color: var(--text-muted); font-weight: 500;">GPT-5.6 Sol / o1</div>
                </div>
              </div>
              <span class="tool-status-tag tag-active" id="statusChatGPT">ACTIVE</span>
            </div>
            <div class="tool-cost-large" style="color: #38BDF8;" id="costChatGPT">$0.00</div>
            <div class="tool-tokens-text">
              <span id="tokensChatGPT">0 Tokens</span>
              <span id="reqsChatGPT">0 Calls</span>
            </div>
            <div class="tool-context-wrapper">
              <div class="tool-context-header">
                <span>🧠 <span data-i18n="ctx_stress_label">Context Stress</span></span>
                <span class="tool-context-pct" id="ctxPctChatGPT">0%</span>
              </div>
              <div class="tool-context-bar-bg">
                <div class="tool-context-bar-fill" id="ctxBarChatGPT" style="width: 0%; background: #34D399;"></div>
              </div>
              <div class="tool-opt-tip">
                <span id="ctxTipChatGPT" style="color: var(--accent-emerald);">Optimal Safe</span>
                <span style="font-family: var(--font-mono); font-size: 10px;" id="optCmdChatGPT">Cmd+N</span>
              </div>
            </div>
          </div>

        </div>
      </div>

      <!-- 表盘区域 (Three Dial Gauges) -->
      <div class="dials-grid">
        
        <!-- 表盘 1: 今日消费与自定义预算表盘 -->
        <div class="card">
          <div class="card-title">
            <span data-i18n="gauge1_title">🎯 Daily Cost & Budget</span>
            <span id="budgetStatusBadge" style="font-size: 11px; color: var(--accent-cyan);">ON TRACK</span>
          </div>
          <div class="gauge-wrapper">
            <svg class="gauge-svg" width="180" height="180" viewBox="0 0 180 180">
              <circle class="gauge-bg" cx="90" cy="90" r="75"></circle>
              <circle id="costGaugeCircle" class="gauge-fill" cx="90" cy="90" r="75"
                stroke="url(#costGradient)"
                stroke-dasharray="471.2"
                stroke-dashoffset="471.2"></circle>
              <defs>
                <linearGradient id="costGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#38BDF8" />
                  <stop offset="100%" stop-color="#8B5CF6" />
                </linearGradient>
                <linearGradient id="costWarningGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#F59E0B" />
                  <stop offset="100%" stop-color="#F97316" />
                </linearGradient>
                <linearGradient id="costDangerGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#F43F5E" />
                  <stop offset="100%" stop-color="#E11D48" />
                </linearGradient>
              </defs>
            </svg>
            <div class="gauge-center-text">
              <span class="gauge-value" id="gaugeTodayCost">$0.00</span>
              <span class="gauge-label" id="gaugeTodayTokens">0 Tokens</span>
            </div>
          </div>
          <div class="dial-footer">
            <span><span data-i18n="gauge1_calls">Today Calls:</span> <span class="highlight" id="gaugeTodayReqs">0</span></span>
            <span><span data-i18n="gauge1_limit">Daily Budget:</span> 
              <span class="budget-pill" onclick="openBudgetModal()" title="Click to edit daily budget">
                $<span id="gaugeDailyBudget">50.00</span> ✏️
              </span>
            </span>
          </div>
        </div>

        <!-- 表盘 2: 实时速率仪表 -->
        <div class="card">
          <div class="card-title">
            <span data-i18n="gauge2_title">⚡ Real-time Token Velocity</span>
            <span style="font-size: 11px; color: var(--accent-emerald);">LIVE VELOCITY</span>
          </div>
          <div class="gauge-wrapper">
            <svg class="gauge-svg" width="180" height="180" viewBox="0 0 180 180">
              <circle class="gauge-bg" cx="90" cy="90" r="75"></circle>
              <circle id="velGaugeCircle" class="gauge-fill" cx="90" cy="90" r="75"
                stroke="url(#velGradient)"
                stroke-dasharray="471.2"
                stroke-dashoffset="471.2"></circle>
              <defs>
                <linearGradient id="velGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#10B981" />
                  <stop offset="100%" stop-color="#06B6D4" />
                </linearGradient>
              </defs>
            </svg>
            <div class="gauge-center-text">
              <span class="gauge-value" id="gaugeVelocity">0</span>
              <span class="gauge-label" data-i18n="gauge2_unit">Tokens / min</span>
            </div>
          </div>
          <div class="dial-footer">
            <span><span data-i18n="gauge2_status">Routing:</span> <span class="highlight" style="color: var(--accent-emerald);" data-i18n="gauge2_status_val">Zero-Lag</span></span>
            <span><span data-i18n="gauge2_latency">Avg Latency:</span> <span class="highlight">~1.2 ms</span></span>
          </div>
        </div>

        <!-- 表盘 3: 上下文负荷指示表盘 (带各工具明细分布) -->
        <div class="card">
          <div class="card-title">
            <span data-i18n="gauge3_title">🧠 Context Stress & Window</span>
            <span style="font-size: 11px; color: var(--accent-emerald);" data-i18n="gauge3_realtime">LIVE LOAD</span>
          </div>
          <div class="gauge-wrapper">
            <svg class="gauge-svg" width="180" height="180" viewBox="0 0 180 180">
              <circle class="gauge-bg" cx="90" cy="90" r="75"></circle>
              <circle id="contextGaugeCircle" class="gauge-fill" cx="90" cy="90" r="75"
                stroke="url(#contextGradient)"
                stroke-dasharray="471.2"
                stroke-dashoffset="471.2"></circle>
              <defs>
                <linearGradient id="contextGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#10B981" />
                  <stop offset="70%" stop-color="#F59E0B" />
                  <stop offset="100%" stop-color="#F43F5E" />
                </linearGradient>
              </defs>
            </svg>
            <div class="gauge-center-text">
              <span class="gauge-value" id="gaugeContextPct">0%</span>
              <span class="gauge-label" data-i18n="gauge3_unit">Current Window Load</span>
            </div>
          </div>
          
          <!-- 各工具独立负荷分布列表 -->
          <div class="tool-stress-breakdown">
            <div class="tool-stress-row">
              <span>🟣 Claude Code</span>
              <span class="stress-badge" id="badgeStressClaude">0%</span>
            </div>
            <div class="tool-stress-row">
              <span>🟢 Antigravity (Gemini)</span>
              <span class="stress-badge" id="badgeStressAntigravity">0%</span>
            </div>
            <div class="tool-stress-row">
              <span>🔵 ChatGPT / Codex</span>
              <span class="stress-badge" id="badgeStressChatGPT">0%</span>
            </div>
          </div>

          <div class="dial-footer" style="margin-top: 10px; padding-top: 10px;">
            <span><span data-i18n="gauge3_health">Health:</span> <span class="highlight" id="contextHealthText" style="color: var(--accent-emerald);">Optimal Safe</span></span>
            <span><span data-i18n="gauge3_peak">Day Peak:</span> <span class="highlight" id="gaugePeakContext">0%</span></span>
          </div>
        </div>

      </div>

      <!-- 双列视图: 模型分布 + 实时请求流水 -->
      <div class="two-col-grid">
        
        <!-- 活跃模型与花费榜单 -->
        <div class="card">
          <div class="card-title">
            <span data-i18n="models_title">🏆 热门模型调用与花费分布</span>
            <span style="font-size: 11px;">MODELS BY SPENT</span>
          </div>
          <div class="model-list" id="modelList">
            <div style="color: var(--text-muted); font-size: 13px; text-align: center; padding: 20px;" data-i18n="models_empty">No model usage recorded yet</div>
          </div>
        </div>

        <!-- 实时调用流水明细 -->
        <div class="card">
          <div class="feed-header-bar">
            <div class="card-title" style="margin-bottom: 0;">
              <span data-i18n="feed_title">📡 实时请求拦截明细流</span>
              <span style="font-size: 11px; color: var(--accent-emerald);">REALTIME</span>
            </div>
            <div class="filter-pills">
              <button class="filter-btn active" id="filterAll" onclick="setFilter('all')">All</button>
              <button class="filter-btn" id="filterAnthropic" onclick="setFilter('anthropic')">Claude</button>
              <button class="filter-btn" id="filterGemini" onclick="setFilter('gemini')">Antigravity</button>
              <button class="filter-btn" id="filterOpenAI" onclick="setFilter('openai')">ChatGPT</button>
            </div>
          </div>
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th data-i18n="th_time">Time</th>
                  <th data-i18n="th_project">Project</th>
                  <th data-i18n="th_model">Model / Tool</th>
                  <th data-i18n="th_tokens">Tokens (In → Out)</th>
                  <th data-i18n="th_cost">Cost</th>
                </tr>
              </thead>
              <tbody id="feedTableBody">
                <tr>
                  <td colspan="5" style="text-align: center; color: var(--text-muted); padding: 30px;" data-i18n="feed_waiting">Waiting for AI requests...</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

      </div>

    </div>

    <!-- ======================================================== -->
    <!-- VIEW 2: PROJECTS & WORKSPACES ATTRIBUTION (专属企业级视窗)    -->
    <!-- ======================================================== -->
    <div id="viewProjects" class="view-panel hidden">
      
      <!-- Executive KPI Ribbon -->
      <div class="kpi-ribbon">
        <div class="kpi-card">
          <div class="kpi-label" data-i18n="kpi_projects_count">Active Projects</div>
          <div class="kpi-value" id="kpiProjectsCount">0</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label" data-i18n="kpi_lifetime_spent">All-Time Spend</div>
          <div class="kpi-value" style="color: var(--accent-amber);" id="kpiLifetimeSpent">$0.00</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label" data-i18n="kpi_lifetime_tokens">All-Time Tokens</div>
          <div class="kpi-value" style="color: var(--accent-blue);" id="kpiLifetimeTokens">0</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label" data-i18n="kpi_top_project">Top Cost Center</div>
          <div class="kpi-value" style="font-size: 18px; color: var(--accent-purple); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" id="kpiTopProject">-</div>
        </div>
      </div>

      <!-- Projects Toolbar (Search & Sort) -->
      <div class="projects-toolbar">
        <div class="search-input-box">
          <span>🔍</span>
          <input type="text" id="projectSearchInput" class="search-input" placeholder="Search Git repositories / workspaces..." oninput="filterProjectsGrid()">
        </div>
        <div style="font-size: 12px; color: var(--text-muted); font-family: var(--font-mono);" data-i18n="projects_desc">
          Calculated from project inception · Full lifecycle token expenditure
        </div>
      </div>

      <!-- Projects Cards Grid -->
      <div class="projects-grid" id="projectsStudioGrid">
        <div style="color: var(--text-muted); font-size: 13px; padding: 20px;">Loading projects...</div>
      </div>

    </div>

    <!-- ======================================================== -->
    <!-- VIEW 3: FULL STREAM TRACE LOGS (全量审计流)                 -->
    <!-- ======================================================== -->
    <div id="viewStream" class="view-panel hidden">
      <div class="card">
        <div class="feed-header-bar">
          <div class="card-title" style="margin-bottom: 0;">
            <span data-i18n="stream_full_title">📡 Full Intercepted API Request Logs</span>
            <span style="font-size: 11px; color: var(--accent-emerald);">LIVE CAPTURE</span>
          </div>
          <div class="filter-pills">
            <button class="filter-btn active" id="streamFilterAll" onclick="setStreamFilter('all')">All</button>
            <button class="filter-btn" id="streamFilterAnthropic" onclick="setStreamFilter('anthropic')">Anthropic</button>
            <button class="filter-btn" id="streamFilterGemini" onclick="setStreamFilter('gemini')">Gemini</button>
            <button class="filter-btn" id="streamFilterOpenAI" onclick="setStreamFilter('openai')">OpenAI</button>
          </div>
        </div>
        <div class="table-container" style="max-height: 650px;">
          <table>
            <thead>
              <tr>
                <th data-i18n="th_time">Time</th>
                <th data-i18n="th_project">Project</th>
                <th data-i18n="th_model">Model / Tool</th>
                <th data-i18n="th_tokens">Tokens (In → Out)</th>
                <th data-i18n="th_cost">Cost</th>
              </tr>
            </thead>
            <tbody id="fullStreamTableBody">
              <tr>
                <td colspan="5" style="text-align: center; color: var(--text-muted); padding: 40px;">Waiting for AI requests...</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

  </div>

  <!-- 自定义预算弹窗 -->
  <div class="modal-overlay" id="budgetModal">
    <div class="modal-card">
      <div class="modal-title">
        <span>🎯</span>
        <span data-i18n="modal_budget_title">Set Daily Spending Budget</span>
      </div>
      <p style="font-size: 13px; color: var(--text-muted);" data-i18n="modal_budget_desc">
        Configure your daily target AI spending threshold. The dial will adjust and warn when approaching your limit.
      </p>
      <div class="budget-input-wrapper">
        <span class="budget-input-symbol">$</span>
        <input type="number" id="budgetInput" class="budget-input" min="1" step="5" value="50">
      </div>
      <div class="preset-pills">
        <button class="preset-btn" onclick="setBudgetPreset(10)">$10</button>
        <button class="preset-btn" onclick="setBudgetPreset(25)">$25</button>
        <button class="preset-btn" onclick="setBudgetPreset(50)">$50</button>
        <button class="preset-btn" onclick="setBudgetPreset(100)">$100</button>
        <button class="preset-btn" onclick="setBudgetPreset(200)">$200</button>
        <button class="preset-btn" onclick="setBudgetPreset(500)">$500</button>
      </div>
      <div class="modal-actions">
        <button class="btn" onclick="closeBudgetModal()" data-i18n="modal_cancel">Cancel</button>
        <button class="btn-primary" onclick="saveBudget()" data-i18n="modal_save">Save Budget</button>
      </div>
    </div>
  </div>

  <script>
    let currentFilter = 'all';
    let streamFilter = 'all';
    let currentLang = localStorage.getItem('tg_lang') || 'zh';
    let activeTab = 'overview';
    let userDailyBudget = 50.0;
    let globalProjectsCache = [];

    const I18N = {
      en: {
        brand_badge: "AI Architecture",
        proxy_active: "Proxy Active (8001)",
        tab_overview: "Realtime Dials & Engine",
        tab_projects: "Projects Attribution",
        tab_stream: "Stream Trace",
        btn_budget: "🎯 Budget",
        btn_refresh: "🔄 Refresh",
        btn_clear: "🗑️ Clear",
        kpi_projects_count: "Active Projects",
        kpi_lifetime_spent: "All-Time Spend",
        kpi_lifetime_tokens: "All-Time Tokens",
        kpi_top_project: "Top Cost Center",
        projects_desc: "Calculated from project inception · Full lifecycle token expenditure",
        projects_title: "📁 Projects & Workspaces Cost Attribution",
        matrix_title: "💻 AI Coding Tools Multi-Dashboard",
        matrix_subtitle: "CONNECTED TOOLS & CONTEXT STRESS",
        ctx_stress_label: "Context Stress",
        gauge1_title: "🎯 Daily Cost & Budget",
        gauge1_calls: "Today Calls:",
        gauge1_limit: "Daily Budget:",
        gauge2_title: "⚡ Real-time Token Velocity",
        gauge2_unit: "Tokens / min",
        gauge2_status: "Routing:",
        gauge2_status_val: "Zero-Lag",
        gauge2_latency: "Avg Latency:",
        gauge3_title: "🧠 Context Stress & Window",
        gauge3_unit: "Current Window Load",
        gauge3_realtime: "LIVE LOAD",
        gauge3_health: "Health:",
        gauge3_health_safe: "Optimal Safe",
        gauge3_health_moderate: "Moderate",
        gauge3_health_warn: "⚠️ Overload Warn",
        gauge3_peak: "Day Peak:",
        models_title: "🏆 Top Models & Cost Share",
        models_empty: "No model usage recorded yet",
        models_calls: "calls",
        feed_title: "📡 Live Intercept Stream",
        stream_full_title: "📡 Full Intercepted API Request Logs",
        th_time: "Time",
        th_project: "Project",
        th_model: "Model / Tool",
        th_tokens: "Tokens (In → Out)",
        th_cost: "Cost",
        feed_waiting: "Waiting for AI requests...",
        confirm_clear: "Are you sure you want to clear all TokenGuard records?",
        modal_budget_title: "Set Daily Spending Budget",
        modal_budget_desc: "Configure your daily target AI spending threshold. The dial will adjust and warn when approaching your limit.",
        modal_cancel: "Cancel",
        modal_save: "Save Budget",
        budget_on_track: "ON TRACK",
        budget_near_limit: "⚠️ NEAR LIMIT",
        budget_over: "🚨 OVER BUDGET",
        status_safe: "Optimal Safe",
        status_mod: "Moderate Load",
        status_warn: "⚠️ High Load (/compact)"
      },
      zh: {
        brand_badge: "AI 架构网关",
        proxy_active: "代理运行中 (8001)",
        tab_overview: "实时监控与表盘",
        tab_projects: "项目成本归集",
        tab_stream: "全量审计流",
        btn_budget: "🎯 设置预算",
        btn_refresh: "🔄 刷新数据",
        btn_clear: "🗑️ 清空记录",
        kpi_projects_count: "活跃研发项目",
        kpi_lifetime_spent: "全生命周期总花费",
        kpi_lifetime_tokens: "历史累计 Token",
        kpi_top_project: "第一成本中心",
        projects_desc: "从项目诞生第一天起全部累计计算 · 全生命周期输入输出成本",
        projects_title: "📁 研发项目与代码仓库成本归集 (Projects Attribution)",
        matrix_title: "💻 AI 编程软件专属监控矩阵",
        matrix_subtitle: "已连接客户端与独立负荷",
        ctx_stress_label: "上下文负荷",
        gauge1_title: "🎯 今日消费与自定义预算表盘",
        gauge1_calls: "今日调用:",
        gauge1_limit: "每日预算:",
        gauge2_title: "⚡ 实时 Token 吞吐速率",
        gauge2_unit: "Tokens / 分钟",
        gauge2_status: "当前状态:",
        gauge2_status_val: "活跃无感",
        gauge2_latency: "平均时延:",
        gauge3_title: "🧠 上下文负荷与窗口状态",
        gauge3_unit: "实时当前窗口负荷",
        gauge3_realtime: "实时负载",
        gauge3_health: "健康状态:",
        gauge3_health_safe: "极佳安全",
        gauge3_health_moderate: "适度使用",
        gauge3_health_warn: "⚠️ 警戒超载",
        gauge3_peak: "今日峰值:",
        models_title: "🏆 热门模型调用与花费分布",
        models_empty: "暂无模型调用数据",
        models_calls: "次调用",
        feed_title: "📡 实时请求拦截明细流",
        stream_full_title: "📡 全量请求拦截审计流",
        th_time: "时间",
        th_project: "所属项目",
        th_model: "模型 / 工具",
        th_tokens: "Token (入 → 出)",
        th_cost: "花费",
        feed_waiting: "等待 AI 工具发起请求...",
        confirm_clear: "确定要清空所有 TokenGuard 历史记录吗？",
        modal_budget_title: "设置每日消费预算 (Daily Budget)",
        modal_budget_desc: "设置您期望的每日最高 AI 调用金额。表盘会自动计算当前完成比例，并在接近或超出时提供视觉预警。",
        modal_cancel: "取消",
        modal_save: "保存预算",
        budget_on_track: "运行平稳",
        budget_near_limit: "⚠️ 接近限额",
        budget_over: "🚨 超出预算",
        status_safe: "极佳安全",
        status_mod: "适度使用",
        status_warn: "⚠️ 负荷偏高 (/compact)"
      }
    };

    function switchTab(tab) {
      activeTab = tab;
      document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
      document.querySelectorAll('.view-panel').forEach(p => p.classList.add('hidden'));

      if (tab === 'overview') {
        document.getElementById('tabOverview').classList.add('active');
        document.getElementById('viewOverview').classList.remove('hidden');
      } else if (tab === 'projects') {
        document.getElementById('tabProjects').classList.add('active');
        document.getElementById('viewProjects').classList.remove('hidden');
      } else if (tab === 'stream') {
        document.getElementById('tabStream').classList.add('active');
        document.getElementById('viewStream').classList.remove('hidden');
      }
    }

    function switchLanguage(lang) {
      currentLang = lang;
      localStorage.setItem('tg_lang', lang);
      document.getElementById('btnLangEn').classList.toggle('active', lang === 'en');
      document.getElementById('btnLangZh').classList.toggle('active', lang === 'zh');
      applyTranslations();
      fetchDashboardData();
    }

    function applyTranslations() {
      const t = I18N[currentLang];
      document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (t[key]) {
          el.textContent = t[key];
        }
      });
    }

    function openBudgetModal() {
      document.getElementById('budgetInput').value = userDailyBudget;
      document.getElementById('budgetModal').classList.add('open');
    }

    function closeBudgetModal() {
      document.getElementById('budgetModal').classList.remove('open');
    }

    function setBudgetPreset(val) {
      document.getElementById('budgetInput').value = val;
    }

    async function saveBudget() {
      const val = parseFloat(document.getElementById('budgetInput').value);
      if (val > 0) {
        userDailyBudget = val;
        try {
          await fetch('/api/dashboard/budget', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ budget: val })
          });
        } catch (e) {
          console.error('Failed to persist budget:', e);
        }
        closeBudgetModal();
        fetchDashboardData();
      }
    }

    async function clearUsageData() {
      const t = I18N[currentLang];
      if (confirm(t.confirm_clear)) {
        try {
          await fetch('/api/dashboard/clear', { method: 'POST' });
          fetchDashboardData();
        } catch (e) {
          console.error('Clear failed:', e);
        }
      }
    }

    function setGaugeProgress(circleId, percent) {
      const circle = document.getElementById(circleId);
      if (!circle) return;
      const radius = circle.r.baseVal.value;
      const circumference = 2 * Math.PI * radius;
      const offset = circumference - (Math.min(100, Math.max(0, percent)) / 100) * circumference;
      circle.style.strokeDasharray = `${circumference}`;
      circle.style.strokeDashoffset = `${offset}`;
    }

    function updateToolContextBar(barId, pctId, tipId, badgeId, pct, t) {
      const bar = document.getElementById(barId);
      const pctEl = document.getElementById(pctId);
      const tip = document.getElementById(tipId);
      const badge = document.getElementById(badgeId);

      const val = Math.min(100, Math.max(0, pct));
      if (pctEl) pctEl.textContent = `${val.toFixed(1)}%`;
      if (bar) bar.style.width = `${Math.max(4, val)}%`;

      let col = '#10B981';
      let tipText = t.status_safe;
      let badgeClass = 'stress-badge stress-safe';

      if (val > 80) {
        col = '#F43F5E';
        tipText = t.status_warn;
        badgeClass = 'stress-badge stress-warn';
      } else if (val > 50) {
        col = '#F59E0B';
        tipText = t.status_mod;
        badgeClass = 'stress-badge stress-mod';
      }

      if (bar) bar.style.backgroundColor = col;
      if (tip) {
        tip.textContent = tipText;
        tip.style.color = col;
      }
      if (badge) {
        badge.textContent = `${val.toFixed(1)}%`;
        badge.className = badgeClass;
      }
    }

    function selectProjectCard(projName) {
      const projSelect = document.getElementById('projectSelect');
      projSelect.value = projName;
      fetchDashboardData();
    }

    function onProjectDropdownChange() {
      fetchDashboardData();
    }

    function setFilter(f) {
      currentFilter = f;
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      if (f === 'all') document.getElementById('filterAll').classList.add('active');
      if (f === 'anthropic') document.getElementById('filterAnthropic').classList.add('active');
      if (f === 'gemini') document.getElementById('filterGemini').classList.add('active');
      if (f === 'openai') document.getElementById('filterOpenAI').classList.add('active');
      fetchDashboardData();
    }

    function setStreamFilter(f) {
      streamFilter = f;
      document.querySelectorAll('#viewStream .filter-btn').forEach(b => b.classList.remove('active'));
      if (f === 'all') document.getElementById('streamFilterAll').classList.add('active');
      if (f === 'anthropic') document.getElementById('streamFilterAnthropic').classList.add('active');
      if (f === 'gemini') document.getElementById('streamFilterGemini').classList.add('active');
      if (f === 'openai') document.getElementById('streamFilterOpenAI').classList.add('active');
      renderFullStream(window._lastRecentRequests || []);
    }

    function filterProjectsGrid() {
      const q = (document.getElementById('projectSearchInput').value || '').trim().toLowerCase();
      const currentSelected = document.getElementById('projectSelect').value || 'all';
      const grid = document.getElementById('projectsStudioGrid');
      
      const filtered = globalProjectsCache.filter(p => p.project_name.toLowerCase().includes(q));
      if (filtered.length === 0) {
        grid.innerHTML = `<div style="color: var(--text-muted); font-size: 13px; padding: 20px;">No projects matching "${q}"</div>`;
        return;
      }

      grid.innerHTML = filtered.map(p => {
        const isActive = currentSelected === p.project_name ? 'active-project' : '';
        const inTok = (p.input_tokens || 0).toLocaleString();
        const outTok = (p.output_tokens || 0).toLocaleString();
        const totalTok = (p.tokens || 0).toLocaleString();
        return `
          <div class="project-card ${isActive}" onclick="selectProjectCard('${p.project_name}')">
            <div class="project-card-top">
              <div class="project-name-badge">
                <span>📁</span>
                <span>${p.project_name}</span>
              </div>
              <div class="project-spent-text">$${p.spent.toFixed(2)}</div>
            </div>
            <div class="project-bar-bg">
              <div class="project-bar-fill" style="width: ${Math.max(6, p.cost_pct)}%;"></div>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 12px; color: var(--text-muted); font-family: var(--font-mono);">
              <span style="color: var(--accent-blue); font-weight: 700;">${p.cost_pct}% Lifetime Share</span>
              <span>${p.requests.toLocaleString()} calls</span>
            </div>
            <div class="token-split-bar">
              <span>Prompt: ${inTok}</span>
              <span>Completion: ${outTok}</span>
            </div>
          </div>
        `;
      }).join('');
    }

    function renderFullStream(requests) {
      const tbody = document.getElementById('fullStreamTableBody');
      let filtered = requests;
      if (streamFilter !== 'all') {
        filtered = requests.filter(r => (r.provider || '').toLowerCase() === streamFilter);
      }

      if (!filtered || filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 40px;">No requests in stream</td></tr>`;
        return;
      }

      tbody.innerHTML = filtered.map(r => {
        const d = new Date(r.started_at * 1000);
        const timeStr = d.toTimeString().split(' ')[0];
        const proj = r.project_name || 'General';
        const costStr = (r.cost_usd || 0).toFixed(4);
        const inTokens = (r.input_tokens || 0).toLocaleString();
        const outTokens = (r.output_tokens || 0).toLocaleString();
        return `
          <tr>
            <td style="color: var(--text-muted);">${timeStr}</td>
            <td><span style="background: rgba(139, 92, 246, 0.15); color: #C084FC; padding: 2px 7px; border-radius: 6px; font-size: 11px;">📁 ${proj}</span></td>
            <td style="font-weight: 600;">${r.model_name || '?'}</td>
            <td>${inTokens} → ${outTokens}</td>
            <td style="color: var(--accent-amber); font-weight: 700;">$${costStr}</td>
          </tr>
        `;
      }).join('');
    }

    async function fetchDashboardData() {
      const projSelect = document.getElementById('projectSelect');
      const selectedProj = projSelect ? projSelect.value : 'all';
      const url = `/api/dashboard/data?project=${encodeURIComponent(selectedProj)}`;

      try {
        const res = await fetch(url);
        if (!res.ok) return;
        const data = await res.json();
        if (data.daily_budget) {
          userDailyBudget = data.daily_budget;
        }
        renderDashboard(data);
      } catch (err) {
        console.error('Fetch error:', err);
      }
    }

    function renderDashboard(data) {
      const { summary, today, velocity_tpm, tool_matrix, top_models, recent_requests, projects } = data;
      const t = I18N[currentLang];
      window._lastRecentRequests = recent_requests || [];

      // 0. 项目数据缓存与渲染
      const projSelect = document.getElementById('projectSelect');
      const currentSelected = data.selected_project || 'all';
      
      if (projects && projects.length > 0) {
        globalProjectsCache = projects;
        document.getElementById('tabProjectsCount').textContent = projects.length;
        document.getElementById('kpiProjectsCount').textContent = `${projects.length} Repos`;
        
        const totalLifetimeSpent = projects.reduce((acc, p) => acc + (p.spent || 0), 0);
        const totalLifetimeTokens = projects.reduce((acc, p) => acc + (p.tokens || 0), 0);
        
        document.getElementById('kpiLifetimeSpent').textContent = `$${totalLifetimeSpent.toFixed(2)}`;
        document.getElementById('kpiLifetimeTokens').textContent = totalLifetimeTokens.toLocaleString();
        if (projects[0]) {
          document.getElementById('kpiTopProject').textContent = `${projects[0].project_name} ($${projects[0].spent.toFixed(2)})`;
        }

        let selectHtml = `<option value="all" ${currentSelected === 'all' ? 'selected' : ''}>📁 All Projects (全部项目)</option>`;
        projects.forEach(p => {
          selectHtml += `<option value="${p.project_name}" ${currentSelected === p.project_name ? 'selected' : ''}>📁 ${p.project_name} ($${p.spent.toFixed(2)})</option>`;
        });
        projSelect.innerHTML = selectHtml;

        filterProjectsGrid();
      }

      // 1. 更新三大工具卡片及其各自的 Context Stress
      if (tool_matrix) {
        const c = tool_matrix.claude_code;
        document.getElementById('costClaude').textContent = `$${c.spent.toFixed(2)}`;
        document.getElementById('tokensClaude').textContent = `${c.tokens.toLocaleString()} Tokens`;
        document.getElementById('reqsClaude').textContent = `${c.requests} Calls`;
        updateToolContextBar('ctxBarClaude', 'ctxPctClaude', 'ctxTipClaude', 'badgeStressClaude', c.context_stress_pct || 0, t);

        const a = tool_matrix.antigravity;
        document.getElementById('costAntigravity').textContent = `$${a.spent.toFixed(2)}`;
        document.getElementById('tokensAntigravity').textContent = `${a.tokens.toLocaleString()} Tokens`;
        document.getElementById('reqsAntigravity').textContent = `${a.requests} Calls`;
        updateToolContextBar('ctxBarAntigravity', 'ctxPctAntigravity', 'ctxTipAntigravity', 'badgeStressAntigravity', a.context_stress_pct || 0, t);

        const g = tool_matrix.chatgpt;
        document.getElementById('costChatGPT').textContent = `$${g.spent.toFixed(2)}`;
        document.getElementById('tokensChatGPT').textContent = `${g.tokens.toLocaleString()} Tokens`;
        document.getElementById('reqsChatGPT').textContent = `${g.requests} Calls`;
        updateToolContextBar('ctxBarChatGPT', 'ctxPctChatGPT', 'ctxTipChatGPT', 'badgeStressChatGPT', g.context_stress_pct || 0, t);
      }

      // 2. 表盘 1 (今日消费与自定义预算)
      document.getElementById('gaugeTodayCost').textContent = `$${today.spent.toFixed(2)}`;
      document.getElementById('gaugeTodayTokens').textContent = `${today.tokens.toLocaleString()} Tokens`;
      document.getElementById('gaugeTodayReqs').textContent = `${today.requests}`;
      document.getElementById('gaugeDailyBudget').textContent = `${userDailyBudget.toFixed(2)}`;

      const budgetPct = (today.spent / userDailyBudget) * 100;
      const costCircle = document.getElementById('costGaugeCircle');
      const statusBadge = document.getElementById('budgetStatusBadge');

      if (budgetPct >= 100) {
        costCircle.setAttribute('stroke', 'url(#costDangerGradient)');
        statusBadge.textContent = t.budget_over;
        statusBadge.style.color = 'var(--accent-rose)';
      } else if (budgetPct >= 75) {
        costCircle.setAttribute('stroke', 'url(#costWarningGradient)');
        statusBadge.textContent = t.budget_near_limit;
        statusBadge.style.color = 'var(--accent-amber)';
      } else {
        costCircle.setAttribute('stroke', 'url(#costGradient)');
        statusBadge.textContent = t.budget_on_track;
        statusBadge.style.color = 'var(--accent-cyan)';
      }
      setGaugeProgress('costGaugeCircle', Math.max(8, Math.min(100, budgetPct)));

      // 3. 表盘 2 (速率)
      document.getElementById('gaugeVelocity').textContent = velocity_tpm.toLocaleString();
      const velPct = Math.min(100, (velocity_tpm / 200000) * 100);
      setGaugeProgress('velGaugeCircle', Math.max(8, velPct));

      // 4. 表盘 3 (实时当前上下文负荷 vs 今日峰值)
      const currentContextPct = ((today.current_context_pct !== undefined ? today.current_context_pct : today.max_context_pct) * 100).toFixed(1);
      const peakContextPct = ((today.max_context_pct || 0) * 100).toFixed(1);
      
      document.getElementById('gaugeContextPct').textContent = `${currentContextPct}%`;
      setGaugeProgress('contextGaugeCircle', Math.max(8, currentContextPct));
      
      const healthText = document.getElementById('contextHealthText');
      if (currentContextPct > 80) {
        healthText.textContent = t.gauge3_health_warn;
        healthText.style.color = 'var(--accent-rose)';
      } else if (currentContextPct > 50) {
        healthText.textContent = t.gauge3_health_moderate;
        healthText.style.color = 'var(--accent-amber)';
      } else {
        healthText.textContent = t.gauge3_health_safe;
        healthText.style.color = 'var(--accent-emerald)';
      }
      const peakEl = document.getElementById('gaugePeakContext');
      if (peakEl) peakEl.textContent = `${peakContextPct}%`;

      // 5. 模型榜单
      const modelList = document.getElementById('modelList');
      if (top_models && top_models.length > 0) {
        const maxSpent = Math.max(...top_models.map(m => m.total_spent), 0.01);
        modelList.innerHTML = top_models.map(m => {
          const pct = Math.min(100, Math.max(6, (m.total_spent / maxSpent) * 100));
          const providerClass = `pill-${m.provider || 'anthropic'}`;
          return `
            <div class="model-item">
              <div class="model-item-top">
                <div class="model-name">
                  <span class="provider-pill ${providerClass}">${m.provider || 'AI'}</span>
                  <span>${m.model_name}</span>
                </div>
                <div class="model-cost">$${m.total_spent.toFixed(2)}</div>
              </div>
              <div class="model-bar-bg">
                <div class="model-bar-fill" style="width: ${pct}%;"></div>
              </div>
              <div style="display: flex; justify-content: space-between; font-size: 11px; color: var(--text-muted); font-family: var(--font-mono);">
                <span>${m.total_tokens.toLocaleString()} tokens</span>
                <span>${m.requests} ${t.models_calls}</span>
              </div>
            </div>
          `;
        }).join('');
      }

      // 6. 实时流水流
      const tbody = document.getElementById('feedTableBody');
      if (recent_requests && recent_requests.length > 0) {
        let filtered = recent_requests;
        if (currentFilter !== 'all') {
          filtered = recent_requests.filter(r => (r.provider || '').toLowerCase() === currentFilter);
        }
        tbody.innerHTML = filtered.slice(0, 15).map(r => {
          const d = new Date(r.started_at * 1000);
          const timeStr = d.toTimeString().split(' ')[0];
          const proj = r.project_name || 'General';
          const costStr = (r.cost_usd || 0).toFixed(4);
          const inTokens = (r.input_tokens || 0).toLocaleString();
          const outTokens = (r.output_tokens || 0).toLocaleString();
          return `
            <tr>
              <td style="color: var(--text-muted);">${timeStr}</td>
              <td><span style="background: rgba(139, 92, 246, 0.15); color: #C084FC; padding: 2px 6px; border-radius: 4px; font-size: 11px;">📁 ${proj}</span></td>
              <td style="font-weight: 600;">${r.model_name || '?'}</td>
              <td>${inTokens} → ${outTokens}</td>
              <td style="color: var(--accent-amber); font-weight: 700;">$${costStr}</td>
            </tr>
          `;
        }).join('');
      }

      // 7. 全量审计流
      renderFullStream(recent_requests || []);
    }

    // 初始化
    applyTranslations();
    fetchDashboardData();
    setInterval(fetchDashboardData, 3000);
  </script>
</body>
</html>
"""
