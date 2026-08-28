from __future__ import annotations

from pathlib import Path


class PreviewError(RuntimeError):
    pass


def render_pdf_page(pdf_path: Path, page_number: int = 0, scale: float = 1.5) -> bytes:
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz
        except ImportError as exc:
            raise PreviewError("PDF preview requires PyMuPDF.") from exc

    try:
        document = fitz.open(pdf_path)
    except (OSError, RuntimeError) as exc:
        raise PreviewError(f"Could not open PDF for preview: {pdf_path}") from exc
    try:
        if page_number < 0 or page_number >= len(document):
            raise PreviewError(f"PDF page {page_number + 1} is outside the document.")
        page = document.load_page(page_number)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        return pixmap.tobytes("png")
    finally:
        document.close()
