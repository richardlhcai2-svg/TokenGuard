"""Standalone proxy launcher — tg serve."""
import os
import sys
from rich.console import Console
from rich.panel import Panel
from . import config
from .storage import UsageStore

console = Console()


def _find_proxy_app():
    """Locate and import the proxy FastAPI app."""
    # Try in-package path (pip install with proxy bundled)
    try:
        from tokenguard.proxy.app.main import app
        return app
    except ImportError:
        pass
    # Try symlink path (dev mode: src/tokenguard/proxy -> proxy/app)
    pkg_proxy = os.path.join(os.path.dirname(__file__), "proxy")
    if os.path.isdir(pkg_proxy):
        if pkg_proxy not in sys.path:
            sys.path.insert(0, pkg_proxy)
    try:
        from app.main import app
        return app
    except ImportError:
        pass
    # Try project root path (dev mode: run from project root)
    dev = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "proxy")
    if os.path.isdir(dev) and dev not in sys.path:
        sys.path.insert(0, dev)
    try:
        from app.main import app
        return app
    except ImportError:
        raise ImportError(
            "Cannot find proxy FastAPI app. Install with: pip install -e ."
        )


def serve(port: int = 8001, host: str = "0.0.0.0", reload: bool = False):
    import uvicorn

    proxy_secret = config.get_proxy_secret()
    UsageStore()  # ensure DB initialized

    # Configure for standalone mode — BACKEND_URL will be unreachable,
    # triggering the SQLite fallback in _save_usage_async
    os.environ.setdefault("BACKEND_URL", "http://localhost:0")
    os.environ.setdefault("PROXY_SECRET", proxy_secret)

    api_keys = config.get_api_keys()
    providers_msg = ", ".join(api_keys.keys()) if api_keys else "none"

    console.print(Panel(
        f"[bold green]TokenGuard Proxy Starting[/bold green]\n\n"
        f"  Listen:    http://{host}:{port}\n"
        f"  Storage:   SQLite (~/.tokenguard/usage.db)\n"
        f"  Providers: {providers_msg}\n"
        f"  Secret:    {proxy_secret[:8]}...{proxy_secret[-4:]}\n\n"
        f"  [bold]In your tools, set:[/bold]\n"
        f"    Base URL:  http://localhost:{port}\n"
        f"    Header:    x-tokenguard-key: {proxy_secret}",
        title="TokenGuard",
    ))

    app = _find_proxy_app()
    uvicorn.run(app, host=host, port=port, reload=reload, log_level="info")
