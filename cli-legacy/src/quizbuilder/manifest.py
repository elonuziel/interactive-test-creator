from __future__ import annotations

from pathlib import Path

from .pipeline import PipelineRunner


def generate_manifest(scripts_dir: Path) -> None:
    PipelineRunner(scripts_dir).generate_manifest()
