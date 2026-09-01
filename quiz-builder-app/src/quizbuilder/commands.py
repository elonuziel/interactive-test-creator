from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .documents import classify_pdf, preferred_pdf
from .exporter import build_standalone_quiz
from .pipeline import PipelineRunner
from .prompts import generate_prompt
from .validation import load_questions
from .markdown import validate_image_references
from .workspace import Workspace, clean_scratch, discover_sources
from .form_numbers import resolve_form_number


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
    selected_pdf = preferred_pdf(pdf.resolve() if pdf else sources.pdf, workspace.path) if (pdf or sources.pdf) else None
    if len(pdf_candidates) > 1 and pdf is None:
        raise ValueError(f"Multiple PDF sources found in {workspace.path}; choose one explicitly.")
    if not selected_pdf:
        raise FileNotFoundError(f"No PDF found in {workspace.path}")

    scripts = config.scripts_root
    runner = PipelineRunner(scripts)
    artifacts = []
    selected_answer_key = answer_key or (sources.answer_keys[0] if sources.answer_keys else None)
    selected_form = form
    if selected_form is None:
        try:
            import fitz
            pdf_text = "\n".join(page.get_text() for page in fitz.open(selected_pdf))
        except Exception:
            pdf_text = ""
        resolution = resolve_form_number(pdf_text, selected_pdf.name)
        if resolution.status == "ambiguous":
            raise ValueError("Multiple possible form numbers detected; provide an explicit form override.")
        selected_form = resolution.raw_value
    if selected_answer_key:
        if not selected_form:
            selected_form = config.default_form or "0"
        answers = workspace.path / "answers.json"
        runner.extract_answers(selected_answer_key, selected_form, answers)
        artifacts.append(answers)
    if selected_form and not selected_answer_key:
        # Retain detected form metadata even when no official key is supplied.
        pass
    if classify_pdf(selected_pdf, workspace=workspace.path):
        raw = workspace.path / "raw_text.md"
        images = workspace.path / "images"
        page_map = workspace.path / "page_map.json"
        runner.extract_text(selected_pdf, raw, images, page_map)
        markdown = workspace.path / "questions.md"
        runner.parse_questions(raw, markdown, images, page_map)
        if selected_form:
            from .form_numbers import FormCandidate, FormResolution
            from .markdown import dump_questions
            questions = load_questions(markdown)
            normalized = str(int(selected_form))
            resolution = FormResolution(
                FormCandidate(str(selected_form), normalized, "manual-override" if form else "pdf-content", 1.0, "PDF form metadata", normalized == "0"),
                (),
                "resolved",
                bool(form),
            )
            markdown.write_text(dump_questions(questions, resolution), encoding="utf-8")
        artifacts.extend((raw, markdown))
    else:
        pages = workspace.path / "pages_output"
        merged = workspace.path / f"{workspace.name}_clean.pdf"
        runner.render_pages(selected_pdf, pages, config.default_discard_pages, merged)
        # Keep the full rendered pages available so questions.md can reference
        # a complete page for the web cropper.
        artifacts.extend((pages, merged))

    if workspace.questions_path.exists():
        has_answers = bool(selected_answer_key) or (workspace.path / "answers.json").is_file() or (workspace.path / "answers.md").is_file()
        if has_answers:
            runner.merge_answers(workspace.path)
        runner.validate(workspace.questions_path)
        questions = load_questions(workspace.questions_path)
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
    selected_form = form
    if selected_form is None and sources.pdf:
        try:
            import fitz
            text = "\n".join(page.get_text() for page in fitz.open(sources.pdf))
        except Exception:
            text = ""
        resolution = resolve_form_number(text, sources.pdf.name)
        selected_form = resolution.raw_value or config.default_form
    selected_form = selected_form or config.default_form
    runner = PipelineRunner(config.scripts_root)
    return generate_prompt(runner, workspace.path, workspace.name, selected_form, bool(sources.answer_keys), kind)


def validate_questions(path: Path) -> int:
    return len(load_questions(path))


def clean_workspace(path: Path) -> int:
    return len(clean_scratch(Workspace(path.name, path.resolve())))


def build_workspace(config: Config, path: Path, output: Path | None = None) -> Path:
    return build_standalone_quiz(path.resolve(), config.scripts_root, output)
