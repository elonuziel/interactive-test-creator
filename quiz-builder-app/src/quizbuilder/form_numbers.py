from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


@dataclass(frozen=True)
class FormCandidate:
    raw_value: str
    normalized_value: str
    source: str
    confidence: float
    context: str = ""
    is_form_zero: bool = False


@dataclass(frozen=True)
class FormResolution:
    candidate: FormCandidate | None
    candidates: tuple[FormCandidate, ...] = ()
    status: str = "missing"  # resolved, missing, ambiguous
    was_overridden: bool = False

    @property
    def raw_value(self) -> str | None:
        return self.candidate.raw_value if self.candidate else None

    @property
    def normalized_value(self) -> str | None:
        return self.candidate.normalized_value if self.candidate else None

    @property
    def is_form_zero(self) -> bool:
        return bool(self.candidate and self.candidate.is_form_zero)


_LABEL_RE = re.compile(
    r"(?:מבחן\s*(?:מספר|מס['׳״\"]?|no\.?|number)?|"
    r"מספר\s+מבחן|שאלון|טופס|form|test|exam\s*(?:no\.?|number)?)"
    r"[^\d]{0,24}(\d{1,})",
    re.IGNORECASE,
)


def normalize_form_number(value: str | int | None) -> str | None:
    if value is None:
        return None
    match = re.search(r"\d+", str(value).strip())
    if not match:
        return None
    return str(int(match.group(0)))


def _candidate(raw: str, source: str, confidence: float, context: str) -> FormCandidate:
    normalized = normalize_form_number(raw)
    assert normalized is not None
    return FormCandidate(raw, normalized, source, confidence, context, normalized == "0")


def detect_form_candidates(text: str = "", filename: str = "") -> tuple[FormCandidate, ...]:
    candidates: list[FormCandidate] = []
    text = str(text or "")
    filename = str(filename or "")
    for match in _LABEL_RE.finditer(text):
        context = text[max(0, match.start() - 30):min(len(text), match.end() + 30)].strip()
        # The broad "מבחן" alternative can match inside "קוד מבחן"; inspect
        # the actual label span, not surrounding text from another header.
        label_start = match.start()
        if re.search(r"קוד\s+מבחן\s*$", text[max(0, label_start - 12):match.start(1)], re.IGNORECASE):
            continue
        candidates.append(_candidate(match.group(1), "pdf-content", 1.0, context.replace("קוד מבחן", "")))
    for match in _LABEL_RE.finditer(filename):
        context = filename[max(0, match.start() - 20):min(len(filename), match.end() + 20)]
        candidates.append(_candidate(match.group(1), "filename", 0.65, context))

    unique: dict[tuple[str, str], FormCandidate] = {}
    for item in candidates:
        key = (item.normalized_value, item.source)
        if key not in unique or item.confidence > unique[key].confidence:
            unique[key] = item
    return tuple(sorted(unique.values(), key=lambda item: (-item.confidence, item.normalized_value)))


def resolve_form_number(text: str = "", filename: str = "", override: str | None = None) -> FormResolution:
    candidates = detect_form_candidates(text, filename)
    if override is not None and str(override).strip():
        normalized = normalize_form_number(override)
        if normalized is None:
            raise ValueError(f"Invalid form number override: {override}")
        item = _candidate(str(override).strip(), "manual-override", 1.0, "User supplied override")
        return FormResolution(item, candidates, "resolved", True)
    if not candidates:
        return FormResolution(None, (), "missing")
    top = candidates[0]
    close = [item for item in candidates[1:] if top.confidence - item.confidence < 0.15 and item.normalized_value != top.normalized_value]
    if close:
        # Prefer an explicit Form 0/טופס 0 candidate over unrelated numeric
        # metadata such as an exam code when the filename confirms Form 0.
        zero_candidates = [item for item in candidates if item.is_form_zero and item.source == "filename"]
        if zero_candidates:
            return FormResolution(zero_candidates[0], candidates, "resolved")
        return FormResolution(None, candidates, "ambiguous")
    return FormResolution(top, candidates, "resolved")


def form_metadata_lines(resolution: FormResolution) -> list[str]:
    if not resolution.candidate:
        return []
    item = resolution.candidate
    lines = [f"Form number: {item.raw_value}"]
    lines.append(f"Form lookup number: {item.normalized_value}")
    if item.is_form_zero:
        lines.append("Form mode: zero-test (correct answer is option 1; shuffle displayed options)")
    return lines


def metadata_from_markdown(text: str) -> FormResolution:
    form_match = re.search(r"(?mi)^\s*form\s+number\s*:\s*([^\s]+)", text)
    lookup_match = re.search(r"(?mi)^\s*form\s+lookup\s+number\s*:\s*([^\s]+)", text)
    if not form_match:
        return FormResolution(None, (), "missing")
    raw = form_match.group(1)
    normalized = normalize_form_number(lookup_match.group(1) if lookup_match else raw)
    if normalized is None:
        return FormResolution(None, (), "missing")
    candidate = FormCandidate(raw, normalized, "questions.md", 1.0, "questions.md metadata", normalized == "0")
    return FormResolution(candidate, (candidate,), "resolved")
