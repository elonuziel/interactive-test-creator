from __future__ import annotations

from pathlib import Path

from .paths import application_root
from .pipeline import PipelineRunner


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
