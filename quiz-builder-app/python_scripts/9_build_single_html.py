"""
9_build_single_html.py — Build a single self-contained HTML quiz file.

Merges index.html, style.css, app.js, questions.md, and optionally images
into one standalone HTML file that works by double-clicking (no server needed).

Usage:
    python 9_build_single_html.py tests/2019_a
    python 9_build_single_html.py tests/2019_a -o "botany_2019a.html"
    python 9_build_single_html.py tests/2019_a --no-images
"""

import argparse
import base64
import json
import mimetypes
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/src')
from quizbuilder.markdown import load_questions as load_markdown_questions
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Resolve paths relative to the repo root & PyInstaller _MEIPASS
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CLI_LEGACY_DIR = os.path.dirname(SCRIPT_DIR) if os.path.basename(SCRIPT_DIR) == 'python_scripts' else SCRIPT_DIR

def resolve_web_asset(filename):
    """Find template assets (index.html, style.css, app.js) strictly inside quiz-builder-app/web/."""
    frozen_base = getattr(sys, '_MEIPASS', None)
    candidates = []
    if frozen_base:
        candidates.extend([
            os.path.join(frozen_base, 'quiz-builder-app', 'web', filename),
            os.path.join(frozen_base, 'web', filename),
            os.path.join(frozen_base, filename),
        ])
    candidates.extend([
        os.path.join(CLI_LEGACY_DIR, 'web', filename),
        os.path.join(SCRIPT_DIR, filename),
    ])

    for cand in candidates:
        if os.path.isfile(cand):
            return cand
    raise FileNotFoundError(f"Template asset '{filename}' not found in bundle or disk.")

def read_file(path, encoding='utf-8'):
    """Read and return file contents as a string."""
    with open(path, 'r', encoding=encoding) as f:
        return f.read()

def read_binary(path):
    """Read and return file contents as bytes."""
    with open(path, 'rb') as f:
        return f.read()

def image_to_data_uri(image_path):
    """Convert an image file to a base64 data URI."""
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type:
        mime_type = 'image/png'
    data = read_binary(image_path)
    b64 = base64.b64encode(data).decode('ascii')
    return f"data:{mime_type};base64,{b64}"

def process_questions(questions, test_dir, embed_images=True):
    """
    Process questions.json: optionally convert image paths to data URIs.
    Returns the processed questions list and total image bytes embedded.
    """
    total_img_bytes = 0

    for q in questions:
        for field in ('image', 'pageImage'):
            img_path = q.get(field)
            if not img_path:
                continue

            if embed_images:
                # Resolve relative to the test directory
                abs_path = os.path.join(test_dir, img_path)
                if os.path.isfile(abs_path):
                    total_img_bytes += os.path.getsize(abs_path)
                    q[field] = image_to_data_uri(abs_path)
                else:
                    print(f"  Warning: image file not found: {abs_path}")
            else:
                # Strip image fields when --no-images is used
                q[field] = None

    # Clean up None values
    for q in questions:
        for field in ('image', 'pageImage'):
            if q.get(field) is None and field in q:
                del q[field]

    return questions, total_img_bytes

