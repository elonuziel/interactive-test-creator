"""Tests for provider detection in quizbuilder.providers."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quizbuilder.providers import detect_providers


def test_detect_providers_prefers_freebuff_command():
    detected = detect_providers(
        freebuff_commands=("freebuff", "freebuff-cli"),
        lookup=lambda name: "/usr/bin/freebuff" if name == "freebuff" else None,
    )
    assert len(detected) == 1
    provider, command = detected[0]
    assert provider.id == "freebuff"
    assert command == "/usr/bin/freebuff"


def test_detect_providers_falls_back_to_alias():
    detected = detect_providers(
        freebuff_commands=("freebuff", "freebuff-cli"),
        lookup=lambda name: "/usr/bin/freebuff-cli" if name == "freebuff-cli" else None,
    )
    assert len(detected) == 1
    provider, command = detected[0]
    assert provider.id == "freebuff"
    assert command == "/usr/bin/freebuff-cli"


def test_detect_providers_returns_empty_when_unavailable():
    detected = detect_providers(lookup=lambda _name: None)
    assert detected == []


def test_provider_registry_detects_freebuff_alias():
    detected = detect_providers(
        freebuff_commands=("freebuff", "freebuff-cli"),
        lookup=lambda name: "/opt/freebuff-cli" if name == "freebuff-cli" else None,
    )
    assert [(provider.id, command) for provider, command in detected] == [("freebuff", "/opt/freebuff-cli")]
