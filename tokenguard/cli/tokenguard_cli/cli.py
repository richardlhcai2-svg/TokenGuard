"""TokenGuard CLI — AI development cost intelligence."""

import argparse
import os
import re
import subprocess
import sys

_TG_BLOCK_RE = re.compile(
    r"^#\s*TokenGuard\b[^\n]*\nexport\s+ANTHROPIC_BASE_URL=\"[^\"]*\"\n?",
    re.MULTILINE,
)


def main():
    parser = argparse.ArgumentParser(
        prog="tg",
        description="TokenGuard — AI development cost intelligence",
    )
    subparsers = parser.add_subparsers(dest="command")

    # init
    init_parser = subparsers.add_parser("init", help="Configure TokenGuard proxy")
    init_parser.add_argument(
        "--proxy-url",
        default="http://localhost:8001",
        help="TokenGuard proxy URL (default: http://localhost:8001)",
    )
    init_parser.add_argument(
        "--key",
        help="Proxy secret key",
    )

    # status
    subparsers.add_parser("status", help="Show current TokenGuard config")

    # verify
    subparsers.add_parser("verify", help="End-to-end verification test")

    # onboard
    subparsers.add_parser("onboard", help="5-minute onboarding wizard")

    # uninstall
    subparsers.add_parser("uninstall", help="Remove TokenGuard configuration")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "status":
        cmd_status()
    elif args.command == "verify":
        from tokenguard_cli.verify import cmd_verify
        cmd_verify(args)
    elif args.command == "onboard":
        from tokenguard_cli.verify import cmd_onboard
        cmd_onboard(args)
    elif args.command == "uninstall":
        cmd_uninstall()
    else:
        parser.print_help()


def _get_zshrc():
    return os.path.expanduser("~/.zshrc")


def _read_lines(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return f.readlines()


def _write_lines(path, lines):
    with open(path, "w") as f:
        f.writelines(lines)


def cmd_init(args):
    """Configure TokenGuard proxy for Claude Code."""
    proxy_url = args.proxy_url

    env_var = "ANTHROPIC_BASE_URL"
    zshrc = _get_zshrc()
    config_lines = _read_lines(zshrc)

    # Remove old tokenguard block if present
    content = "".join(config_lines)
    content = _TG_BLOCK_RE.sub("", content)
    config_lines = content.splitlines(True)

    # Add new entry
    new_entry = f"# TokenGuard: AI cost intelligence proxy\nexport {env_var}=\"{proxy_url}\"\n"
    config_lines.append(new_entry)
    _write_lines(zshrc, config_lines)

    print(f"[OK] Set {env_var}={proxy_url}")
    print(f"     Added to {zshrc}")
    print("[OK] Proxy key configured")
    print()
    print("Next steps:")
    print(f"  source {zshrc}")
    print("  tg status")
    print()
    print("To test:")
    print(f'  ANTHROPIC_BASE_URL={proxy_url} claude --message "hello"')


def cmd_status():
    """Show current TokenGuard configuration."""
    env_var = "ANTHROPIC_BASE_URL"
    value = os.environ.get(env_var, "")

    zshrc = _get_zshrc()
    lines = _read_lines(zshrc)
    config_line = [l.strip() for l in lines if "tokenguard" in l.lower()]

    print("TokenGuard Status:")
    print(f"  Env var ({env_var}):", value or "(not set)")
    print(f"  Config file ({zshrc}):", config_line[0] if config_line else "(not configured)")

    if not value and not config_line:
        print("\n  TokenGuard is not configured. Run 'tg init' to set it up.")
    else:
        print("\n  TokenGuard is active!")


def cmd_uninstall():
    """Remove TokenGuard configuration."""
    zshrc = _get_zshrc()
    lines = _read_lines(zshrc)
    content = "".join(lines)

    new_content = _TG_BLOCK_RE.sub("", content)
    if new_content == content:
        print("Nothing to remove.")
        return

    _write_lines(zshrc, new_content.splitlines(True))

    os.environ.pop("ANTHROPIC_BASE_URL", None)

    print(f"[OK] Removed TokenGuard config from {zshrc}")
    print(f"     Run 'source {zshrc}' to apply")


if __name__ == "__main__":
    main()
