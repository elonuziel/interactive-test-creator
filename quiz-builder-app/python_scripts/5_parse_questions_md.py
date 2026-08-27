import sys
import json
import re
import os
import argparse
from glob import glob

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ── Patterns (mirrors quiz_builder.js L216–L225) ───────────────────────────
# Step 2.1: robust question detection
Q_PATTERN = re.compile(
    r'(?:^#*\s*שאלה\s+(?:מספר\s+)?:?\d+\s*:?'   # ### שאלה 1:  /  שאלה מספר :1
    r'|^#*\s*(?:מספר\s+)?שאלה\s*:?\s*\d+\s*:?'   # מספר שאלה :1
    r'|\d+\s*:?\s*מספר\s+שאלה'                 # 1 :מספר שאלה
    r'|^\d+\s*[\.\)]\s'                         # 1.  /  1)
    r'|^\d+\s*-\s'                              # 1 -
    r'|^.+\s[\.:]\s*\d+\s*$)'                  # question text ... . 12 / : 12
)

# Step 2.2: dual answer patterns
ANS_START_PATTERN = re.compile(
    r'^(?:[-\*\+\u2022]\s*)?([א-ט1-9])\s*[\.\)]\s*(.*)$'   # - א. text  /  * א) text
)
ANS_START_DOT_FIRST = re.compile(
    r'^[\.\)]\s*([א-ט1-9])\s+(.*)$'            # .א text  (LTR-grouped Hebrew)
)
ANS_END_PATTERN = re.compile(
    r'^(.*)\s+([א-ט1-9])\s*[\.\)]$'           # text א.  /  text א)
)
ANS_END_DOT_FIRST = re.compile(
    r'^(.*)\s+[\.\)]\s*([א-ט1-9])$'           # text .א  (LTR-grouped Hebrew)
)

# Mid‑line answer: letter+period/paren anywhere in the line (not at start)
ANS_MIDLINE_RE = re.compile(
    r'(?:^|.+)'                                 # optional leading text
    r'([א-ט1-9])\s*[\.\)]\s+'                  # א.  /  1)  with trailing space
)

# Step 2.3: noise filtering
NOISE_RE = re.compile(
    r'(?:^עמוד\s+\d+\s+מתוך\s+\d+$'            # עמוד 1 מתוך 5
    r'|^\d+\s+מתוך\s*\d+\s+עמוד$)'             # 1 מתוך5 עמוד  (LTR-grouped)
)
NOISE_WORDS = ("קוד מבחן", "מבחן מס'", "מבחן מס")

# Step 2.4: image keyword detection
IMAGE_KEYWORDS = re.compile(
    r'לפניכם|גרף|תרשים|תמונה|איור|מפה|ציור|דיאגרמה|צילום|טבלה|בטבלה|תרשים|scheme'
)

# Additional chemistry-oriented cues that often imply the answer relies on a visual figure
# even if explicit words like "תרשים" or "איור" are missing in OCR text.
VISUAL_HINT_KEYWORDS = re.compile(
    r'המסומנ|קונפיגורציה|איזומר|איזומריה|IUPAC|NMR|ספקטרום|מנגנון|חיצים|קרבוקטיון|'
    r'המולקול|החומרים הבאים|הבאות|תוצרי התגובה|מה יהיה תוצר|אלקנים|דיאנים|כיראל'
)

ALPHA_REF_OPTION_RE = re.compile(r'^(?:[A-D]|[A-D]\s*ו-\s*[A-D])$')

QUESTION_CUE_RE = re.compile(
    r'מהו|מהי|מה יהיה|מה יהיו|כמה|איזה|מי|למי|מתאר|נכונה|ספקטרום|קונפיגורציה|תוצר'
)


def is_noise(line):
    """Return True if the line is a page-number marker or exam-header fluff."""
    return NOISE_RE.match(line) or any(w in line for w in NOISE_WORDS)


