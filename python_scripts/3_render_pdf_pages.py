import fitz
import os
import re
import argparse

NOISE_LINE_RE = re.compile(
    r'(?:^עמוד\s+\d+(?:\s+מתוך\s+\d+)?$'       # עמוד 1 מתוך 5 or עמוד 1
    r'|^\d+\s+מתוך\s*\d+\s+עמוד$'              # 1 מתוך 5 עמוד
    r'|^\s*[-–—]?\s*\d+\s*[-–—]?\s*$'          # - 1 - or 1
    r'|^page\s+\d+(?:\s+of\s+\d+)?$)'          # page 1 of 5 or page 1
, re.IGNORECASE)
NOISE_PHRASES = ("קוד מבחן", "מבחן מס'", "מבחן מס", "exam code")

def is_noise_line(line):
    """Check if line is header/footer fluff (page numbers, test codes)."""
    stripped = line.strip()
    if not stripped:
        return True
    if NOISE_LINE_RE.match(stripped):
        return True
    lower_line = stripped.lower()
    for phrase in NOISE_PHRASES:
        if phrase in lower_line:
            return True
    return False

def is_blank_page(page, dpi=150, max_dark_pixels=300, max_dark_ratio=0.0005):
    """
    Determine whether a PyMuPDF page is blank without using AI.
    Combines text/drawing/image analysis with pixmap pixel darkness counts.
    """
    text = page.get_text().strip()
    non_noise_text = []
    if text:
        for line in text.splitlines():
            if not is_noise_line(line):
                non_noise_text.append(line)
    
    meaningful_text = "".join(non_noise_text).strip()
    images = page.get_images()
    drawings = page.get_drawings()
    
    # 1. Digital PDF with meaningful text -> NOT blank
    if len(meaningful_text) > 0:
        return False

    # 2. Digital PDF with no text, no images, and no drawings -> BLANK
    if len(images) == 0 and len(drawings) == 0:
        return True

    # 3. Scanned or vector page (has images/drawings but no text) -> evaluate pixel darkness
    pix = page.get_pixmap(dpi=dpi)
    if pix.n != 1:
        pix_gray = fitz.Pixmap(fitz.csGRAY, pix)
    else:
        pix_gray = pix
    
    samples = pix_gray.samples
    total_pixels = len(samples)
    if total_pixels == 0:
        return True
    
    near_white_count = sum(samples.count(b) for b in range(235, 256))
    dark_pixel_count = total_pixels - near_white_count
    dark_ratio = dark_pixel_count / total_pixels
    
    if dark_pixel_count <= max_dark_pixels or dark_ratio <= max_dark_ratio:
        return True

    return False

def main():
    parser = argparse.ArgumentParser(description="Render PDF pages as images (useful for Scanned PDFs).")
    parser.add_argument("pdf_file", help="Path to the PDF file")
    parser.add_argument("-o", "--outdir", help="Output directory for images", default="pages")
    parser.add_argument("--dpi", type=int, default=150, help="DPI for the rendered images")
    parser.add_argument("--discard-blank", action="store_true", default=True,
                        help="Automatically discard blank pages without AI (default: True)")
    parser.add_argument("--keep-blank", dest="discard_blank", action="store_false",
                        help="Keep all pages including blank ones")
    parser.add_argument("--merged-pdf", help="Optional path to output a merged PDF containing only non-blank pages", default=None)
    
    args = parser.parse_args()

    try:
        doc = fitz.open(args.pdf_file)
    except Exception as e:
        print(f"Error opening PDF: {e}")
        return

    os.makedirs(args.outdir, exist_ok=True)
    
    clean_doc = fitz.open() if args.merged_pdf else None

    rendered_count = 0
    skipped_count = 0

    for i, page in enumerate(doc):
        filename = os.path.join(args.outdir, f"page_{i+1}.png")
        is_blank = False
        if args.discard_blank:
            try:
                is_blank = is_blank_page(page, dpi=args.dpi)
            except Exception as err:
                print(f"Warning: Failed to evaluate blank status for page {i+1}: {err}. Retaining page.")
                is_blank = False

        if is_blank:
            print(f"Skipped blank page {i+1} ({filename})")
            skipped_count += 1
            continue

        if clean_doc is not None:
            clean_doc.insert_pdf(doc, from_page=i, to_page=i)

        pix = page.get_pixmap(dpi=args.dpi)
        pix.save(filename)
        print(f"Saved {filename}")
        rendered_count += 1

    if clean_doc is not None:
        os.makedirs(os.path.dirname(os.path.abspath(args.merged_pdf)), exist_ok=True)
        clean_doc.save(args.merged_pdf)
        clean_doc.close()
        print(f"Created merged PDF without blank pages: '{args.merged_pdf}'")

    if skipped_count > 0:
        print(f"Rendered {rendered_count} pages to '{args.outdir}' (discarded {skipped_count} blank page(s)).")
    else:
        print(f"Rendered {rendered_count} pages to '{args.outdir}' directory.")

if __name__ == "__main__":
    main()

