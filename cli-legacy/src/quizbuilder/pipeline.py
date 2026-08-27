from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys


@dataclass(frozen=True)
class StageResult:
    name: str
    returncode: int
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class PipelineError(RuntimeError):
    pass


class PipelineRunner:
    """Run pipeline stages without coupling them to terminal presentation."""

    def __init__(self, scripts_dir: Path):
        self.scripts_dir = scripts_dir

    def run(self, script_name: str, *args: str, cwd: Path | None = None) -> StageResult:
        script = self.scripts_dir / script_name
        if not script.is_file():
            raise PipelineError(f"Pipeline script not found: {script}")
        result = subprocess.run(
            [sys.executable, str(script), *(str(arg) for arg in args)],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        return StageResult(script_name, result.returncode, result.stdout, result.stderr)

    def require_success(self, script_name: str, *args: str, cwd: Path | None = None) -> StageResult:
        result = self.run(script_name, *args, cwd=cwd)
        if not result.ok:
            detail = (result.stderr or result.stdout or "unknown pipeline error").strip()
            raise PipelineError(f"Pipeline stage {script_name} failed: {detail}")
        return result

    def detect_pdf(self, pdf: Path) -> StageResult:
        return self.run("1_detect_pdf_type.py", str(pdf))

    def extract_text(self, pdf: Path, output: Path, image_dir: Path, page_map: Path) -> StageResult:
        return self.require_success(
            "2_extract_text_fitz.py", str(pdf), "-o", str(output),
            "--extract-images", str(image_dir), "--page-map", str(page_map),
        )

    def render_pages(self, pdf: Path, output_dir: Path, discard_pages: str, merged_pdf: Path) -> StageResult:
        return self.require_success(
            "3_render_pdf_pages.py", str(pdf), "-o", str(output_dir),
            "--discard-pages", discard_pages, "--merged-pdf", str(merged_pdf),
        )

    def parse_questions(self, source: Path, output: Path, image_dir: Path, page_map: Path) -> StageResult:
        return self.require_success(
            "5_parse_questions_md.py", str(source), "-o", str(output),
            "--image-dir", str(image_dir), "--page-map", str(page_map),
        )

    def merge_answers(self, workspace: Path) -> StageResult:
        return self.require_success("6_merge_json_answers.py", str(workspace))

    def validate(self, questions: Path) -> StageResult:
        return self.require_success("7_check_json.py", str(questions))

    def generate_manifest(self) -> StageResult:
        return self.require_success("8_generate_manifest.py")
