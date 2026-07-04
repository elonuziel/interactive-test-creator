import fitz
import sys
import os
import argparse

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    parser = argparse.ArgumentParser(description="Extract raw text from a Digital PDF.")
    parser.add_argument("pdf_file", help="Path to the PDF file")
    parser.add_argument("-o", "--output", help="Path to the output Markdown file", default=None)
    parser.add_argument("--reverse", action="store_true",
                        help="Reverse Hebrew word order on each line (use only if PyMuPDF outputs visual-order text)")
    parser.add_argument("--first-page-only", action="store_true",
                        help="Extract only the first page (useful for quick inspection before full extraction)")
    
    args = parser.parse_args()

    try:
        doc = fitz.open(args.pdf_file)
    except Exception as e:
        print(f"Error opening PDF: {e}")
        return

    full_text = ""
    pages = doc[:1] if args.first_page_only else doc
    for page in pages:
        full_text += page.get_text() + "\n"

    if args.reverse:
        # Reverse Hebrew word order on each line (needed when PyMuPDF outputs
        # logical Hebrew words in visual left-to-right order on each line).
        lines = full_text.split('\n')
        out_lines = []
        for line in lines:
            if not line.strip():
                out_lines.append(line)
                continue
            words = line.split(' ')
            words.reverse()
            out_lines.append(' '.join(words))
        full_text = '\n'.join(out_lines)

    out_file = args.output
    if not out_file:
        suffix = f"_page1" if args.first_page_only else ""
        out_file = os.path.splitext(args.pdf_file)[0] + f'_extracted{suffix}.md'

    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(full_text)

    action = "extracted"
    if args.reverse:
        action += " (with Hebrew word reversal)"
    print(f"Successfully {action} text to {out_file}")

if __name__ == "__main__":
    main()