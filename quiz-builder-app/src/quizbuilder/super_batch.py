from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from dataclasses import dataclass, field, replace
import json
from pathlib import Path
import re
import threading
from typing import Any, Callable

from .batch import _project_slug, exam_variant, match_answer_keys
from .documents import classify_pdf, clean_pdf
from .markdown import load_questions, write_questions
from .models import Workspace
from .prompts import extract_markdown_from_response, send_to_provider
from .config import Config
from .workspace import discover_sources


@dataclass(frozen=True)
class ExamOverview:
    pdf: Path
    workspace: Path
    name: str
    is_digital: bool | None
    page_count: int | None = None
    test_number: str | None = None
    year: str | None = None
    variant: str | None = None
    confidence: float = 0.0
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnswerKeyCandidate:
    path: Path
    answers: dict[int, str] = field(default_factory=dict)
    score: int = 0


@dataclass
class SuperBatchItem:
    overview: ExamOverview
    answer_keys: tuple[AnswerKeyCandidate, ...] = ()
    selected_answer_key: Path | None = None
    decision: str | None = None
    dedicated_instructions: str = ""
    overwrite: bool = False
    status: str = "pending"
    error: str | None = None


@dataclass(frozen=True)
class SuperBatchPlan:
    root: Path
    items: tuple[SuperBatchItem, ...]


@dataclass(frozen=True)
class SuperBatchResult:
    item: SuperBatchItem
    output: Path | None = None
    success: bool = False
    error: str | None = None


def extract_exam_metadata(text: str, filename: str = "") -> dict[str, str | None]:
    combined = f"{filename}\n{text}"
    number = None
    for pattern in (
        r"(?:test|exam|בחינה|מבחן)\s*(?:number|no\.?|מספר)?\s*[:#-]?\s*(\d{2,})",
        r"שאלון\s*[:#-]?\s*(\d{2,})",
    ):
        match = re.search(pattern, combined, re.IGNORECASE)
        if match:
            number = match.group(1)
            break
    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", combined)
    return {"test_number": number, "year": year_match.group(1) if year_match else None, "variant": exam_variant(filename)}


def _parse_answer_text(text: str) -> dict[int, str]:
    result: dict[int, str] = {}
    bracket_q = re.compile(r"\[(\d+)\]")
    bracket_a = re.compile(r"\{(\d+)\}")
    for line in text.splitlines():
        # Check Form Zero bracket pattern [Q] {A}
        q_m = bracket_q.search(line)
        a_m = bracket_a.search(line)
        if q_m and a_m:
            ans_val = int(a_m.group(1))
            letter = chr(ord("A") + ans_val - 1) if 1 <= ans_val <= 26 else str(ans_val)
            result[int(q_m.group(1))] = letter
            continue
        # Standard line pattern: 1: A, - 1: B, 1. C
        match = re.search(r"(?:^|[-*+]\s*)\b(\d+)\s*[,;:\t.-]\s*([A-Dא-ד1-4])\b", line, re.IGNORECASE)
        if match:
            result[int(match.group(1))] = match.group(2).upper()
    return result


def normalize_answer_key(path: Path) -> dict[int, str]:
    suffix = path.suffix.lower()
    if not path.is_file():
        return {}
    if suffix == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            if isinstance(data, dict):
                norm: dict[int, str] = {}
                for k, v in data.items():
                    if str(k).isdigit():
                        if isinstance(v, int):
                            letter = chr(ord("A") + v - 1) if 1 <= v <= 26 else str(v)
                            norm[int(k)] = letter
                        else:
                            norm[int(k)] = str(v).strip().upper()
                return norm
        except Exception:
            return {}
    elif suffix in {".xlsx", ".xls"}:
        try:
            import pandas as pd
            frame = pd.read_excel(path, header=None)
            raw_text = "\n".join(frame.fillna("").astype(str).apply(lambda row: " ".join(row), axis=1))
            return _parse_answer_text(raw_text)
        except Exception:
            return {}
    elif suffix in {".md", ".csv", ".txt"}:
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            return _parse_answer_text(text)
        except Exception:
            return {}
    return {}


