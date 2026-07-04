import fitz
import sys
import os
import json
import re
import argparse
from collections import defaultdict

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ── Noise patterns (mirrors quiz_builder.js L225) ──────────────────────────
NOISE_LINE_RE = re.compile(
    r'(?:^עמוד\s+\d+\s+מתוך\s+\d+$'            # עמוד 1 מתוך 5
    r'|^\d+\s+מתוך\s*\d+\s+עמוד$)'             # 1 מתוך5 עמוד  (LTR-grouped)
)
NOISE_WORDS = ("קוד מבחן", "מבחן מס'", "מבחן מס")

def is_noise_line(line):
    """Return True if the line is a page-number marker or exam-header fluff."""
    stripped = line.strip()
    if not stripped:
        return True
    if NOISE_LINE_RE.match(stripped):
        return True
    for w in NOISE_WORDS:
        if w in stripped:
            return True
    return False


# ── Smart text grouping (mirrors quiz_builder.js groupPdfTextItemsToLines) ──
def extract_lines_smart(page):
    """
    Use page.get_text("dict") to get positioned text spans,
    group them into lines by y‑coordinate proximity (≤ 2pt tolerance),
    sort lines top‑to‑bottom, and within each line sort spans LTR.
    Returns a list of line strings.
    """
    blocks = page.get_text("dict")["blocks"]
    items = []

    for block in blocks:
        if block["type"] != 0:          # skip image blocks
            continue
        for line_block in block.get("lines", []):
            for span in line_block.get("spans", []):
                text = span["text"].strip()
                if not text:
                    continue
                bbox = span["bbox"]      # (x0, y0, x1, y1)
                items.append({
                    "text": text,
                    "x": bbox[0],        # left edge
                    "y": bbox[1],        # top edge
                })

    if not items:
        return []

    # Sort primary by y (ascending = top of page first), secondary by x (LTR)
    items.sort(key=lambda i: (round(i["y"], 1), i["x"]))

    # Group into lines — tolerance 2pt
    lines = []
    current_line_y = None
    current_line_chunks = []

    for item in items:
        if current_line_y is None or abs(item["y"] - current_line_y) > 2:
            if current_line_chunks:
                current_line_chunks.sort(key=lambda c: c["x"])
                lines.append(" ".join(c["text"] for c in current_line_chunks))
            current_line_y = item["y"]
            current_line_chunks = [item]
        else:
            current_line_chunks.append(item)

    if current_line_chunks:
        current_line_chunks.sort(key=lambda c: c["x"])
        lines.append(" ".join(c["text"] for c in current_line_chunks))

    return lines


# ── Hebrew word‑order helpers ──────────────────────────────────────────────
def reverse_words_line(line):
    """Reverse word order on a single line (for visual→logical correction)."""
    stripped = line.strip()
    if not stripped:
        return line
    words = stripped.split()
    words.reverse()
    return " ".join(words)


def auto_detect_hebrew_order(doc, sample_pages=3):
    """
    Sample the first *sample_pages* pages; count signal patterns.
    Returns True if word‑reversal is needed (visual order detected),
    False if text is already in logical order.
    Mirrors quiz_builder.js maybeFixHebrewWordOrder (L97-112).
    """
    normal_signals = 0
    reversed_signals = 0

    pages_to_check = min(sample_pages, len(doc))
    for i in range(pages_to_check):
        lines = extract_lines_smart(doc[i])
        for line in lines:
            # "שאלה מספר" or "מבחן מס" → logical (normal) order
            if re.search(r'שאלה\s+מספר|מבחן\s+מס', line):
                normal_signals += 1
            # "מספר שאלה" or "מס מבחן" → visual (reversed) order
            if re.search(r'מספר\s+שאלה|מס\s+מבחן', line):
                reversed_signals += 1

    return reversed_signals > normal_signals


