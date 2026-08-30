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
    from .quickstart import quickstart as _qs
    _qs()


@cli.command()
@click.option("--port", default=8001, type=int, help="Proxy listen port")
@click.option("--host", default="0.0.0.0", help="Proxy bind address")
@click.option("--reload", is_flag=True, help="Auto-reload on code changes")
def serve(port, host, reload):
    """Start standalone proxy with local SQLite storage."""
    from .serve import serve as _s
    _s(port=port, host=host, reload=reload)


@cli.command()
@click.option("--port", default=8001, type=int, help="Proxy listen port")
def deploy(port):
    """Start the full Docker Compose stack."""
    from .deploy import deploy as _d
    _d(port=port)


@cli.command()
@click.option("--watch", "-w", is_flag=True, help="Auto-refresh every 3 seconds")
@click.option("--days", default=7, type=int, help="Number of days to show")
@click.option("--project", "-p", default=None, type=str, help="Filter stats by project/workspace name")
def stats(watch, days, project):
    """Show usage dashboard in the terminal."""
    from .stats import stats as _st
    _st(watch=watch, days=days, project=project)


@cli.command("projects")
@click.option("--days", default=None, type=int, help="Number of days to analyze (default: all-time lifetime)")
def projects_cmd(days):
    """Show AI cost attribution broken down by Git Repository / Project / Workspace."""
    from .stats import show_projects
    show_projects(days=days)


@cli.command()
@click.argument("key", required=False)
@click.argument("value", required=False)
def config(key, value):
    """View or set configuration (API keys, settings)."""
    from .config_cli import config_cmd
    config_cmd(key=key, value=value)


@cli.command("dashboard")
@click.option("--port", default=8001, type=int, help="Proxy dashboard port")
def dashboard(port):
    """Open visual dial dashboard in your web browser."""
    import webbrowser
    import urllib.request
    from rich.console import Console

    console = Console()
    url = f"http://localhost:{port}/dashboard"
    console.print(f"[bold cyan]🎯 Opening TokenGuard Visual Dashboard:[/bold cyan] [underline]{url}[/underline]")
    try:
        urllib.request.urlopen(f"http://localhost:{port}/health", timeout=1)
    except Exception:
        console.print(f"[yellow]⚠️ Note: TokenGuard proxy on port {port} is not running. Run 'tg serve' to start it.[/yellow]")
    webbrowser.open(url)


@cli.command("ui", hidden=True)
@click.option("--port", default=8001, type=int, help="Proxy dashboard port")
def ui_cmd(port):
    """Alias for dashboard."""
    import webbrowser
    webbrowser.open(f"http://localhost:{port}/dashboard")
