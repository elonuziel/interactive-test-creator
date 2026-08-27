from __future__ import annotations

import json
import copy
from pathlib import Path
import tempfile

from .markdown import dump_questions

from .paths import application_root
from .pipeline import PipelineRunner
from .runs import QuizRun


def build_standalone_quiz(workspace: Path, scripts_dir: Path | None = None, output: Path | None = None) -> Path:
    scripts_dir = scripts_dir or application_root() / "python_scripts"
    runner = PipelineRunner(scripts_dir)
    args = [str(workspace)]
    if output:
        args.extend(["-o", str(output)])
    runner.require_success("9_build_single_html.py", *args)
    if output:
        return output
    html_files = sorted(workspace.glob("*.html"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not html_files:
        raise FileNotFoundError(f"No standalone HTML file was generated in {workspace}")
    return html_files[0]


def build_run_standalone_quiz(
    run: QuizRun,
    output: Path,
    scripts_dir: Path | None = None,
) -> Path:
    """Export a derived run while keeping source project files untouched."""

    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="quizbuilder-run-") as directory:
        workspace = Path(directory)
        questions = [copy.deepcopy(item.question) for item in run.questions]
        for item, question in zip(run.questions, questions):
            for field in ("image", "pageImage"):
                image = question.get(field)
                if image and not Path(image).is_absolute():
                    question[field] = str((item.source_path / image).resolve())
        (workspace / "questions.md").write_text(
            dump_questions(questions), encoding="utf-8"
        )
        build_standalone_quiz(workspace, scripts_dir, output)
    return output
