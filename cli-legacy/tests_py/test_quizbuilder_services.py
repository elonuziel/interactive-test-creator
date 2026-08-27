import importlib.util
from pathlib import Path
import sys


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from quizbuilder.providers import detect_providers
from quizbuilder.workspace import create_workspace, discover_sources
from quizbuilder.models import Workspace


def test_provider_registry_detects_only_available_commands():
    found = detect_providers(lookup=lambda name: f"/bin/{name}" if name == "freebuff-cli" else None)
    assert [(provider.id, command) for provider, command in found] == [("freebuff", "/bin/freebuff-cli")]


def test_workspace_creation_and_source_discovery(tmp_path):
    workspace = create_workspace(tmp_path, "biology practice")
    (workspace.path / "exam.pdf").touch()
    (workspace.path / "answers.xlsx").touch()
    sources = discover_sources(workspace)
    assert workspace.name == "biology_practice"
    assert sources.pdf.name == "exam.pdf"
    assert sources.answer_keys[0].name == "answers.xlsx"
