"""Docker stack launcher — tg deploy."""
import os
import shutil
import subprocess
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from . import config

console = Console()

DEFAULT_COMPOSE_CONTENT = """version: "3.9"

services:
  db:
    image: timescale/timescaledb:latest-pg16
    container_name: tokenguard-db
    environment:
      POSTGRES_USER: tokenguard
      POSTGRES_PASSWORD: tokenguard_dev
      POSTGRES_DB: tokenguard
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    container_name: tokenguard-redis
    ports:
      - "6379:6379"

  backend:
    image: tokenguard/backend:latest
    container_name: tokenguard-backend
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://tokenguard:tokenguard_dev@db:5432/tokenguard
      REDIS_URL: redis://redis:6379/0
      JWT_SECRET: ${JWT_SECRET:-dev-secret-change-in-production}
      PROXY_SECRET: ${PROXY_SECRET}
    depends_on:
      - db
      - redis

  proxy:
    image: tokenguard/proxy:latest
    container_name: tokenguard-proxy
    ports:
      - "${PROXY_PORT:-8001}:8001"
    environment:
      BACKEND_URL: http://backend:8000
      REDIS_URL: redis://redis:6379/0
      PROXY_SECRET: ${PROXY_SECRET}
    depends_on:
      - backend

  frontend:
    image: tokenguard/frontend:latest
    container_name: tokenguard-frontend
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000/api/v1
    depends_on:
      - backend

volumes:
  pgdata:
"""


def _find_or_create_compose_file() -> tuple[str, str]:
    """Find existing docker-compose.yml or generate one in ~/.tokenguard."""
    # 1. Check current directory
    cwd_compose = os.path.join(os.getcwd(), "docker-compose.yml")
    if os.path.isfile(cwd_compose):
        return cwd_compose, os.getcwd()

    # 2. Check project root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    proj_compose = os.path.join(project_root, "docker-compose.yml")
    if os.path.isfile(proj_compose):
        return proj_compose, project_root

    # 3. Fallback: create in ~/.tokenguard/docker-compose.yml
    tg_dir = Path.home() / ".tokenguard"
    tg_dir.mkdir(parents=True, exist_ok=True)
    tg_compose = tg_dir / "docker-compose.yml"
    if not tg_compose.exists():
        tg_compose.write_text(DEFAULT_COMPOSE_CONTENT)
    return str(tg_compose), str(tg_dir)


def _get_docker_compose_cmd() -> list[str]:
    """Detect if 'docker compose' or 'docker-compose' is available."""
    # Try docker compose first
    try:
        res = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True)
        if res.returncode == 0:
            return ["docker", "compose"]
    except Exception:
        pass

    # Fallback to docker-compose
    if shutil.which("docker-compose"):
        return ["docker-compose"]

    return ["docker", "compose"]


def deploy(port: int = 8001):
    compose_file, work_dir = _find_or_create_compose_file()

    proxy_secret = config.get_proxy_secret()
    env = os.environ.copy()
    env["PROXY_SECRET"] = proxy_secret
    env["PROXY_PORT"] = str(port)

    console.print(Panel(
        "[bold green]Starting TokenGuard Stack[/bold green]\n\n"
        f"  Proxy port: {port}\n"
        f"  Compose:    {compose_file}\n"
        f"  Secret:     {proxy_secret[:8]}...{proxy_secret[-4:]}\n\n"
        f"  [dim]Press Ctrl+C to stop[/dim]",
        title="TokenGuard Deploy",
    ))

    docker_cmd = _get_docker_compose_cmd()
    cmd = docker_cmd + ["-f", compose_file, "up", "-d"]
    console.print(f"  Running: {' '.join(cmd)}\n")

    try:
        result = subprocess.run(cmd, env=env, cwd=work_dir)
        if result.returncode == 0:
            console.print(f"\n[green]✓[/green] Stack started!")
            console.print(f"  Dashboard: [cyan]http://localhost:3000[/cyan]")
            console.print(f"  Proxy:     [cyan]http://localhost:{port}[/cyan]")
            console.print(f"\n  Run [bold]{' '.join(docker_cmd)} logs -f[/bold] to see logs")
            console.print(f"  Run [bold]{' '.join(docker_cmd)} down[/bold] to stop")
        else:
            console.print(f"\n[red]✗[/red] Failed to start stack (exit code {result.returncode})")
            sys.exit(result.returncode)
    except FileNotFoundError:
        console.print("[red]✗[/red] Docker is not installed or not in PATH. Please install Docker to use full-stack mode.")
        sys.exit(1)