def normalize_whitespace(text):
    """Replace non‑breaking spaces, collapse whitespace, strip. (L288–295)"""
    return re.sub(r'\s+', ' ', text.replace('\u00A0', ' ')).strip()

def clean_option_text(text):
    """
    Same cleanup as clean_question_text but applied to individual answer options.
    """
    text = normalize_whitespace(text)
    # Strip leading stray dots
    text = re.sub(r'^\.(?!\s*[א-ט1-9]\s)', '', text)
    # Strip trailing hyphens
    text = re.sub(r'-\s*$', '', text)
    # Split merged Hebrew+digit / digit+Hebrew
    text = re.sub(r'([א-ת])(\d)', r'\1 \2', text)
    text = re.sub(r'(\d)([א-ת])', r'\1 \2', text)
    return normalize_whitespace(text)


def clean_question_text(text):
    """
    Fix LTR‑grouping artifacts that appear in smart‑extracted Hebrew text:
    - Stray leading dots (e.g. '.(text' → '(text')
    - Trailing hyphens from line‑breaks (e.g. 'text-' → 'text')
    - Dot‑then‑letter merges (e.g. '.א' → 'א.')
    - Misplaced ? and : at start of question → move to end
    - Merged word+digit (e.g. 'הן6' → 'הן 6')
    - Parenthesized content at line start → move to end
    """
    text = normalize_whitespace(text)
    # Strip leading stray dots that aren't part of an answer marker
    text = re.sub(r'^\.(?!\s*[א-ט1-9]\s)', '', text)
    # Strip trailing hyphens (line‑break artifacts)
    text = re.sub(r'-\s*$', '', text)
    # Fix dot‑letter sequences: '.א ' → 'א. ' (LTR artifact)
    text = re.sub(r'\.([א-ט1-9])\s', r'\1. ', text)
    # Split merged Hebrew‑letter + digit: 'הן6' → 'הן 6'
    text = re.sub(r'([א-ת])(\d)', r'\1 \2', text)
    # Split merged digit + Hebrew: '6מיליון' → '6 מיליון'
    text = re.sub(r'(\d)([א-ת])', r'\1 \2', text)

    # Move misplaced ? from start to end: "?text" → "text?"
    if text.startswith('?'):
        text = text[1:] + '?'

    # Move misplaced :( or : from start to end: ":(text" → "text:" / ":text" → "text:"
    if text.startswith(':('):
        text = text[2:] + ':'
    elif text.startswith(':'):
        text = text[1:] + ':'

    return normalize_whitespace(text)

def reverse_words(line):
    """Return the line with word order reversed (for RTL edge‑case matching)."""
    stripped = line.strip()
    if not stripped:
        return ""
    words = stripped.split()
    words.reverse()
    return " ".join(words)


def extract_header_question_text(line):
    """Extract inline question text from a question header line when present."""
    patterns = [
        r'^#*\s*שאלה\s+(?:מספר\s+)?:?\d+\s*:?\s*',
        r'^#*\s*(?:מספר\s+)?שאלה\s*:?\s*\d+\s*:?\s*',
        r'^\d+\s*:?\s*מספר\s+שאלה\s*:?\s*',
        r'^\d+\s*[\.\)]\s*',
        r'^\d+\s*-\s*',
    ]
    for pat in patterns:
        stripped = re.sub(pat, '', line).strip()
        if stripped != line.strip():
            return stripped
    # Handle lines like: "מה התוצר...? . 1" / "... : 12"
    m = re.match(r'^(.*)\s[\.:]\s*\d+\s*$', line.strip())
    if m:
        return m.group(1).strip()
    # Handle lines like: "... מהו ... 23" (trailing question number with no punctuation)
    m = re.match(r'^(.*\S)\s+(\d+)\s*$', line.strip())
    if m and (QUESTION_CUE_RE.search(m.group(1)) or '?' in m.group(1)):
        return m.group(1).strip()
    return ''


