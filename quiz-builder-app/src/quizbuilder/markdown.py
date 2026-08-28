from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .form_numbers import FormResolution, form_metadata_lines, metadata_from_markdown, resolve_form_number


class MarkdownError(ValueError):
    pass


NOISE_RE = re.compile(
    r'(?:^עמוד\s+\d+\s+מתוך\s+\d+$'
    r'|^\d+\s+מתוך\s*\d+\s+עמוד$)'
)
NOISE_WORDS = ("קוד מבחן", "מבחן מס'", "מבחן מס")


def normalize_whitespace(text: str) -> str:
    """Replace non-breaking spaces, collapse whitespace, and strip."""
    return re.sub(r"\s+", " ", str(text or "").replace("\u00A0", " ")).strip()


def is_noise_line(line: str) -> bool:
    """Return True if the line is a page-number marker or exam-header noise."""
    line = line.strip()
    return bool(NOISE_RE.match(line) or any(w in line for w in NOISE_WORDS))


def reverse_words(line: str) -> str:
    """Return the line with word order reversed (for RTL edge-case matching)."""
    stripped = line.strip()
    if not stripped:
        return ""
    words = stripped.split()
    words.reverse()
    return " ".join(words)


def clean_option_text(text: str) -> str:
    """Normalize and clean option text artifacts."""
    text = normalize_whitespace(text)
    text = re.sub(r"^\.(?!\s*[א-ט1-9]\s)", "", text)
    text = re.sub(r"-\s*$", "", text)
    text = re.sub(r"([א-ת])(\d)", r"\1 \2", text)
    text = re.sub(r"(\d)([א-ת])", r"\1 \2", text)
    return normalize_whitespace(text)


def clean_question_text(text: str) -> str:
    """Fix LTR-grouping artifacts that appear in extracted Hebrew text."""
    text = normalize_whitespace(text)
    text = re.sub(r"^\.(?!\s*[א-ט1-9]\s)", "", text)
    text = re.sub(r"-\s*$", "", text)
    text = re.sub(r"\.([א-ט1-9])\s", r"\1. ", text)
    text = re.sub(r"([א-ת])(\d)", r"\1 \2", text)
    text = re.sub(r"(\d)([א-ת])", r"\1 \2", text)

    if text.startswith("?"):
        text = text[1:] + "?"

    if text.startswith(":("):
        text = text[2:] + ":"
    elif text.startswith(":"):
        text = text[1:] + ":"

    return normalize_whitespace(text)


def _parse_answer(val: str) -> int:
    val = val.strip().upper()
    mapping = {
        "A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5, "G": 6, "H": 7, "I": 8, "J": 9,
        "א": 0, "ב": 1, "ג": 2, "ד": 3, "ה": 4, "ו": 5, "ז": 6, "ח": 7, "ט": 8, "י": 9,
        "1": 0, "2": 1, "3": 2, "4": 3, "5": 4, "6": 5, "7": 6, "8": 7, "9": 8, "10": 9,
    }
    return mapping.get(val, 0)


def load_questions(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MarkdownError(f"Could not read questions file {path}: {exc}") from exc
    questions: list[dict[str, Any]] = []
    header_pattern = re.compile(r"(?m)^##+\s*(?:Question|שאלה)\s+\d+[.: \t-]*(.*)$", re.IGNORECASE)
    matches = list(header_pattern.finditer(text))
    if not matches:
        raise MarkdownError("Questions Markdown must contain at least one question.")

    metadata_resolution = metadata_from_markdown(text)
    for i, match in enumerate(matches):
        inline_header_text = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        lines = [line.rstrip() for line in block.splitlines()]

        answer_match = re.search(r"(?mi)^(?:Answer|תשובה):\s*([A-Jא-י1-9]|10)\s*$", block)
        answer = _parse_answer(answer_match.group(1)) if answer_match else 0

        option_indexes = [idx for idx, line in enumerate(lines) if re.match(r"^(?:[-*+]|\d+\.|\([1-9]\)|\(10\)|[א-יA-Ja-j]\.)\s+", line)]
        if not option_indexes:
            continue

        body_question_lines = lines[:option_indexes[0]]
        body_question = " ".join(line.strip() for line in body_question_lines if line.strip() and not line.strip().startswith("pageImage:"))

        if inline_header_text and body_question:
            question = f"{inline_header_text} {body_question}"
        elif inline_header_text:
            question = inline_header_text
        elif body_question:
            question = body_question
        else:
            question = f"Question {i + 1}"

        options: list[str] = []
        for idx in option_indexes:
            line_str = lines[idx]
            if re.match(r"(?mi)^(?:Answer|תשובה):", line_str):
                continue
            match_opt = re.match(r"^(?:[-*+]|\d+\.|\([1-9]\)|\(10\)|[א-יA-Ja-j]\.)\s*(?:(?:[א-יA-Ja-j1-9]|10)[\.\)]|\((?:[א-יA-Ja-j1-9]|10)\)\s+)?(.*)$", line_str)
            if match_opt:
                opt_str = match_opt.group(1).strip()
                if opt_str:
                    options.append(opt_str)

        metadata: dict[str, Any] = {}
        image_match = re.search(r"(?mi)^(pageImage|image):\s*(\S+)\s*$", block)
        if image_match:
            metadata[image_match.group(1)] = image_match.group(2)

        explanation_match = re.search(r"(?mi)^(?:Explanation|Rationale|הסבר|נימוק):\s*(.+)$", block)
        if explanation_match:
            metadata["explanation"] = explanation_match.group(1).strip()

        if question and options:
            item = {"question": question, "options": options, "correctIndex": answer}
            if metadata_resolution.is_form_zero:
                item["shuffleOptions"] = True
            item.update(metadata)
            questions.append(item)

    if not questions:
        raise MarkdownError("Questions Markdown must contain at least one valid question with options.")
    return questions


def read_form_metadata(path: Path) -> FormResolution:
    return metadata_from_markdown(path.read_text(encoding="utf-8"))


def dump_questions(questions: list[dict[str, Any]], form_resolution: FormResolution | None = None) -> str:
    sections: list[str] = ["# Quiz Questions", ""]
    if form_resolution and form_resolution.candidate:
        sections.extend(form_metadata_lines(form_resolution))
        sections.append("")
    for index, item in enumerate(questions, 1):
        sections.extend([f"## Question {index}", ""])
        img = item.get("image") or item.get("pageImage")
        if img:
            sections.extend([f"image: {img}", ""])
        sections.extend([str(item.get("question", "")).strip(), ""])
        for option in item.get("options", []):
            sections.append(f"- {str(option).strip()}")
        answer = int(item.get("correctIndex", 0))
        letter = chr(ord('A') + answer) if 0 <= answer < 26 else str(answer + 1)
        sections.extend(["", f"Answer: {letter}"])
        if item.get("explanation"):
            sections.extend(["", f"Explanation: {str(item['explanation']).strip()}"])
        sections.append("")
    return "\n".join(sections)


def validate_image_references(questions: list[dict[str, Any]], base_dir: Path) -> list[str]:
    missing: list[str] = []
    for index, question in enumerate(questions, 1):
        for field in ("image", "pageImage"):
            value = question.get(field)
            if not value or str(value).startswith(("data:", "http://", "https://")):
                continue
            target = Path(str(value))
            if not target.is_absolute():
                target = base_dir / target
            if not target.is_file():
                missing.append(f"Question {index}: {field}={value}")
    return missing


def write_questions(path: Path, questions: list[dict[str, Any]], form_resolution: FormResolution | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_questions(questions, form_resolution), encoding="utf-8")
