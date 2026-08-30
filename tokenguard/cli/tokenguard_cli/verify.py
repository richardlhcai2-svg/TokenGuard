"""Onboarding and verification commands."""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone


def cmd_verify(args):
    """Verify TokenGuard setup is working end-to-end.

    Tests: backend health → auth → proxy connectivity → sample data submission.
    """
    backend_url = os.getenv("TOKENGUARD_BACKEND", "http://localhost:8000")
    proxy_url = os.getenv("ANTHROPIC_BASE_URL", "")

    print("TokenGuard Verify")
    print("=" * 50)

    passed = 0
    total = 0
    failures = []

    # 1. Backend health
    total += 1
    print("\n[1/4] Checking backend health...")
    try:
        import urllib.request
        req = urllib.request.Request(f"{backend_url}/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            if data.get("status") == "ok":
                print(f"  OK  Backend running at {backend_url}")
                passed += 1
            else:
                print(f"  FAIL  Unexpected response: {data}")
                failures.append("backend_health")
    except Exception as e:
        print(f"  FAIL  Cannot reach backend: {e}")
        failures.append("backend_health")

    # 2. Auth test (create temp user if needed)
    total += 1
    print("\n[2/4] Testing authentication...")
    try:
        import urllib.request
        # Try to register a test user
        payload = json.dumps({
            "email": "test@tokenguard.local",
            "name": "Test User",
            "password": "testtest123",
        }).encode()
        req = urllib.request.Request(
            f"{backend_url}/api/v1/auth/register",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                token_data = json.loads(resp.read())
                token = token_data["access_token"]
                print(f"  OK  Registration successful")
        except urllib.error.HTTPError as e:
            if e.code == 409:
                # Already exists, try login
                login_payload = json.dumps({
                    "email": "test@tokenguard.local",
                    "password": "testtest123",
                }).encode()
                req = urllib.request.Request(
                    f"{backend_url}/api/v1/auth/login",
                    data=login_payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    token_data = json.loads(resp.read())
                    token = token_data["access_token"]
                print(f"  OK  Login successful")
            else:
                print(f"  FAIL  Auth error: {e.code} {e.reason}")
                failures.append("auth")
                # Skip remaining tests if auth fails
                _print_summary(passed, total, failures)
                return

        # Store token for next test
        _save_token(token)
        print(f"  OK  Token stored for verification")
        passed += 1
    except Exception as e:
        print(f"  FAIL  Auth test failed: {e}")
        failures.append("auth")

    # 3. Proxy URL check
    total += 1
    print("\n[3/4] Checking proxy configuration...")
    if proxy_url:
        print(f"  OK  ANTHROPIC_BASE_URL={proxy_url}")
        passed += 1
    else:
        print(f"  WARN  ANTHROPIC_BASE_URL not set")
        print(f"        Run: tg init --proxy-url http://localhost:8001")
        failures.append("proxy_config")

    # 4. Sample data submission
    total += 1
    print("\n[4/4] Testing data submission...")
    try:
        token = _load_token()
        if not token:
            print("  FAIL  No token found. Re-run auth test.")
            failures.append("data_submission")
        else:
            payload = json.dumps({
                "organization_id": "00000000-0000-0000-0000-000000000000",
                "user_id": "test-user",
                "tool_name": "claude_code",
                "model_name": "claude-sonnet-4-20250514",
                "provider": "anthropic",
                "input_tokens": 1000,
                "output_tokens": 500,
                "cache_creation_tokens": 0,
                "cache_read_tokens": 0,
                "cost_usd": "0.003",
                "session_id": f"verify-{int(datetime.now(timezone.utc).timestamp())}",
                "project_name": "tg-verify",
                "task_type": "general",
                "context_window_size": 200000,
                "context_usage_pct": "0.75",
                "started_at": datetime.now(timezone.utc).isoformat(),
            }).encode()

            req = urllib.request.Request(
                f"{backend_url}/internal/usage",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "x-tokenguard-key": "dev-secret-key",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                result = json.loads(resp.read())
                if result.get("status") == "saved":
                    print(f"  OK  Sample usage record saved")
                    passed += 1
                else:
                    print(f"  FAIL  Unexpected response: {result}")
                    failures.append("data_submission")
    except Exception as e:
        print(f"  FAIL  Data submission failed: {e}")
        failures.append("data_submission")

    _print_summary(passed, total, failures)

    if failures:
        print("\nRemediation:")
        if "backend_health" in failures:
            print("  - Ensure backend is running: cd backend && uvicorn app.main:app --reload")
        if "auth" in failures:
            print("  - Check database connection and ensure migrations are applied")
        if "proxy_config" in failures:
            print("  - Run: tg init --proxy-url http://localhost:8001")
        if "data_submission" in failures:
            print("  - Check PROXY_SECRET matches between proxy and backend")
        sys.exit(1)
    else:
        print("\nAll checks passed! TokenGuard is ready.")


def _save_token(token: str):
    path = os.path.expanduser("~/.tokenguard_token")
    with open(path, "w") as f:
        f.write(token)


def _load_token() -> str | None:
    path = os.path.expanduser("~/.tokenguard_token")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return f.read().strip()


def _print_summary(passed: int, total: int, failures: list[str]):
    print("\n" + "=" * 50)
    print(f"Results: {passed}/{total} checks passed")
    if failures:
        print(f"Failed: {', '.join(failures)}")
    else:
        print("Status: All systems operational")


def cmd_onboard(args):
    """5-minute onboarding wizard."""
    backend_url = os.getenv("TOKENGUARD_BACKEND", "http://localhost:8000")

    print("TokenGuard Onboarding Wizard")
    print("=" * 50)
    print("\nLet's get you set up in 5 minutes.\n")

    # Step 1: Organization
    print("[1/4] Organization Setup")
    org_name = input(f"  Organization name [{os.getenv('USER', 'my-team')}]: ").strip() or os.getenv("USER", "my-team")
    print(f"  OK  Organization '{org_name}' will be created automatically on first login.")

    # Step 2: Register/Login
    print(f"\n[2/4] Account Setup")
    email = input(f"  Email [{os.getenv('USER')}@localhost]: ").strip() or f"{os.getenv('USER', '')}@localhost"
    password = input("  Password: ").strip()
    if len(password) < 8:
        print("  ERROR  Password must be at least 8 characters")
        sys.exit(1)

    print("\n  Registering...")
    try:
        import urllib.request
        payload = json.dumps({"email": email, "name": org_name, "password": password}).encode()
        req = urllib.request.Request(
            f"{backend_url}/api/v1/auth/register",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            token_data = json.loads(resp.read())
            token = token_data["access_token"]
        print("  OK  Account created")
    except urllib.error.HTTPError as e:
        if e.code == 409:
            print("  INFO  Account exists, logging in...")
            login_payload = json.dumps({"email": email, "password": password}).encode()
            req = urllib.request.Request(
                f"{backend_url}/api/v1/auth/login",
                data=login_payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                token_data = json.loads(resp.read())
                token = token_data["access_token"]
            print("  OK  Logged in")
        else:
            print(f"  ERROR  {e.code}: {e.reason}")
            sys.exit(1)

    _save_token(token)

    # Step 3: Proxy setup
    print(f"\n[3/4] Proxy Configuration")
    proxy_port = input(f"  Proxy port [8001]: ").strip() or "8001"
    proxy_url = f"http://localhost:{proxy_port}"

    # Update .zshrc
    zshrc = os.path.expanduser("~/.zshrc")
    lines = _read_lines(zshrc)
    content = "".join(lines)
    import re
    TG_BLOCK_RE = re.compile(
        r"^#\s*TokenGuard\b[^\n]*\nexport\s+ANTHROPIC_BASE_URL=\"[^\"]*\"\n?",
        re.MULTILINE | re.IGNORECASE,
    )
    content = TG_BLOCK_RE.sub("", content)
    content += f"# TokenGuard: AI cost intelligence proxy\nexport ANTHROPIC_BASE_URL=\"{proxy_url}\"\n"
    with open(zshrc, "w") as f:
        f.write(content)
    print(f"  OK  ANTHROPIC_BASE_URL={proxy_url} added to {zshrc}")

    # Step 4: Verification
    print(f"\n[4/4] Quick Verification")
    print(f"  Run: tg verify")
    print(f"  Then visit: http://localhost:3000")
    print(f"\nYou're all set! Next steps:")
    print(f"  1. source {zshrc}")
    print(f"  2. tg verify")
    print(f"  3. Open http://localhost:3000")


def _read_lines(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return f.readlines()