def looks_like_trailing_number_question(line):
    """Heuristic for question lines ending with a bare number (e.g., '... 23')."""
    s = line.strip()
    m = re.match(r'^(.*\S)\s+(\d+)\s*$', s)
    if not m:
        return False
    head = m.group(1).strip()
    if ANS_START_PATTERN.match(s) or ANS_START_DOT_FIRST.match(s):
        return False
    if ANS_END_PATTERN.match(s) or ANS_END_DOT_FIRST.match(s):
        return False
    return bool(QUESTION_CUE_RE.search(head) or '?' in head)


def has_alpha_reference_options(options):
    """Detect options that reference figure-labeled choices like A/B/C/D pairs."""
    hits = 0
    for o in options:
        if ALPHA_REF_OPTION_RE.match(o.strip()):
            hits += 1
    return hits >= 2


def extract_page_number_from_text(text):
    """Extract 1-based page number from inline markdown marker like '(עמוד 5)'."""
    if not text:
        return None
    m = re.search(r'\(\s*עמוד\s*(\d+)\s*\)', text)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    return None


def find_images_for_page(page_num, images_dir):
    """Return sorted list of relative image paths for a given page number."""
    if not images_dir or not os.path.isdir(images_dir):
        return []
    pattern = os.path.join(images_dir, f"page{page_num}_img*.png")
    matches = glob(pattern)
    matches.sort()
    # Return relative paths from the images dir
    return [os.path.basename(m) for m in matches]


def try_match_patterns(line):
    """
    Try answer start/end/midline patterns against the line AND its word‑reversed form.
    Returns (letter, text) or (None, None).
    """
    # Try start patterns (letter-first)
    m = ANS_START_PATTERN.match(line)
    if m:
        return m.group(1), (m.group(2) or "").strip()

    # Try start patterns (dot-first, from LTR grouping)
    m = ANS_START_DOT_FIRST.match(line)
    if m:
        return m.group(1), (m.group(2) or "").strip()

    # Try end patterns (letter-last)
    m = ANS_END_PATTERN.match(line)
    if m:
        return m.group(2), (m.group(1) or "").strip()

    # Try end patterns (dot-before-letter, from LTR grouping)
    m = ANS_END_DOT_FIRST.match(line)
    if m:
        return m.group(2), (m.group(1) or "").strip()

    # Try reversed line
    rev = reverse_words(line)
    if rev and rev != line:
        m = ANS_START_PATTERN.match(rev)
        if m:
            return m.group(1), (m.group(2) or "").strip()
        m = ANS_START_DOT_FIRST.match(rev)
        if m:
            return m.group(1), (m.group(2) or "").strip()
        m = ANS_END_PATTERN.match(rev)
        if m:
            return m.group(2), (m.group(1) or "").strip()
        m = ANS_END_DOT_FIRST.match(rev)
        if m:
            return m.group(2), (m.group(1) or "").strip()

    return None, None


def try_split_midline_answer(line, has_question_text=False):
    """
    If the line has an answer marker mid‑line, return (preceding_text, letter, answer_text).
    Otherwise return None.

    When has_question_text is True and the fragment before the answer marker
    looks like content (not a question ending), the fragment is merged into
    the answer text rather than being treated as question continuation.
    """
    m = ANS_MIDLINE_RE.search(line)
    if not m:
        return None
    letter = m.group(1)
    start = m.start(1)      # position of the letter in the line
    before = line[:start].strip()
    # Clean LTR artifacts from the question fragment
    before = re.sub(r'^\.', '', before)          # stray leading dot
    before = re.sub(r'-\s*$', '', before)        # trailing line‑break hyphen
    before = before.strip()
    after = line[start:].strip()
    # Strip the letter+separator from the answer text
    answer_text = re.sub(r'^[א-ט1-9]\s*[\.\)]\s*', '', after).strip()

    # Heuristic: if we already have question text and the fragment looks like
    # answer content (not ending with : or ?), it's likely a multi‑line option
    if has_question_text and before:
        if not re.search(r'[?:]\s*$', before):
            # Restore trailing hyphen (it's a word‑join hyphen like דו-חמצני, not a line‑break artifact)
            if re.search(r'-\s*$', line[:start]):
                before = before + "-"
            # Merge fragment into the answer; answer_text comes first (RTL verb→object order)
            answer_text = (answer_text + " " + before).strip()
            before = ""

    return before, letter, answer_text


