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


def test_frozen_application_root_uses_meipass(monkeypatch, tmp_path):
    from quizbuilder.paths import application_root

    meipass_dir = tmp_path / "meipass"
    meipass_dir.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass_dir), raising=False)

    assert application_root() == meipass_dir


def test_frozen_pipeline_runner_runs_in_process(monkeypatch, tmp_path):
    from quizbuilder.pipeline import PipelineRunner

    script = tmp_path / "test_stage.py"
    script.write_text(
        "import sys\nprint('hello ' + sys.argv[1])\nraise SystemExit(0)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    runner = PipelineRunner(tmp_path)
    result = runner.run("test_stage.py", "world")

    assert result.ok is True
    assert "hello world" in result.stdout


def test_gui_main_raises_runtime_error_without_pyside6(monkeypatch):
    import pytest
    from quizbuilder import gui

    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", None)
    with pytest.raises(RuntimeError, match="GUI requires PySide6"):
        gui.main()

