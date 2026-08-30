"""Terminal dashboard — tg stats & tg projects."""
import time
from typing import Optional
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
    table.add_column("Model")
    table.add_column("Provider", style="dim")
    table.add_column("Spent", justify="right", style="bold")
    table.add_column("Tokens", justify="right")
    table.add_column("Requests", justify="right")
    for m in models:
        table.add_row(
            m["model_name"], m.get("provider", ""),
            f"${m['total_spent']:.2f}", f"{m['total_tokens']:,}", str(m["requests"]),
        )
    return table


def _projects_table(projects_data: list) -> Table:
    table = Table(title="📁 AI Cost Attribution by Project / Workspace", box=None, header_style="bold cyan")
    table.add_column("Project / Workspace", style="bold white")
    table.add_column("Spent", justify="right", style="bold yellow")
    table.add_column("Share", justify="right", style="cyan")
    table.add_column("Tokens", justify="right")
    table.add_column("Calls", justify="right")
    table.add_column("Last Active", style="dim")
    for p in projects_data:
        la = time.strftime("%Y-%m-%d %H:%M", time.localtime(p.get("last_active", 0))) if p.get("last_active") else "-"
        table.add_row(
            f"📁 {p['project_name']}",
            f"${p['spent']:.2f}",
            f"{p['cost_pct']:.1f}%",
            f"{p['tokens']:,}",
            str(p["requests"]),
            la,
        )
    return table


def _feed_table(feed: list) -> Table:
    table = Table(box=None, header_style="dim")
    table.add_column("Time", style="dim", width=10)
    table.add_column("Project", style="magenta", width=14)
    table.add_column("Model", style="cyan")
    table.add_column("Tokens", justify="right", width=18)
    table.add_column("Cost", justify="right", style="yellow")
    for r in feed:
        t = time.strftime("%H:%M:%S", time.localtime(r.get("started_at", 0)))
        table.add_row(
            t,
            r.get("project_name", "General"),
            r.get("model_name", "?"),
            f"{r.get('input_tokens', 0)}->{r.get('output_tokens', 0)} tok",
            f"${r.get('cost_usd', 0):.4f}",
        )
    return table


def show_projects(days: Optional[int] = None):
    """Render project cost attribution table in CLI."""
    store = UsageStore()
    p_data = store.get_project_stats(days=days)
    if not p_data:
        msg = f"No project usage recorded in the last {days} days." if days else "No project usage recorded yet."
        console.print(f"[yellow]{msg}[/yellow]")
        return
    title = f"📁 Project Cost Attribution (Last {days}d)" if days else "📁 Project Cost Attribution (All-Time Lifetime)"
    console.print(Panel(_projects_table(p_data), title=title))


def stats(watch: bool = False, days: int = 7, project: Optional[str] = None):
    store = UsageStore()
    title_suffix = f" (Project: {project})" if project and project != "all" else ""
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
                    s = store.get_stats(days, project=project)
                    m = store.get_top_models(days, 5, project=project)
                    f = store.get_live_feed(8, project=project)
                    layout["summary"].update(
                        Panel(_summary_table(s), title=f"TokenGuard Usage (Last {days}d){title_suffix}")
                    )
                    layout["models"].update(_models_table(m))
                    layout["feed"].update(Panel(_feed_table(f), title="Live Feed"))
                    time.sleep(3)
            except KeyboardInterrupt:
                pass
    else:
        s = store.get_stats(days, project=project)
        console.print(Panel(_summary_table(s), title=f"TokenGuard Usage (Last {days}d){title_suffix}"))
        m = store.get_top_models(days, 5, project=project)
        if m:
            console.print(_models_table(m))
        f = store.get_live_feed(10, project=project)
        if f:
            console.print(Panel(_feed_table(f), title="Recent Requests"))
