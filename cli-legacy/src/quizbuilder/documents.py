from __future__ import annotations

from pathlib import Path
import shutil
import subprocess


class DocumentError(RuntimeError):
    pass


def find_soffice() -> str | None:
    candidate = shutil.which("soffice")
    if candidate:
        return candidate
    if __import__("sys").platform == "win32":
        for path in (
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ):
            if Path(path).is_file():
                return path
    return None


def detect_docx_converter() -> tuple[str | None, str | None]:
    soffice = find_soffice()
    if soffice:
        return "soffice", soffice
    return None, None


def convert_docx_to_pdf_with_soffice(soffice_path: str, docx_path: str, output_dir: str) -> tuple[bool, str]:
    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [soffice_path, "--headless", "--convert-to", "pdf:writer_pdf_Export", "--outdir", output_dir, docx_path],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        expected_pdf = Path(output_dir) / f"{Path(docx_path).stem}.pdf"
        if result.returncode == 0 and expected_pdf.is_file():
            return True, "ok"
        detail = (result.stderr or result.stdout or "conversion failed").strip()
        return False, detail
    except Exception as exc:
        return False, str(exc)


def convert_docx_batch(
    docx_files: list[str],
    work_dir: str,
    backend_name: str,
    backend_value: str,
    overwrite_existing: bool = False,
) -> dict:
    converted: list[tuple[str, str]] = []
    skipped: list[tuple[str, str]] = []
    failed: list[tuple[str, str]] = []

    work_dir_path = Path(work_dir)
    for docx_name in docx_files:
        docx_path = work_dir_path / docx_name
        expected_pdf = work_dir_path / f"{docx_path.stem}.pdf"

        if expected_pdf.exists() and not overwrite_existing:
            skipped.append((docx_name, "matching PDF already exists"))
            continue

        try:
            if backend_name == "soffice":
                ok, msg = convert_docx_to_pdf_with_soffice(backend_value, str(docx_path), str(work_dir_path))
            else:
                ok, msg = False, "no conversion backend configured"
        except Exception as exc:
            ok, msg = False, str(exc)

        if ok and expected_pdf.is_file():
            converted.append((docx_name, expected_pdf.name))
        else:
            failed.append((docx_name, msg or "unknown conversion error"))

    return {
        "converted": converted,
        "skipped": skipped,
        "failed": failed,
    }


def convert_docx_with_soffice(source: Path, output_dir: Path) -> Path:
    soffice = find_soffice()
    if not soffice:
        raise DocumentError("LibreOffice (soffice) was not found; convert the DOCX to PDF manually.")
    output_dir.mkdir(parents=True, exist_ok=True)
    ok, msg = convert_docx_to_pdf_with_soffice(soffice, str(source), str(output_dir))
    output = output_dir / f"{source.stem}.pdf"
    if not ok or not output.is_file():
        raise DocumentError(f"DOCX conversion failed: {msg}")
    return output


def classify_pdf(pdf_path: Path, minimum_chars_per_page: int = 50) -> bool:
    """Return True when the PDF contains enough extractable text to be digital."""
    try:
        import fitz
    except ImportError as exc:
        raise DocumentError("PyMuPDF is required for PDF classification.") from exc

    try:
        document = fitz.open(pdf_path)
        pages = min(3, len(document))
        if not pages:
            return False
        characters = sum(len(document[index].get_text().strip()) for index in range(pages))
        return characters / pages >= minimum_chars_per_page
    except Exception as exc:
        raise DocumentError(f"Could not inspect PDF {pdf_path}: {exc}") from exc
