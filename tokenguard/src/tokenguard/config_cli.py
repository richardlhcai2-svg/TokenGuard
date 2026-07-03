"""tg config command handler."""
from rich.console import Console
from rich.table import Table
from . import config

console = Console()


def config_cmd(key=None, value=None):
    if key and value:
        config.set(key, value)
        console.print(f"[green]✓[/green] {key} set")
    elif key:
        val = config.get(key)
        if val is None:
            console.print(f"[yellow]Key '{key}' not set[/yellow]")
        else:
            masked = config.list_keys().get(key, val)
            console.print(f"{key} = {masked}")
    else:
        keys = config.list_keys()
        if not keys:
            console.print("[yellow]No configuration yet. Run tg quickstart.[/yellow]")
            return
        table = Table(title="TokenGuard Config", box=None)
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")
        for k, v in keys.items():
            table.add_row(k, str(v))
        console.print(table)
