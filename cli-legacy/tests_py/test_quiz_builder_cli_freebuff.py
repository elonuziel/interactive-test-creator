import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / 'quiz_builder_cli.py'
spec = importlib.util.spec_from_file_location('quiz_builder_cli', MODULE_PATH)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


def test_detect_freebuff_prefers_freebuff_command():
    calls = []

    def lookup(name):
        calls.append(name)
        return '/usr/bin/freebuff' if name == 'freebuff' else None

    assert cli.detect_freebuff_command(lookup) == '/usr/bin/freebuff'
    assert calls == ['freebuff']


def test_detect_freebuff_falls_back_to_alias():
    def lookup(name):
        return '/usr/bin/freebuff-cli' if name == 'freebuff-cli' else None

    assert cli.detect_freebuff_command(lookup) == '/usr/bin/freebuff-cli'


def test_detect_freebuff_returns_none_when_unavailable():
    assert cli.detect_freebuff_command(lambda _name: None) is None