def build_plan(root: Path) -> SuperBatchPlan:
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Projects folder not found: {root}")
    items: list[SuperBatchItem] = []
    # Discover all PDFs
    all_pdfs = [
        p for p in sorted(root.rglob("*.pdf"), key=lambda p: str(p).casefold())
        if ".quizbuilder" not in p.parts and not p.name.casefold().endswith("_clean.pdf")
    ]
    # Group by parent folder to detect multiple PDFs sharing a folder
    by_folder: dict[Path, list[Path]] = {}
    for pdf in all_pdfs:
        by_folder.setdefault(pdf.parent, []).append(pdf)

    for folder, pdfs in by_folder.items():
        is_multi = len(pdfs) > 1 and not (folder / "questions.md").is_file()
        for pdf in pdfs:
            if is_multi:
                workspace = folder / ".quizbuilder" / _project_slug(pdf.stem)
                exam_name = f"{folder.name} - {pdf.stem}"
            else:
                workspace = folder
                exam_name = pdf.stem

            sources = discover_sources(Workspace(folder.name, folder))
            keys = match_answer_keys(pdf, sources.answer_keys) or sources.answer_keys
            candidates = tuple(AnswerKeyCandidate(key, normalize_answer_key(key)) for key in keys)
            metadata = extract_exam_metadata(pdf.stem, pdf.name)
            overview = ExamOverview(
                pdf=pdf,
                workspace=workspace,
                name=exam_name,
                is_digital=None,
                test_number=metadata["test_number"],
                year=metadata["year"],
                variant=metadata["variant"],
                warnings=("PDF classification pending",),
            )
            items.append(SuperBatchItem(overview, candidates))

    return SuperBatchPlan(root, tuple(items))


def classify_plan_item(item: SuperBatchItem) -> SuperBatchItem:
    digital = classify_pdf(item.overview.pdf)
    warnings = tuple(w for w in item.overview.warnings if w != "PDF classification pending")
    item.overview = replace(item.overview, is_digital=digital, warnings=warnings)
    if len(item.answer_keys) == 1:
        item.selected_answer_key = item.answer_keys[0].path
    elif len(item.answer_keys) > 1:
        item.error = "Multiple answer keys require confirmation."
    return item


def zero_test_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**question, "correctIndex": 0} for question in questions]


def strict_questions(path: Path, allow_unanswered: bool = False) -> list[dict[str, Any]]:
    questions = load_questions(path)
    if not questions:
        raise ValueError("Generated questions.md is empty.")
    for index, question in enumerate(questions, 1):
        if not str(question.get("question", "")).strip():
            raise ValueError(f"Question {index} has no text.")
        options = question.get("options", [])
        if len(options) < 2:
            raise ValueError(f"Question {index} must have at least two options.")
        answer = question.get("correctIndex")
        if answer is None:
            if not allow_unanswered:
                raise ValueError(f"Question {index} is missing an answer index.")
        elif not isinstance(answer, int) or not 0 <= answer < len(options):
            raise ValueError(f"Question {index} has an invalid answer index: {answer}.")
    return questions


def generation_prompt(item: SuperBatchItem, context: str, mode: str = "two_phase") -> str:
    key_info = "No answer key selected; follow the decision exactly."
    if item.selected_answer_key:
        normalized = normalize_answer_key(item.selected_answer_key)
        key_summary = f"{len(normalized)} answers loaded from {item.selected_answer_key.name}" if normalized else item.selected_answer_key.name
        key_info = f"Use the normalized answer key ({key_summary}) at: {item.selected_answer_key.resolve()}; do not independently solve answers."

    return f"""You are generating the final canonical questions.md for exam '{item.overview.name}'.
Source PDF Path: {item.overview.pdf.resolve()}
Workspace Directory: {item.overview.workspace.resolve()}
Metadata: test number={item.overview.test_number or 'unknown'}, year={item.overview.year or 'unknown'}, variant={item.overview.variant or 'unknown'}.
Mode: {mode}. Decision: {item.decision or 'use_answer_key'}.
{key_info}
Dedicated instructions: {item.dedicated_instructions or 'none'}.

Instructions:
1. If you have file access tools, inspect the source PDF and workspace files directly.
2. Return ONLY canonical Markdown using the following exact structure for every question:
   ## Question 1
   [Question text here]
   - Option A text
   - Option B text
   - Option C text
   - Option D text
   Answer: A
3. Do NOT include markdown code blocks (```markdown), conversational filler, or explanations.

Document Context Excerpt:
{context}
"""


def default_decision(item: SuperBatchItem) -> str:
    if item.overview.is_digital:
        return "zero_test"
    if item.selected_answer_key:
        return "use_answer_key"
    return "generate_only"


