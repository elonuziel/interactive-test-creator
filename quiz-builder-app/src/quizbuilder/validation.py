from __future__ import annotations

import json
from pathlib import Path

from .markdown import MarkdownError, load_questions as load_markdown_questions


class ValidationError(ValueError):
    pass


def questions_path(directory: Path) -> Path:
    markdown = directory / "questions.md"
    return markdown if markdown.is_file() else directory / "questions.json"


def load_questions(path: Path) -> list[dict]:
    try:
        if path.suffix.lower() == ".md":
            payload = load_markdown_questions(path)
        else:
            payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, MarkdownError) as exc:
        raise ValidationError(f"Could not read questions file {path}: {exc}") from exc
    if not isinstance(payload, list) or not payload:
        raise ValidationError("Questions file must contain a non-empty array.")
    invalid = []
    for index, question in enumerate(payload, 1):
        if not isinstance(question, dict) or not isinstance(question.get("question"), str) or not question["question"].strip() or not isinstance(question.get("options"), list) or not question["options"]:
            invalid.append(index)
    if invalid:
        raise ValidationError(f"Invalid question entries: {', '.join(map(str, invalid))}")
    return payload
