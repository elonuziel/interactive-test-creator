from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class MarkdownError(ValueError):
    pass


def _parse_answer(val: str) -> int:
    val = val.strip().upper()
    mapping = {
        "A": 0, "B": 1, "C": 2, "D": 3,
        "א": 0, "ב": 1, "ג": 2, "ד": 3,
        "1": 0, "2": 1, "3": 2, "4": 3,
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

    for i, match in enumerate(matches):
        inline_header_text = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        lines = [line.rstrip() for line in block.splitlines()]

        answer_match = re.search(r"(?mi)^(?:Answer|תשובה):\s*([A-Dא-ד1-4])\s*$", block)
        answer = _parse_answer(answer_match.group(1)) if answer_match else 0

        option_indexes = [idx for idx, line in enumerate(lines) if re.match(r"^(?:[-*+]|\d+\.|\([1-4]\)|[א-ד]\.)\s+", line)]
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
            match_opt = re.match(r"^(?:[-*+]|\d+\.|\([1-4]\)|[א-ד]\.)\s*(?:(?:[א-דA-D1-4][\.\)]|\([א-דA-D1-4]\))\s+)?(.*)$", line_str)
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
            item.update(metadata)
            questions.append(item)

    if not questions:
        raise MarkdownError("Questions Markdown must contain at least one valid question with options.")
    return questions


def dump_questions(questions: list[dict[str, Any]]) -> str:
    sections: list[str] = ["# Quiz Questions", ""]
    for index, item in enumerate(questions, 1):
        sections.extend([f"## Question {index}", ""])
        img = item.get("image") or item.get("pageImage")
        if img:
            sections.extend([f"image: {img}", ""])
        sections.extend([str(item.get("question", "")).strip(), ""])
        for option in item.get("options", []):
            sections.append(f"- {str(option).strip()}")
        answer = int(item.get("correctIndex", 0))
        sections.extend(["", f"Answer: {chr(ord('A') + answer)}"])
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


def write_questions(path: Path, questions: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_questions(questions), encoding="utf-8")
