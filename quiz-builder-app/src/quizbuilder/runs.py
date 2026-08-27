from __future__ import annotations

import copy
import json

from .persistence import write_json_atomic
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .models import Workspace
from .validation import ValidationError, load_questions


class RunError(ValueError):
    """Raised when a test run cannot be assembled."""


@dataclass(frozen=True)
class RunQuestion:
    """A question in a run, retaining its source project for review."""

    question: dict
    source: str
    source_path: Path


@dataclass(frozen=True)
class QuizRun:
    """Questions selected for one standalone quiz run."""

    name: str
    questions: tuple[RunQuestion, ...]
    sources: tuple[str, ...]

    @property
    def payload(self) -> list[dict]:
        return [copy.deepcopy(item.question) for item in self.questions]


def assemble_run(
    workspaces: Iterable[Workspace],
    *,
    name: str | None = None,
    mix: bool = False,
) -> QuizRun:
    selected = tuple(workspaces)
    if not selected:
        raise RunError("Select at least one test to run.")
    if not mix and len(selected) != 1:
        raise RunError("Select exactly one test, or enable mixed mode.")

    run_questions: list[RunQuestion] = []
    source_names: list[str] = []
    for workspace in selected:
        path = workspace.questions_path
        if not path.is_file():
            raise RunError(f"Test '{workspace.name}' has no questions.json file (questions.md is also accepted).")
        try:
            questions = load_questions(path)
        except ValidationError as exc:
            raise RunError(f"Test '{workspace.name}' is invalid: {exc}") from exc
        source_names.append(workspace.name)
        run_questions.extend(
            RunQuestion(copy.deepcopy(question), workspace.name, workspace.path)
            for question in questions
        )

    if not run_questions:
        raise RunError("The selected tests contain no questions.")
    default_name = "mixed_quiz" if mix else source_names[0]
    return QuizRun(name=name or default_name, questions=tuple(run_questions), sources=tuple(source_names))


def write_run_questions(run: QuizRun, output: Path) -> Path:
    """Write a derived questions file without changing any source project."""

    output.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(output, run.payload)
    return output
