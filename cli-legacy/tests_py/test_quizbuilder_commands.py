from pathlib import Path
import sys

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quizbuilder.cli import main
from quizbuilder.commands import clean_workspace, process_workspaces, validate_questions
from quizbuilder.config import Config


def test_clean_workspace_removes_known_artifacts(tmp_path):
    (tmp_path / "prompt_local_agent.txt").write_text("prompt", encoding="utf-8")
    (tmp_path / "questions.json").write_text("[]", encoding="utf-8")
    assert clean_workspace(tmp_path) == 1
    assert not (tmp_path / "prompt_local_agent.txt").exists()
    assert (tmp_path / "questions.json").exists()


def test_validate_questions_returns_count(tmp_path):
    path = tmp_path / "questions.json"
    path.write_text('[{"question":"What?","options":["Yes","No"]}]', encoding="utf-8")
    assert validate_questions(path) == 1


def test_cli_version_command(capsys):
    rc = main(["version"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "2.1.0" in captured.out


def test_cli_detect_no_dependencies(capsys):
    rc = main(["detect", "--no-dependencies"])
    assert rc == 0


def test_cli_clean_command(tmp_path, capsys):
    (tmp_path / "prompt_local_agent.txt").write_text("prompt", encoding="utf-8")
    rc = main(["clean", str(tmp_path)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Removed 1 scratch file(s)" in captured.out


def test_cli_validate_command(tmp_path, capsys):
    path = tmp_path / "questions.json"
    path.write_text('[{"question":"What?","options":["Yes","No"]}]', encoding="utf-8")
    rc = main(["validate", str(path)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Valid: 1 question(s)" in captured.out


def test_cli_run_mixed_command_writes_derived_questions(tmp_path, capsys):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    first.joinpath("questions.json").write_text(
        '[{"question":"One","options":["A","B"]}]', encoding="utf-8"
    )
    second.joinpath("questions.json").write_text(
        '[{"question":"Two","options":["A","B"]}]', encoding="utf-8"
    )
    output = tmp_path / "mixed.json"

    rc = main(["run", "--mix", str(first), str(second), "-o", str(output)])

    assert rc == 0
    assert "mixed.json" in capsys.readouterr().out
    assert '"question": "One"' in output.read_text(encoding="utf-8")
    assert '"question": "Two"' in output.read_text(encoding="utf-8")


def test_process_workspaces_continues_after_one_failure(tmp_path, monkeypatch):
    first = tmp_path / "first"
    second = tmp_path / "second"

    def fake_process(_config, workspace, **_kwargs):
        if workspace == second:
            raise RuntimeError("broken PDF")
        return [workspace / "questions.json"]

    monkeypatch.setattr("quizbuilder.commands.process_workspace", fake_process)
    results = process_workspaces(Config.defaults(root=tmp_path), [first, second])

    assert results[0].success is True
    assert results[1].success is False
    assert results[1].error == "broken PDF"

