from pathlib import Path
import os
import sys

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quizbuilder.config import Config


def test_config_defaults(tmp_path):
    config = Config.defaults(root=tmp_path)
    assert config.workspace_root == tmp_path
    assert config.default_form == "0"
    assert config.default_discard_pages == "std"
    assert config.auto_build is True
    assert config.provider.open_browser is True
    assert "freebuff" in config.provider.freebuff_commands


def test_config_load_from_toml(tmp_path):
    toml_file = tmp_path / "custom_config.toml"
    toml_file.write_text(
        """
workspace_root = "/tmp/my_tests"
scripts_root = "/tmp/my_scripts"
default_form = "1"
default_discard_pages = "1-3, 5"
auto_build = false

[provider]
freebuff_commands = ["my-freebuff", "freebuff-cli"]
open_browser = false
""",
        encoding="utf-8",
    )

    config = Config.load(path=toml_file)
    assert str(config.workspace_root) == "/tmp/my_tests"
    assert str(config.scripts_root) == "/tmp/my_scripts"
    assert config.default_form == "1"
    assert config.default_discard_pages == "1-3, 5"
    assert config.auto_build is False
    assert config.provider.freebuff_commands == ("my-freebuff", "freebuff-cli")
    assert config.provider.open_browser is False


def test_config_load_from_env_var(tmp_path, monkeypatch):
    toml_file = tmp_path / "env_config.toml"
    toml_file.write_text('default_form = "42"\n', encoding="utf-8")
    monkeypatch.setenv("QUIZBUILDER_CONFIG", str(toml_file))

    config = Config.load()
    assert config.default_form == "42"


def test_config_load_nonexistent_returns_defaults(tmp_path):
    nonexistent = tmp_path / "nonexistent.toml"
    config = Config.load(path=nonexistent, root=tmp_path)
    assert config.workspace_root == tmp_path
    assert config.default_form == "0"
