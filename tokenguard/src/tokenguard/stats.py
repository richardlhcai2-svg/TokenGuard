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


def _feed_table(feed: list) -> Table:
    table = Table(box=None, header_style="dim")
    table.add_column("Time", style="dim", width=10)
    table.add_column("Model", style="cyan")
    table.add_column("Tokens", justify="right", width=18)
    table.add_column("Cost", justify="right", style="yellow")
    for r in feed:
        t = time.strftime("%H:%M:%S", time.localtime(r.get("started_at", 0)))
        table.add_row(
            t, r.get("model_name", "?"),
            f"{r.get('input_tokens', 0)}->{r.get('output_tokens', 0)} tok",
            f"${r.get('cost_usd', 0):.4f}",
        )
    return table


def stats(watch: bool = False, days: int = 7):
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
                    m = store.get_top_models(days, 5)
                    f = store.get_live_feed(8)
                    layout["summary"].update(
                        Panel(_summary_table(s), title=f"TokenGuard Usage (Last {days}d)")
                    )
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
