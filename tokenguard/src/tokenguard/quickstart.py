"""Interactive setup wizard — tg quickstart."""
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import print as rprint
from . import config, __version__

console = Console()


def quickstart():
    rprint(f"[bold cyan]{'╔' + '═' * 45 + '╗'}[/bold cyan]")
    rprint(f"[bold cyan]║{' ':>45}║[/bold cyan]")
    rprint(f"[bold cyan]║{'TokenGuard Setup':^45}║[/bold cyan]")
    rprint(f"[bold cyan]║{'AI Cost Intelligence CLI':^45}║[/bold cyan]")
    rprint(f"[bold cyan]║{' ':>45}║[/bold cyan]")
    rprint(f"[bold cyan]{'╚' + '═' * 45 + '╝'}[/bold cyan]")
    console.print(f"Version {__version__}\n")

    api_keys = config.get_api_keys()
    if api_keys:
        console.print(f"[green]✓[/green] Already configured with {len(api_keys)} API key(s)")
        redo = Confirm.ask("  Reconfigure?", default=False)
        if not redo:
            _show_next_steps()
            return

    # Step 1: Account
    console.rule("[bold]Step 1/3: Account[/bold]")
    email = Prompt.ask("  Email", default=config.get("email", ""))
    org = Prompt.ask("  Organization", default=config.get("organization", "My Team"))
    if email:
        config.set("email", email)
    config.set("organization", org)

    # Step 2: API Keys
    console.rule("[bold]Step 2/3: API Keys[/bold]")
    console.print("  Configure your AI providers. Skip any with Enter.\n")
    providers = [
        ("anthropic", "Anthropic (Claude)"),
        ("openai", "OpenAI (GPT/o-series)"),
        ("gemini", "Google Gemini"),
        ("deepseek", "DeepSeek"),
    ]
    configured = []
    for key, name in providers:
        existing = config.get(f"{key}_api_key", "")
        if Confirm.ask(f"  Use [bold]{name}[/bold]?", default=bool(existing)):
            hint = f" (current: {existing[:8]}...)" if existing else ""
            api_key = Prompt.ask(f"  Enter {name} API key{hint}", password=True, default=existing)
            if api_key:
                config.set(f"{key}_api_key", api_key)
                configured.append(name)
                console.print(f"  [green]✓[/green] {name} configured")
            else:
                console.print(f"  [yellow]✗[/yellow] {name} skipped")
        else:
            console.print(f"  [dim]  {name} skipped[/dim]")

    # Step 3: Mode
    console.rule("[bold]Step 3/3: Run Mode[/bold]")
    use_docker = Confirm.ask(
        "  Run full stack with Docker? (Web dashboard + team features)",
        default=False,
    )
    config.set("run_mode", "docker" if use_docker else "standalone")
    console.print(f"  [green]✓[/green] {'Full Stack' if use_docker else 'Standalone'} mode selected")

    _show_next_steps()


def _show_next_steps():
    proxy_secret = config.get_proxy_secret()
    api_keys = config.get_api_keys()
    mode = config.get("run_mode", "standalone")

    lines = [
        "",
        f"  [bold green]TokenGuard is ready![/bold green]",
        "",
        f"  API Keys: {', '.join(api_keys.keys()) if api_keys else '[yellow]none[/yellow]'}",
        f"  Mode: {mode}",
        "",
        "  [bold]In your AI tools, configure:[/bold]",
        f"    Base URL:  http://localhost:8001",
        f"    Header:    x-tokenguard-key: {proxy_secret}",
        "",
    ]
    for provider in api_keys:
        lines.append(f"               x-{provider}-key: <your-{provider}-key>")
    lines.append("")
    lines.append("  [bold]Next:[/bold]")
    lines.append(f"    {'tg deploy' if mode == 'docker' else 'tg serve'}  → Start the proxy")
    lines.append("    tg stats  → View usage in real-time")
    lines.append("")

    console.print(Panel("\n".join(lines), title="Setup Complete"))
