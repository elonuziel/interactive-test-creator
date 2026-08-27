from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class Workspace:
    name: str
    path: Path

    @property
    def questions_path(self) -> Path:
        return self.path / "questions.json"


@dataclass(frozen=True)
class SourceFiles:
    pdf: Path | None = None
    docx: tuple[Path, ...] = ()
    answer_keys: tuple[Path, ...] = ()


@dataclass(frozen=True)
class PipelineResult:
    workspace: Workspace
    success: bool
    artifacts: tuple[Path, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProviderChoice:
    id: str
    label: str
    kind: Literal["local", "freebuff", "web"]
    command: str | None = None
    url: str | None = None
