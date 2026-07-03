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
def stats(watch, days):
    """Show usage dashboard in the terminal."""
    from .stats import stats as _st
    _st(watch=watch, days=days)


@cli.command()
@click.argument("key", required=False)
@click.argument("value", required=False)
def config(key, value):
    """View or set configuration (API keys, settings)."""
    from .config_cli import config_cmd
    config_cmd(key=key, value=value)
