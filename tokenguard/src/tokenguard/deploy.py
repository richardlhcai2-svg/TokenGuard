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
    env = os.environ.copy()
    env["PROXY_SECRET"] = proxy_secret

    console.print(Panel(
        "[bold green]Starting TokenGuard Stack[/bold green]\n\n"
        f"  Proxy port: {port}\n"
        f"  Compose:    {COMPOSE_FILE}\n"
        f"  Secret:     {proxy_secret[:8]}...{proxy_secret[-4:]}\n\n"
        f"  [dim]Press Ctrl+C to stop[/dim]",
        title="TokenGuard Deploy",
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
