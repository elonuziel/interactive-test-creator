from __future__ import annotations

from pathlib import Path

from .config import Config
from .documents import classify_pdf
from .exporter import build_standalone_quiz
from .pipeline import PipelineRunner
from .prompts import generate_prompt
from .validation import load_questions
from .workspace import Workspace, clean_scratch, discover_sources


def process_workspace(config: Config, workspace_path: Path) -> list[Path]:
    workspace = Workspace(workspace_path.name, workspace_path.resolve())
    sources = discover_sources(workspace)
    if not sources.pdf:
        raise FileNotFoundError(f"No PDF found in {workspace.path}")

    scripts = config.scripts_root
    runner = PipelineRunner(scripts)
    artifacts = []
    if classify_pdf(sources.pdf):
        raw = workspace.path / "raw_text.md"
        images = workspace.path / "images"
        page_map = workspace.path / "page_map.json"
        runner.extract_text(sources.pdf, raw, images, page_map)
        runner.parse_questions(raw, workspace.questions_path, images, page_map)
        artifacts.extend((raw, workspace.questions_path))
    else:
        pages = workspace.path / "pages_output"
        merged = workspace.path / f"{workspace.name}_clean.pdf"
        runner.render_pages(sources.pdf, pages, config.default_discard_pages, merged)
        artifacts.extend((pages, merged))

    if workspace.questions_path.exists():
        runner.merge_answers(workspace.path)
        runner.validate(workspace.questions_path)
        artifacts.append(workspace.questions_path)
    return artifacts


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
