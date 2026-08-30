"""Tests for CLI commands, serve, and deploy logic."""
import os
import tempfile
from click.testing import CliRunner
from tokenguard.cli import cli
from tokenguard.serve import _find_proxy_app
from tokenguard.deploy import _find_or_create_compose_file, _get_docker_compose_cmd


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "TokenGuard" in result.output
    assert "quickstart" in result.output
    assert "serve" in result.output
    assert "deploy" in result.output


def test_find_proxy_app():
    app = _find_proxy_app()
    assert app is not None
    assert getattr(app, "title", "") == "TokenGuard Proxy"


def test_find_or_create_compose_file():
    compose_path, work_dir = _find_or_create_compose_file()
    assert os.path.exists(compose_path)
    assert os.path.isdir(work_dir)


def test_get_docker_compose_cmd():
    cmd = _get_docker_compose_cmd()
    assert isinstance(cmd, list)
    assert len(cmd) in (1, 2)
