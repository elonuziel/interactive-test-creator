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

def parse_page_ranges(pages_str, total_pages=0):
    """
    Parses a string like '1-4,6,8,10' or 'std'/'standard' into a set of 1-indexed integers.
    Standard cleaning ('std'): discards pages 1-4, then every even page (6, 8, 10...) up to total_pages.
    """
    if not pages_str:
        return set()

    clean_str = pages_str.strip().lower()

    if clean_str in {"std", "standard", "default"}:
        discard_set = {1, 2, 3, 4}
        if total_pages >= 6:
            discard_set.update(range(6, total_pages + 1, 2))
        return discard_set

    if clean_str in {"none", "n", "off"}:
        return set()

    discard_set = set()
    parts = pages_str.split(',')
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            try:
                start, end = map(int, part.split('-'))
                discard_set.update(range(start, end + 1))
            except ValueError:
                print(f"Warning: Could not parse page range '{part}'")
        else:
            try:
                discard_set.add(int(part))
            except ValueError:
                print(f"Warning: Could not parse page number '{part}'")
    return discard_set

def main():
    parser = argparse.ArgumentParser(description="Render PDF pages as images (useful for Scanned PDFs).")
    parser.add_argument("pdf_file", help="Path to the PDF file")
    parser.add_argument("-o", "--outdir", help="Output directory for images", default="pages")
    parser.add_argument("--dpi", type=int, default=150, help="DPI for the rendered images")
    parser.add_argument("--discard-pages", type=str, default="",
                        help="Comma-separated list of 1-indexed pages/ranges ('1-4,6,8'), 'std' for standard cleaning, or 'none'")
    parser.add_argument("--merged-pdf", help="Optional path to output a merged PDF containing only non-blank pages", default=None)
    
    args = parser.parse_args()

    try:
        doc = fitz.open(args.pdf_file)
    except Exception as e:
        print(f"Error opening PDF: {e}")
        return

    os.makedirs(args.outdir, exist_ok=True)
    
    clean_doc = fitz.open() if args.merged_pdf else None

    pages_to_discard = parse_page_ranges(args.discard_pages, total_pages=len(doc))

    rendered_count = 0
    skipped_count = 0

    for i, page in enumerate(doc):
        page_num = i + 1
        filename = os.path.join(args.outdir, f"page_{page_num}.png")
        
        if page_num in pages_to_discard:
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
        os.makedirs(os.path.dirname(os.path.abspath(args.merged_pdf)) or '.', exist_ok=True)
        clean_doc.save(args.merged_pdf)
        clean_doc.close()
        print(f"Created merged PDF without blank pages: '{args.merged_pdf}'")

    if skipped_count > 0:
        print(f"Rendered {rendered_count} pages to '{args.outdir}' (discarded {skipped_count} blank page(s)).")
    else:
        print(f"Rendered {rendered_count} pages to '{args.outdir}' directory.")

if __name__ == "__main__":
    main()

