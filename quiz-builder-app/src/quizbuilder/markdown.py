from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class MarkdownError(ValueError):
    pass


def load_questions(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MarkdownError(f"Could not read questions file {path}: {exc}") from exc
    questions: list[dict[str, Any]] = []
    blocks = re.split(r"(?m)^##+\s+Question\s+\d+\s*$", text)
    for block in blocks[1:]:
        lines = [line.rstrip() for line in block.strip().splitlines()]
        if not lines:
            continue
        answer_match = re.search(r"(?mi)^Answer:\s*([A-D])\s*$", block)
        answer = ord(answer_match.group(1).upper()) - ord("A") if answer_match else 0
        option_indexes = [i for i, line in enumerate(lines) if re.match(r"^[-*+]\s+", line)]
        if not option_indexes:
            continue
        question_lines = lines[:option_indexes[0]]
        question = " ".join(line.strip() for line in question_lines if line.strip())
        options: list[str] = []
        for index in option_indexes:
            match = re.match(r"^[-*+]\s+(.*)$", lines[index])
            if match:
                options.append(match.group(1).strip())
        metadata: dict[str, Any] = {}
        image_match = re.search(r"(?mi)^pageImage:\s*(\S+)\s*$", block)
        if image_match:
            metadata["pageImage"] = image_match.group(1)
        if question and options:
            item = {"question": question, "options": options, "correctIndex": answer}
            item.update(metadata)
            questions.append(item)
    if not questions:
        raise MarkdownError("Questions Markdown must contain at least one question.")
    return questions


def dump_questions(questions: list[dict[str, Any]]) -> str:
    sections: list[str] = ["# Quiz Questions", ""]
    for index, item in enumerate(questions, 1):
        sections.extend([f"## Question {index}", ""])
        if item.get("pageImage"):
            sections.extend([f"pageImage: {item['pageImage']}", ""])
        sections.extend([str(item.get("question", "")).strip(), ""])
        for option in item.get("options", []):
            sections.append(f"- {str(option).strip()}")
        answer = int(item.get("correctIndex", 0))
        sections.extend(["", f"Answer: {chr(ord('A') + answer)}", ""])
    return "\n".join(sections)


def write_questions(path: Path, questions: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_questions(questions), encoding="utf-8")