# ── Embedded image extraction ──────────────────────────────────────────────
def extract_embedded_images(doc, out_dir):
    """
    Extract all embedded images from every page.
    Saves as page{N}_img{M}.png, handles CMYK→RGB conversion.
    Returns a dict: { page_number: [relative_path, …] }.
    """
    os.makedirs(out_dir, exist_ok=True)
    page_images = defaultdict(list)

    for page_num in range(len(doc)):
        page = doc[page_num]
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            try:
                pix = fitz.Pixmap(doc, xref)
                if pix.n >= 5:                     # CMYK — convert to RGB
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                fname = f"page{page_num + 1}_img{img_index + 1}.png"
                fpath = os.path.join(out_dir, fname)
                pix.save(fpath)
                pix = None
                page_images[page_num + 1].append(fname)
            except Exception as e:
                print(f"  Skipping image xref={xref} on page {page_num+1}: {e}")

    return dict(page_images)


def main():
    parser = argparse.ArgumentParser(description="Extract raw text from a Digital PDF with smart grouping.")
    parser.add_argument("pdf_file", help="Path to the PDF file")
    parser.add_argument("-o", "--output", help="Path to the output Markdown file", default=None)
    parser.add_argument("--extract-images", help="Directory to save embedded images", default=None)
    parser.add_argument("--page-map", help="Output JSON mapping line index → page number", default=None)
    parser.add_argument("--reverse", action="store_true",
                        help="(deprecated) Reverse is auto‑detected now. Use --force-reverse to override.")
    parser.add_argument("--force-reverse", action="store_true",
                        help="Force Hebrew word‑order reversal regardless of auto‑detection.")
    parser.add_argument("--first-page-only", action="store_true",
                        help="Extract only the first page (useful for quick inspection)")

    args = parser.parse_args()

    if args.reverse:
        print("Note: --reverse is deprecated; word‑order is auto‑detected. Use --force-reverse to override.")

    try:
        doc = fitz.open(args.pdf_file)
    except Exception as e:
        print(f"Error opening PDF: {e}")
        return

    # ── Auto‑detect word order (Step 1.2) ──────────────────────────────────
    should_reverse = args.force_reverse or auto_detect_hebrew_order(doc)

    if args.force_reverse:
        print("Word order: forced reversal.")
    elif should_reverse:
        print("Word order: auto‑detected VISUAL (reversed) — applying correction.")
    else:
        print("Word order: auto‑detected LOGICAL — no reversal needed.")

    # ── Extract images (Step 1.3) ──────────────────────────────────────────
    if args.extract_images:
        images_map = extract_embedded_images(doc, args.extract_images)
        total = sum(len(v) for v in images_map.values())
        print(f"Extracted {total} embedded images to '{args.extract_images}'")
    else:
        images_map = {}

    # ── Extract text with smart grouping (Steps 1.1, 1.4) ──────────────────
    pages_range = doc[:1] if args.first_page_only else doc
    all_lines = []
    line_page_map = []          # line_index → page_number (1‑based)

    for page in pages_range:
        page_num = page.number + 1
        lines = extract_lines_smart(page)
        for line in lines:
            if is_noise_line(line):
                continue
            if should_reverse:
                line = reverse_words_line(line)
            all_lines.append(line)
            line_page_map.append(page_num)
        all_lines.append("")    # page separator blank line
        line_page_map.append(page_num)

    full_text = "\n".join(all_lines)

    # ── Write output ───────────────────────────────────────────────────────
    out_file = args.output
    if not out_file:
        suffix = "_page1" if args.first_page_only else ""
        out_file = os.path.splitext(args.pdf_file)[0] + f'_extracted{suffix}.md'

    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(full_text)

    action = "extracted"
    if should_reverse:
        action += " (with Hebrew word reversal)"
    print(f"Successfully {action} text ({len(all_lines)} lines) to {out_file}")

    # ── Write page‑map (Step 1.5) ──────────────────────────────────────────
    if args.page_map:
        # Map: line_{i} → page_number
        pm = {f"line_{i}": line_page_map[i] for i in range(len(line_page_map)) if all_lines[i].strip()}
        with open(args.page_map, 'w', encoding='utf-8') as f:
            json.dump(pm, f, ensure_ascii=False, indent=2)
        print(f"Page map written to {args.page_map}")

    doc.close()


if __name__ == "__main__":
    main()