def main():
    parser = argparse.ArgumentParser(
        description="Parse extracted Hebrew Markdown into structured JSON with smart detection."
    )
    parser.add_argument("md_file", help="Path to the Markdown file")
    parser.add_argument("-o", "--output", help="Output Markdown file", default="questions.md")
    parser.add_argument("--image-dir", help="Directory containing extracted images (from 2_extract_text_fitz)", default=None)
    parser.add_argument("--page-map", help="JSON file mapping line index → page number (from 2_extract_text_fitz)", default=None)
    parser.add_argument("--include-source-page", action="store_true",
                        help="Include 'sourcePage' field in output JSON for debugging")

    args = parser.parse_args()

    # ── Load page map ──────────────────────────────────────────────────────
    page_map = {}
    if args.page_map:
        try:
            with open(args.page_map, 'r', encoding='utf-8') as f:
                page_map = json.load(f)
        except Exception as e:
            print(f"Warning: could not load page map: {e}")

    # ── Read input ─────────────────────────────────────────────────────────
    try:
        with open(args.md_file, 'r', encoding='utf-8') as f:
            raw_lines = f.readlines()
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    # ── Parse loop (mirrors quiz_builder.js L220–L284) ─────────────────────
    questions = []
    current_q = None
    state = 0          # 0=looking for Q, 1=in question text, 2=in answer options
    line_index = 0     # track position for page‑map lookup

    for raw_line in raw_lines:
        line = raw_line.strip()
        line_index += 1

        # Ignore markdown code fence markers if an AI wrapped output in ```markdown ... ```.
        if line.startswith('```'):
            continue

        if not line or is_noise(line):
            continue

        # ── Question detection ─────────────────────────────────────────────
        if Q_PATTERN.match(line) or Q_PATTERN.match(reverse_words(line)) or looks_like_trailing_number_question(line):
            if current_q:
                questions.append(current_q)
            current_q = {
                'text': [],
                'answers': [],
                # page_map keys are always plain number strings (e.g. "42")
                'source_page': page_map.get(str(line_index)),
            }
            inline_q_text = extract_header_question_text(line)
            if inline_q_text:
                current_q['text'].append(inline_q_text)
                if current_q.get('source_page') is None:
                    current_q['source_page'] = extract_page_number_from_text(inline_q_text)
            state = 1
            continue

        if not current_q:
            continue

        # ── Answer detection ───────────────────────────────────────────────
        if state >= 1:
            letter, text = try_match_patterns(line)

            if letter is not None:
                state = 2
                # Edge case: 'א.' appears alone, its text was the last line of question
                if letter in ('א', '1') and not text and current_q['text']:
                    last_line = current_q['text'][-1].strip()
                    # Do not steal actual question headers/text when options are image-only.
                    if not (
                        Q_PATTERN.match(last_line)
                        or looks_like_trailing_number_question(last_line)
                        or QUESTION_CUE_RE.search(last_line)
                        or '?' in last_line
                    ):
                        text = current_q['text'].pop()
                current_q['answers'].append({'label': letter, 'text': [text] if text else []})
            elif state == 1:
                # Try mid‑line split: option א stuck to question body
                split = try_split_midline_answer(line, has_question_text=bool(current_q['text']))
                if split:
                    before, letter, answer_text = split
                    if before:
                        current_q['text'].append(before)
                    state = 2
                    current_q['answers'].append({'label': letter, 'text': [answer_text] if answer_text else []})
                else:
                    current_q['text'].append(line)
            elif state == 2:
                if current_q['answers']:
                    current_q['answers'][-1]['text'].append(line)

    if current_q:
        questions.append(current_q)

    # ── Format output (Steps 2.4 + 2.5) ────────────────────────────────────
    formatted = []
    for q in questions:
        question_text = clean_question_text(" ".join(q['text']))
        options = []
        for a in q['answers']:
            opt_text = clean_option_text(" ".join(a.get('text', [])))
            if not opt_text and a.get('label'):
                # Keep image-only options parseable and visible in the player.
                opt_text = f"ראה אפשרות {a['label']} בתמונה"
            options.append(opt_text)
        # Filter empty options
        options = [o for o in options if o]
        # Visual content may appear only in options or in chemistry-reference wording.
        has_visual_content = (
            bool(IMAGE_KEYWORDS.search(question_text))
            or any(IMAGE_KEYWORDS.search(o) for o in options)
            or bool(VISUAL_HINT_KEYWORDS.search(question_text))
            or has_alpha_reference_options(options)
        )

        if not question_text:
            continue

        # Keep coverage high for image-heavy OCR where option text may be blank.
        if len(options) < 2:
            label_to_text = {}
            for a in q['answers']:
                lbl = a.get('label')
                txt = clean_option_text(" ".join(a.get('text', [])))
                if lbl and txt:
                    label_to_text[lbl] = txt

            fallback_labels = ('א', 'ב', 'ג', 'ד')
            options = []
            for lbl in fallback_labels:
                txt = label_to_text.get(lbl)
                options.append(txt if txt else f"ראה אפשרות {lbl} בתמונה")

            has_visual_content = True

        obj = {
            'question':     question_text,
            'options':      options,
            'correctIndex': 0,      # placeholder, updated by answer key
        }

        # ── Image association (Step 2.4) ───────────────────────────────────
        if has_visual_content and args.image_dir:
            page = q.get('source_page')
            if page:
                imgs = find_images_for_page(page, args.image_dir)
                # Try page render as fallback (for vector graphics like tables)
                if not imgs:
                    fallback = os.path.join(args.image_dir, f"page{page}_table.png")
                    if os.path.isfile(fallback):
                        imgs = [f"page{page}_table.png"]
                    else:
                        fallback = os.path.join(args.image_dir, f"page{page}.png")
                        if os.path.isfile(fallback):
                            imgs = [f"page{page}.png"]
                if imgs:
                    obj['image'] = f"images/{imgs[0]}"

        # ── Page image for cropper fallback (only if question has diagram keywords or embedded image) ──
        if has_visual_content or obj.get('image'):
            page = q.get('source_page')
            if page:
                test_dir = os.path.dirname(args.md_file)
                page_png = os.path.join(test_dir, "pages_output", f"page_{page}.png")
                if not os.path.isfile(page_png):
                    page_png = os.path.join(test_dir, "pages_output", f"page{page}.png")
                
                if os.path.isfile(page_png):
                    obj['pageImage'] = f"pages_output/{os.path.basename(page_png)}"
                elif args.image_dir:
                    page_png = os.path.join(args.image_dir, f"page{page}.png")
                    if os.path.isfile(page_png):
                        obj['pageImage'] = f"images/page{page}.png"

        # ── Debug: include source page ─────────────────────────────────────
        if args.include_source_page and q.get('source_page') is not None:
            obj['sourcePage'] = q['source_page']

        formatted.append(obj)

    # ── Write output ───────────────────────────────────────────────────────
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(formatted, f, ensure_ascii=False, indent=2)

    img_note = ""
    if args.image_dir:
        img_count = sum(1 for q in formatted if q.get('image'))
        img_note = f" ({img_count} with images)"

    print(f"Parsed {len(formatted)} questions{img_note} -> {args.output}")


if __name__ == '__main__':
    main()
