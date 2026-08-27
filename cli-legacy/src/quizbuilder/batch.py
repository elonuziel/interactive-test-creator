from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

from .models import SourceFiles, Workspace
from .workspace import discover_sources


@dataclass(frozen=True)
class BatchCandidate:
    workspace: Workspace
    sources: SourceFiles
    issues: tuple[str, ...] = ()

    @property
    def ready_to_run(self) -> bool:
        return self.workspace.questions_path.is_file() and not self.issues


def exam_variant(filename: str) -> str | None:
    """Return the Moed variant encoded in a Hebrew or English filename."""

    normalized = re.sub(r"[._'\-]+", " ", filename.casefold())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if re.search(r"(?:מועד|moed)\s*(?:א|a)(?=$|[\s_-]|\d)", normalized) or re.search(r"(?:^|[\s_-]|\d)(?:a)(?=$|[\s_-]|\d)", normalized):
        return "a"
    if re.search(r"(?:מועד|moed)\s*(?:ב|b)(?=$|[\s_-]|\d)", normalized) or re.search(r"(?:^|[\s_-]|\d)(?:b)(?=$|[\s_-]|\d)", normalized):
        return "b"
    if re.search(r"\d[אב](?=$|[\s_-]|\d)", normalized):
        return "a" if normalized[-1] == "א" else "b"
    return None


def match_answer_keys(pdf: Path, answer_keys: tuple[Path, ...]) -> tuple[Path, ...]:
    """Match answer keys to a PDF's Moed variant when the match is unique."""

    variant = exam_variant(pdf.stem)
    if variant is None:
        return answer_keys
    matches = tuple(key for key in answer_keys if exam_variant(key.stem) == variant)
    return matches


def discover_batch(root: Path) -> list[BatchCandidate]:
    """Discover independent test projects without selecting files implicitly."""

    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Projects folder not found: {root}")

    candidates: list[BatchCandidate] = []
    for path in sorted(
        (item for item in root.iterdir() if item.is_dir() and item.name != "runs"),
        key=lambda item: item.name.lower(),
    ):
        pdfs = sorted(
            (item for item in path.iterdir() if item.is_file() and item.suffix.lower() == ".pdf"),
            key=lambda item: item.name.lower(),
        )
        answers = tuple(
            sorted(
                (item for item in path.iterdir() if item.is_file() and item.suffix.lower() in {".csv", ".xls", ".xlsx"}),
                key=lambda item: item.name.lower(),
            )
        )
        if len(pdfs) > 1 and not (path / "questions.json").is_file():
            projects_root = path / ".quizbuilder"
            project_candidates = [(pdf, projects_root / _project_slug(pdf.stem)) for pdf in pdfs]
        else:
            project_candidates = [(None, path)]

        for source_pdf, project_path in project_candidates:
            project_name = path.name if source_pdf is None else f"{path.name} - {source_pdf.stem}"
            matched_answers = match_answer_keys(source_pdf, answers) if source_pdf else answers
            workspace = Workspace(project_name, project_path, source_pdf, matched_answers)
            sources = discover_sources(workspace)
            issues: list[str] = []
            if source_pdf is None and len(pdfs) > 1:
                issues.append("multiple PDF sources; choose one")
            if len(matched_answers) > 1:
                issues.append("multiple answer keys; choose one")
            elif source_pdf and exam_variant(source_pdf.stem) and not matched_answers and answers:
                issues.append("no answer key matches this Moed variant")
            if not workspace.questions_path.is_file():
                issues.append("questions.json is missing")
            candidates.append(BatchCandidate(workspace, sources, tuple(issues)))
    return candidates


def _project_slug(stem: str) -> str:
    slug = re.sub(r"[^\w.-]+", "_", stem, flags=re.UNICODE).strip("._")
    digest = hashlib.sha1(stem.encode("utf-8")).hexdigest()[:8]
    return f"{slug or 'exam'}-{digest}"
