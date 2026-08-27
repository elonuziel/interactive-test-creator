from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .documents import classify_pdf
from .exporter import build_standalone_quiz
from .pipeline import PipelineRunner
from .prompts import generate_prompt
from .validation import load_questions
from .workspace import Workspace, clean_scratch, discover_sources


@dataclass(frozen=True)
class BatchProcessResult:
    workspace: Path
    success: bool
    artifacts: tuple[Path, ...] = ()
    error: str | None = None


def process_workspace(
    config: Config,
    workspace_path: Path,
    answer_key: Path | None = None,
    form: str | None = None,
    pdf: Path | None = None,
) -> list[Path]:
    workspace = Workspace(workspace_path.name, workspace_path.resolve())
    workspace.path.mkdir(parents=True, exist_ok=True)
    sources = discover_sources(workspace)
    pdf_candidates = sorted(
        (item for item in workspace.path.iterdir() if item.is_file() and item.suffix.lower() == ".pdf"),
        key=lambda item: item.name.lower(),
    )
    selected_pdf = pdf.resolve() if pdf else sources.pdf
    if len(pdf_candidates) > 1 and pdf is None:
        raise ValueError(f"Multiple PDF sources found in {workspace.path}; choose one explicitly.")
    if not selected_pdf:
        raise FileNotFoundError(f"No PDF found in {workspace.path}")

    scripts = config.scripts_root
    runner = PipelineRunner(scripts)
    artifacts = []
    selected_answer_key = answer_key or (sources.answer_keys[0] if sources.answer_keys else None)
    if selected_answer_key:
        answers = workspace.path / "answers.json"
        runner.extract_answers(selected_answer_key, form or config.default_form, answers)
        artifacts.append(answers)
    if classify_pdf(selected_pdf):
        raw = workspace.path / "raw_text.md"
        images = workspace.path / "images"
        page_map = workspace.path / "page_map.json"
        runner.extract_text(selected_pdf, raw, images, page_map)
        runner.parse_questions(raw, workspace.questions_path, images, page_map)
        artifacts.extend((raw, workspace.questions_path))
    else:
        pages = workspace.path / "pages_output"
        merged = workspace.path / f"{workspace.name}_clean.pdf"
        runner.render_pages(selected_pdf, pages, config.default_discard_pages, merged)
        artifacts.extend((pages, merged))

    if workspace.questions_path.exists():
        runner.merge_answers(workspace.path)
        runner.validate(workspace.questions_path)
        artifacts.append(workspace.questions_path)
    return artifacts


def process_workspaces(
    config: Config,
    workspaces: list[Workspace | Path],
) -> tuple[BatchProcessResult, ...]:
    results = []
    for selected in workspaces:
        workspace_path = selected.path if isinstance(selected, Workspace) else selected
        answer_key = selected.source_answer_keys[0] if isinstance(selected, Workspace) and selected.source_answer_keys else None
        pdf = selected.source_pdf if isinstance(selected, Workspace) else None
        try:
            artifacts = process_workspace(config, workspace_path, answer_key=answer_key, pdf=pdf)
        except Exception as exc:
            results.append(BatchProcessResult(workspace_path, False, error=str(exc)))
        else:
            results.append(BatchProcessResult(workspace_path, True, tuple(artifacts)))
    return tuple(results)


def generate_workspace_prompt(config: Config, workspace_path: Path, kind: str = "local", form: str | None = None) -> Path:
    workspace = Workspace(workspace_path.name, workspace_path.resolve())
    sources = discover_sources(workspace)
    runner = PipelineRunner(config.scripts_root)
    return generate_prompt(runner, workspace.path, workspace.name, form or config.default_form, bool(sources.answer_keys), kind)


def validate_questions(path: Path) -> int:
    return len(load_questions(path))


def clean_workspace(path: Path) -> int:
    return len(clean_scratch(Workspace(path.name, path.resolve())))


def build_workspace(config: Config, path: Path, output: Path | None = None) -> Path:
    return build_standalone_quiz(path.resolve(), config.scripts_root, output)