def _context_for_pdf(pdf: Path, is_digital: bool) -> str:
    if not is_digital:
        return f"Scanned/Image PDF located at: {pdf.resolve()}. Inspect the file on disk."
    try:
        import fitz
        document = fitz.open(pdf)
        return "\n".join(page.get_text()[:4000] for page in document[:3])
    except Exception:
        return f"Digital PDF located at: {pdf.resolve()}"


def process_item(
    item: SuperBatchItem,
    provider,
    command: str,
    *,
    ai_mode: str = "two_phase",
    discard_pages: str = "",
    clean_digital: bool = False,
    cancel_event: threading.Event | None = None,
    progress: Callable[[SuperBatchItem], None] | None = None,
) -> SuperBatchResult:
    item.overview.workspace.mkdir(parents=True, exist_ok=True)
    output = item.overview.workspace / "questions.md"
    temporary: Path | None = None
    try:
        if cancel_event and cancel_event.is_set():
            item.status = "cancelled"
            return SuperBatchResult(item, error="Cancelled")
        if output.exists() and not item.overwrite:
            raise FileExistsError(f"questions.md already exists: {output}")
        item.status = "classifying"
        if item.overview.is_digital is None:
            item = classify_plan_item(item)
        if progress:
            progress(item)
        if cancel_event and cancel_event.is_set():
            item.status = "cancelled"
            return SuperBatchResult(item, error="Cancelled")

        pdf = item.overview.pdf
        if item.overview.is_digital:
            if clean_digital and discard_pages:
                cleaned = item.overview.workspace / f"{pdf.stem}_clean.pdf"
                clean_pdf(pdf, cleaned, discard_pages)
                pdf = cleaned
            item.status = "extracting"
            if progress:
                progress(item)
            from .commands import process_workspace
            scripts_root = Path(__file__).resolve().parents[2] / "python_scripts"
            config = Config.defaults(root=item.overview.workspace)
            config.scripts_root = scripts_root
            config.default_discard_pages = discard_pages or config.default_discard_pages
            process_workspace(config, item.overview.workspace, item.selected_answer_key if item.decision == "use_answer_key" else None, "0", pdf)
            if item.decision == "zero_test":
                write_questions(output, zero_test_questions(load_questions(output)))
        else:
            if item.decision == "ask_user":
                raise ValueError("Scanned PDF requires a decision: generate_only, zero_test, or dedicated_instructions")
            item.status = "generating"
            if progress:
                progress(item)
            context = _context_for_pdf(pdf, False)
            response = send_to_provider(
                provider,
                command,
                type("Prompt", (), {"read_text": lambda self, encoding="utf-8": generation_prompt(item, context, ai_mode)})(),
                cwd=item.overview.workspace,
            )
            generated = extract_markdown_from_response(response)
            if not generated.strip():
                raise ValueError("CLI AI returned no Markdown output.")
            temporary = output.with_suffix(".super-batch.tmp.md")
            temporary.write_text(generated, encoding="utf-8")
            strict_questions(temporary, allow_unanswered=(item.decision == "generate_only"))
            temporary.replace(output)
            temporary = None

        strict_questions(output, allow_unanswered=(item.decision == "generate_only"))
        item.status = "saved"
        if progress:
            progress(item)
        return SuperBatchResult(item, output, True)
    except Exception as exc:
        if temporary and temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass
        item.status = "failed"
        item.error = str(exc)
        if progress:
            progress(item)
        return SuperBatchResult(item, error=str(exc))


def process_plan(
    plan: SuperBatchPlan,
    provider,
    command: str,
    *,
    workers: int = 2,
    ai_mode: str = "two_phase",
    discard_pages: str = "",
    clean_digital: bool = False,
    cancel_event: threading.Event | None = None,
    progress: Callable[[SuperBatchItem], None] | None = None,
) -> tuple[SuperBatchResult, ...]:
    if workers <= 1:
        return tuple(
            process_item(
                item,
                provider,
                command,
                ai_mode=ai_mode,
                discard_pages=discard_pages,
                clean_digital=clean_digital,
                cancel_event=cancel_event,
                progress=progress,
            )
            for item in plan.items
        )
    results: list[SuperBatchResult] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                process_item,
                item,
                provider,
                command,
                ai_mode=ai_mode,
                discard_pages=discard_pages,
                clean_digital=clean_digital,
                cancel_event=cancel_event,
                progress=progress,
            )
            for item in plan.items
        ]
        for future in as_completed(futures):
            results.append(future.result())
    return tuple(results)
