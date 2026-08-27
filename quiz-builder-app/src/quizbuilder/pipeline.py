from __future__ import annotations

import contextlib
from dataclasses import dataclass
import io
import os
from pathlib import Path
import runpy
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

        if getattr(sys, "frozen", False):
            return self._run_in_process(script, [str(arg) for arg in args], cwd=cwd)

        result = subprocess.run(
            [sys.executable, str(script), *(str(arg) for arg in args)],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        return StageResult(script_name, result.returncode, result.stdout, result.stderr)

    def _run_in_process(self, script: Path, args: list[str], cwd: Path | None = None) -> StageResult:
        saved_argv = sys.argv
        saved_cwd = os.getcwd()
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        returncode = 0
        try:
            if cwd:
                os.chdir(cwd)
            sys.argv = [str(script), *args]
            with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
                try:
                    runpy.run_path(str(script), run_name="__main__")
                except SystemExit as exc:
                    if isinstance(exc.code, int):
                        returncode = exc.code
                    elif exc.code is not None:
                        returncode = 1
                        stderr_buf.write(str(exc.code))
                except Exception as exc:
                    returncode = 1
                    stderr_buf.write(str(exc))
        finally:
            sys.argv = saved_argv
            if cwd:
                os.chdir(saved_cwd)
        return StageResult(script.name, returncode, stdout_buf.getvalue(), stderr_buf.getvalue())

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

    def extract_answers(self, source: Path, form: str, output: Path) -> StageResult:
        return self.require_success(
            "4_extract_csv_answers.py", str(source), str(form), "-o", str(output)
        )

    def merge_answers(self, workspace: Path) -> StageResult:
        return self.require_success("6_merge_json_answers.py", str(workspace))

    def validate(self, questions: Path) -> StageResult:
        return self.require_success("7_check_questions.py", str(questions))

    def generate_manifest(self) -> StageResult:
        return self.require_success("8_generate_manifest.py")
