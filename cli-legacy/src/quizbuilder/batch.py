from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
        workspace = Workspace(path.name, path)
        sources = discover_sources(workspace)
        issues: list[str] = []
        pdf_count = sum(
            1 for item in path.iterdir()
            if item.is_file() and item.suffix.lower() == ".pdf"
        )
        if pdf_count > 1:
            issues.append("multiple PDF sources; choose one")
        if len(sources.answer_keys) > 1:
            issues.append("multiple answer keys; choose one")
        if not workspace.questions_path.is_file():
            issues.append("questions.json is missing")
        candidates.append(BatchCandidate(workspace, sources, tuple(issues)))
    return candidates
