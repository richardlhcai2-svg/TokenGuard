import sys
import os
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_args(proxy_url="http://localhost:8001", key=None):
    return SimpleNamespace(proxy_url=proxy_url, key=key)


class TestCmdInit:
    """Test the init command logic."""

    def test_default_proxy_url(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        zshrc = tmp_path / ".zshrc"
        zshrc.write_text("")
        from tokenguard_cli.cli import cmd_init
        import tokenguard_cli.cli as cli
        cli._get_zshrc = lambda: str(zshrc)
        cmd_init(_make_args())
        content = zshrc.read_text()
        assert "ANTHROPIC_BASE_URL" in content
        assert "http://localhost:8001" in content
        assert "TokenGuard" in content

    def test_custom_proxy_url(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        zshrc = tmp_path / ".zshrc"
        zshrc.write_text("")
        from tokenguard_cli.cli import cmd_init
        import tokenguard_cli.cli as cli
        cli._get_zshrc = lambda: str(zshrc)
        cmd_init(_make_args(proxy_url="https://tg.example.com", key="my-secret"))
        content = zshrc.read_text()
        assert "https://tg.example.com" in content

    def test_init_replaces_old_block(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        zshrc = tmp_path / ".zshrc"
        zshrc.write_text("# TokenGuard\nexport ANTHROPIC_BASE_URL=\"http://old\"\n# other\n")
        from tokenguard_cli.cli import cmd_init
        import tokenguard_cli.cli as cli
        cli._get_zshrc = lambda: str(zshrc)
        cmd_init(_make_args(proxy_url="http://new"))
        content = zshrc.read_text()
        assert "http://old" not in content
        assert content.count("http://new") == 1
        assert "# other" in content

    def test_proxy_key_from_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("TOKENGUARD_KEY", "env-key-123")
        zshrc = tmp_path / ".zshrc"
        zshrc.write_text("")
        from tokenguard_cli.cli import cmd_init
        import tokenguard_cli.cli as cli
        cli._get_zshrc = lambda: str(zshrc)
        cmd_init(_make_args())
        assert zshrc.exists()


class TestCmdStatus:
    """Test the status command."""

    def test_not_configured(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
        zshrc = tmp_path / ".zshrc"
        zshrc.write_text("")
        import tokenguard_cli.cli as cli
        cli._get_zshrc = lambda: str(zshrc)
        from tokenguard_cli.cli import cmd_status
        cmd_status()
        captured = capsys.readouterr()
        assert "not configured" in captured.out.lower() or "not set" in captured.out.lower()

    def test_configured_shows_active(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://localhost:8001")
        zshrc = tmp_path / ".zshrc"
        zshrc.write_text("# TokenGuard\nexport ANTHROPIC_BASE_URL=\"http://localhost:8001\"\n")
        import tokenguard_cli.cli as cli
        cli._get_zshrc = lambda: str(zshrc)
        from tokenguard_cli.cli import cmd_status
        cmd_status()
        captured = capsys.readouterr()
        assert "active" in captured.out.lower()


class TestCmdUninstall:
    """Test the uninstall command."""

    def test_removes_config(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        zshrc = tmp_path / ".zshrc"
        zshrc.write_text("# other config\n# TokenGuard\nexport ANTHROPIC_BASE_URL=\"http://localhost:8001\"\n# more\n")
        import tokenguard_cli.cli as cli
        cli._get_zshrc = lambda: str(zshrc)
        from tokenguard_cli.cli import cmd_uninstall
        cmd_uninstall()
        content = zshrc.read_text()
        assert "TokenGuard" not in content
        assert "ANTHROPIC_BASE_URL" not in content
        assert "# other config" in content
        assert "# more" in content

    def test_nothing_to_remove(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("HOME", str(tmp_path))
        zshrc = tmp_path / ".zshrc"
        zshrc.write_text("# no tokenguard here\nexport SOMETHING=1\n")
        import tokenguard_cli.cli as cli
        cli._get_zshrc = lambda: str(zshrc)
        from tokenguard_cli.cli import cmd_uninstall
        cmd_uninstall()
        captured = capsys.readouterr()
        assert "nothing to remove" in captured.out.lower()