def build_html(test_dir, embed_images=True, title=None):
    """Build a self-contained HTML string from the web app + test data."""

    # ── Read source files ──────────────────────────────────────────────────
    html_path = resolve_web_asset('index.html')
    css_path = resolve_web_asset('style.css')
    js_path = resolve_web_asset('app.js')
    questions_path = os.path.join(test_dir, 'questions.md')
    legacy_path = os.path.join(test_dir, 'questions.json')
    if not os.path.isfile(questions_path):
        questions_path = legacy_path
    if not os.path.isfile(questions_path):
        raise FileNotFoundError(f"questions.md not found in {test_dir}")

    html = read_file(html_path)
    css = read_file(css_path)
    js = read_file(js_path)

    if questions_path.lower().endswith('.md'):
        questions = load_markdown_questions(Path(questions_path))
    else:
        with open(questions_path, 'r', encoding='utf-8') as f:
            questions = json.load(f)

    # ── Process images ─────────────────────────────────────────────────────
    questions, img_bytes = process_questions(questions, test_dir, embed_images)

    # ── Build the embedded questions script ────────────────────────────────
    questions_json = json.dumps(questions, ensure_ascii=False, indent=None)
    embedded_script = f"<script>window.__EMBEDDED_QUESTIONS = {questions_json};</script>"

    # ── Update title if provided ───────────────────────────────────────────
    if title:
        safe_title = title.replace('</title>', '').replace('</TITLE>', '')
        html = re.sub(
            r'<title>.*?</title>',
            f'<title>{safe_title}</title>',
            html
        )

    # ── Inline CSS: replace <link rel="stylesheet" href="style.css"> ──────
    html = re.sub(
        r'<link\s+rel="stylesheet"\s+href="style\.css"\s*/?>',
        lambda _: f'<style>\n{css}\n</style>',
        html
    )

    # ── Inline Cropper.js CSS and JS if available for offline use ─────────
    try:
        cropper_css_path = resolve_web_asset('cropper.min.css')
        cropper_css = read_file(cropper_css_path)
    except FileNotFoundError:
        cropper_css = ''

    try:
        cropper_js_path = resolve_web_asset('cropper.min.js')
        cropper_js = read_file(cropper_js_path)
    except FileNotFoundError:
        cropper_js = ''

    if cropper_css:
        html = re.sub(
            r'<link\s+href="[^"]*cropperjs[^"]*"\s+rel="stylesheet"\s*/?>',
            lambda _: f'<style>\n{cropper_css}\n</style>',
            html
        )
    if cropper_js:
        html = re.sub(
            r'<script\s+src="[^"]*cropperjs[^"]*">\s*</script>',
            lambda _: f'<script>\n{cropper_js}\n</script>',
            html
        )

    # ── Inline JS: replace <script src="app.js"></script> ──────────────────
    html = re.sub(
        r'<script\s+[^>]*src=["\']\.?/?app\.js["\'][^>]*>\s*</script>',
        lambda _: f'{embedded_script}\n<script>\n{js}\n</script>',
        html
    )

    return html, len(questions), img_bytes

def main():
    parser = argparse.ArgumentParser(
        description="Build a single self-contained HTML quiz file from a test directory."
    )
    parser.add_argument(
        'test_dir',
        help="Path to the test directory containing questions.md"
    )
    parser.add_argument(
        '-o', '--output', default=None,
        help="Output HTML file path (default: <test_dir>/<test_name>_interactive_quiz.html)"
    )
    parser.add_argument(
        '--no-images', action='store_true',
        help="Skip embedding images (reduces file size)"
    )
    parser.add_argument(
        '--title', default=None,
        help="Custom title for the HTML page"
    )

    args = parser.parse_args()

    test_dir = args.test_dir
    if not os.path.isdir(test_dir):
        print(f"Error: test directory not found: {test_dir}")
        return 1

    # Derive output filename inside test directory
    test_name = os.path.basename(os.path.normpath(test_dir))
    output_path = args.output or os.path.join(test_dir, f"{test_name}_interactive_quiz.html")

    print(f"Building single-file quiz from: {test_dir}")

    try:
        html, q_count, img_bytes = build_html(
            test_dir,
            embed_images=not args.no_images,
            title=args.title
        )
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    file_size = os.path.getsize(output_path)
    size_str = format_size(file_size)
    img_str = format_size(img_bytes) if img_bytes else "None (0 images referenced in questions)"

    print(f"\n✓ Built successfully: {output_path}")
    print(f"  Questions: {q_count}")
    print(f"  Images embedded: {img_str}")
    print(f"  Total file size: {size_str}")
    print(f"\n  Double-click the file to open the quiz!")

    return 0

def format_size(size_bytes):
    """Format bytes into a human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"

if __name__ == '__main__':
    raise SystemExit(main())
