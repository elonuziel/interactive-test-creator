from __future__ import annotations

import json
from pathlib import Path


class ValidationError(ValueError):
    pass


def load_questions(path: Path) -> list[dict]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"Could not read questions file {path}: {exc}") from exc
    if not isinstance(payload, list) or not payload:
        raise ValidationError("Questions file must contain a non-empty JSON array.")
    invalid = []
    for index, question in enumerate(payload, 1):
        if not isinstance(question, dict) or not isinstance(question.get("question"), str) or not question["question"].strip() or not isinstance(question.get("options"), list) or not question["options"]:
            invalid.append(index)
    if invalid:
        raise ValidationError(f"Invalid question entries: {', '.join(map(str, invalid))}")
    return payload
