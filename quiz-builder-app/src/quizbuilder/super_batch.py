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
from .documents import classify_pdf, clean_pdf, preferred_pdf
from .markdown import load_questions, write_questions, validate_image_references
from .models import Workspace
from .prompts import extract_markdown_from_response, send_to_provider
from .config import Config
from .workspace import discover_sources
from .form_numbers import FormResolution, resolve_form_number


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
    form_number: str | None = None
    form_lookup_number: str | None = None
    form_source: str | None = None
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
    form = resolve_form_number(text, filename)
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
    return {
        "test_number": number,
        "year": year_match.group(1) if year_match else None,
        "variant": exam_variant(filename),
        "form_number": form.raw_value,
        "form_lookup_number": form.normalized_value,
        "form_source": form.candidate.source if form.candidate else None,
    }


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
            rows = frame.fillna("").astype(str).values.tolist()
            for h_idx, row in enumerate(rows):
                cols = [str(c).strip() for c in row]
                q_cols = [(col_idx, c) for col_idx, c in enumerate(cols) if re.search(r"(?:שאלה|question)\s*(\d+)", c, re.IGNORECASE)]
                if q_cols:
                    for d_idx in range(h_idx + 1, len(rows)):
                        data_row = rows[d_idx]
                        if not any(data_row):
                            continue
                        res: dict[int, str] = {}
                        for col_idx, q_header in q_cols:
                            q_num_m = re.search(r"(?:שאלה|question)\s*(\d+)", q_header, re.IGNORECASE)
                            if not q_num_m or col_idx >= len(data_row):
                                continue
                            q_num = int(q_num_m.group(1))
                            val = data_row[col_idx].strip()
                            form0_m = re.search(r"\{(\d+|[A-Dא-ד])\}", val)
                            ans_m = re.search(r"\((\d+|[A-Dא-ד])\)", val)
                            if form0_m:
                                raw_a = form0_m.group(1)
                                letter = chr(ord("A") + int(raw_a) - 1) if raw_a.isdigit() and 1 <= int(raw_a) <= 26 else raw_a.upper()
                                res[q_num] = letter
                            elif ans_m:
                                raw_a = ans_m.group(1)
                                letter = chr(ord("A") + int(raw_a) - 1) if raw_a.isdigit() and 1 <= int(raw_a) <= 26 else raw_a.upper()
                                res[q_num] = letter
                            elif val.isdigit():
                                raw_a = int(val)
                                letter = chr(ord("A") + raw_a - 1) if 1 <= raw_a <= 26 else str(raw_a)
                                res[q_num] = letter
                            elif val and val[0].upper() in "ABCDאבגד":
                                res[q_num] = val[0].upper()
                        if len(res) >= 3:
                            return res
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


def score_answer_key(pdf: Path, key: Path, metadata: dict[str, str | None], answers_count: int = 0) -> int:
    score = 0
    pdf_stem = pdf.stem.casefold()
    key_stem = key.stem.casefold()

    # 1. Moed variant match
    pdf_variant = metadata.get("variant") or exam_variant(pdf.name)
    key_variant = exam_variant(key.name)
    if pdf_variant and key_variant:
        if pdf_variant == key_variant:
            score += 20
        else:
            return -100  # Direct Moed conflict (e.g. A vs B)
    elif pdf_variant and not key_variant:
        score -= 2

    # 2. Test / Form Number match
    test_number = metadata.get("test_number")
    if test_number and test_number in key_stem:
        score += 30

    # 3. Year match
    year = metadata.get("year")
    if year and year in key_stem:
        score += 15

    # 4. Token overlap
    pdf_tokens = set(re.findall(r"\w+", pdf_stem)) - {"test", "exam", "pdf", "moed", "בחינה", "מבחן", "טופס"}
    key_tokens = set(re.findall(r"\w+", key_stem)) - {"answers", "answer", "key", "csv", "xlsx", "xls", "md", "json", "תשובות", "מפתח"}
    overlap = pdf_tokens & key_tokens
    score += len(overlap) * 5

    # 5. Has parsed answers
    if answers_count > 0:
        score += 5

    return score


def build_plan(root: Path) -> SuperBatchPlan:
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Projects folder not found: {root}")
    items: list[SuperBatchItem] = []
    # Discover all PDFs
    all_pdfs = [
        p for p in sorted(root.rglob("*"), key=lambda p: str(p).casefold())
        if p.is_file() and p.suffix.lower() == ".pdf" and ".quizbuilder" not in p.parts and not p.stem.casefold().endswith("_clean")
    ]
    # Group by parent folder to detect multiple PDFs sharing a folder
    by_folder: dict[Path, list[Path]] = {}
    for pdf in all_pdfs:
        by_folder.setdefault(pdf.parent, []).append(pdf)

    for folder, pdfs in by_folder.items():
        is_multi = len(pdfs) > 1 and not (folder / "questions.md").is_file()
        
        # Discover all CSV, Excel, and answer key files in this folder
        ignored_names = {"questions.md", "questions.json", "raw_text.md", "page_map.json", "manifest.json"}
        folder_key_files = sorted(
            [
                f for f in folder.iterdir()
                if f.is_file()
                and f.suffix.lower() in {".csv", ".xlsx", ".xls", ".md", ".json"}
                and f.name.lower() not in ignored_names
            ],
            key=lambda p: p.name.casefold()
        )

        for pdf in pdfs:
            if is_multi:
                workspace = folder / ".quizbuilder" / _project_slug(pdf.stem)
                exam_name = f"{folder.name} - {pdf.stem}"
            else:
                workspace = folder
                exam_name = pdf.stem

            metadata = extract_exam_metadata(pdf.stem, pdf.name)
            
            candidates_list: list[AnswerKeyCandidate] = []
            for key in folder_key_files:
                answers = normalize_answer_key(key)
                score = score_answer_key(pdf, key, metadata, len(answers))
                candidates_list.append(AnswerKeyCandidate(key, answers, score))
            
            # Sort candidates: highest match score first, then alphabetically
            candidates_list.sort(key=lambda c: (c.score, -len(c.path.name)), reverse=True)
            candidates = tuple(candidates_list)

            overview = ExamOverview(
                pdf=pdf,
                workspace=workspace,
                name=exam_name,
                is_digital=None,
                test_number=metadata["test_number"],
                year=metadata["year"],
                variant=metadata["variant"],
                form_number=metadata.get("form_number"),
                form_lookup_number=metadata.get("form_lookup_number"),
                form_source=metadata.get("form_source"),
                confidence=1.0 if metadata.get("form_number") else 0.0,
                warnings=("PDF classification pending",) if metadata.get("form_number") else ("Form number not detected", "PDF classification pending"),
            )
            
            # Auto-select the top matched answer key (if score > 0 or only 1 key available)
            selected_key = candidates[0].path if (candidates and (candidates[0].score > 0 or len(candidates) == 1)) else None
            items.append(SuperBatchItem(overview, candidates, selected_answer_key=selected_key))

    return SuperBatchPlan(root, tuple(items))


def classify_plan_item(item: SuperBatchItem) -> SuperBatchItem:
    try:
        digital = classify_pdf(item.overview.pdf, workspace=item.overview.workspace)
    except Exception:
        digital = False
    warnings = tuple(w for w in item.overview.warnings if w != "PDF classification pending")
    item.overview = replace(item.overview, is_digital=digital, warnings=warnings)
    if not item.selected_answer_key and item.answer_keys:
        if len(item.answer_keys) == 1:
            item.selected_answer_key = item.answer_keys[0].path
        elif item.answer_keys[0].score > (item.answer_keys[1].score if len(item.answer_keys) > 1 else 0):
            item.selected_answer_key = item.answer_keys[0].path
    return item


def zero_test_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**question, "correctIndex": 0, "shuffleOptions": True} for question in questions]


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

    form_number = getattr(item.overview, "form_number", None) or "unknown"
    return f"""You are generating the final canonical questions.md for exam '{item.overview.name}'.
Source PDF Path: {item.overview.pdf.resolve()}
Workspace Directory: {item.overview.workspace.resolve()}
Metadata: test number={item.overview.test_number or 'unknown'}, year={item.overview.year or 'unknown'}, variant={item.overview.variant or 'unknown'}, form={form_number}, normalized form={item.overview.form_lookup_number or 'unknown'}, form source={item.overview.form_source or 'unknown'}.
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
4. Preserve the visible `Form number: {form_number}` metadata line when a form was detected.
5. If this is Form 0, do not solve answers: every source correct answer is option 1 and displayed choices must be shuffled by the shared runtime.

Document Context Excerpt:
{context}
"""


def default_decision(item: SuperBatchItem) -> str:
    if item.selected_answer_key:
        return "use_answer_key"
    if item.overview.is_digital:
        return "zero_test"
    return "generate_only"


def _context_for_pdf(pdf: Path, is_digital: bool, mode: str = "path") -> str:
    if mode == "path":
        return f"PDF file path: {pdf.resolve()}. If your CLI can access local files, inspect this PDF directly."
    if not is_digital:
        try:
            try:
                import pymupdf as fitz
            except ImportError:
                import fitz
            document = fitz.open(pdf)
            pages = []
            for page in document[:5]:
                pages.append(page.get_text()[:5000])
            return "\n\n--- PAGE ---\n\n".join(pages) or "No OCR text was extracted; inspect the supplied PDF path if available."
        except Exception as exc:
            return f"Local OCR extraction unavailable ({exc}). PDF file path: {pdf.resolve()}"
    try:
        try:
            import pymupdf as fitz
        except ImportError:
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
    context_mode: str = "path",
    discard_pages: str = "",
    clean_digital: bool = False,
    auto_build_html: bool = True,
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

        pdf = preferred_pdf(item.overview.pdf, item.overview.workspace)
        if pdf != item.overview.pdf:
            item.status = "using cleaned PDF"
            if progress:
                progress(item)
        if item.overview.is_digital:
            if item.overview.form_lookup_number == "0" and item.decision == "use_answer_key":
                item.decision = "zero_test"
            if clean_digital and discard_pages and pdf == item.overview.pdf:
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
            process_workspace(
                config,
                item.overview.workspace,
                item.selected_answer_key if item.decision == "use_answer_key" else None,
                item.overview.form_number,
                pdf,
            )
            if item.decision == "zero_test" or item.overview.form_lookup_number == "0":
                write_questions(output, zero_test_questions(load_questions(output)))
        else:
            # Every scanned PDF must go through the selected CLI AI for OCR/vision
            # extraction. The decision only controls answer metadata, not OCR.
            if item.decision == "ask_user":
                item.decision = "generate_only"
            item.status = "generating"
            if progress:
                progress(item)
            if context_mode == "extracted":
                context = _context_for_pdf(pdf, False, context_mode)
            else:
                context = _context_for_pdf(pdf, False, "path")
            context = (
                "SCANNED PDF OCR REQUIREMENT: Inspect every page visually and perform OCR yourself. "
                "Do not rely only on the filename or local text excerpt. Preserve diagrams, graphs, tables, "
                "symbols, and question-to-full-page image references.\n\n" + context
            )
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
        missing_images = validate_image_references(load_questions(output), output.parent)
        if missing_images:
            item.overview = replace(item.overview, warnings=item.overview.warnings + tuple(missing_images))
        
        if auto_build_html:
            try:
                from .exporter import build_standalone_quiz
                build_standalone_quiz(item.overview.workspace, output=item.overview.workspace / "quiz.html")
            except Exception:
                pass

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
    context_mode: str = "path",
    discard_pages: str = "",
    clean_digital: bool = False,
    auto_build_html: bool = True,
    auto_build_hub: bool = True,
    cancel_event: threading.Event | None = None,
    progress: Callable[[SuperBatchItem], None] | None = None,
) -> tuple[SuperBatchResult, ...]:
    results: list[SuperBatchResult] = []
    if workers <= 1:
        for item in plan.items:
            res = process_item(
                item,
                provider,
                command,
                ai_mode=ai_mode,
                context_mode=context_mode,
                discard_pages=discard_pages,
                clean_digital=clean_digital,
                auto_build_html=auto_build_html,
                cancel_event=cancel_event,
                progress=progress,
            )
            results.append(res)
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(
                    process_item,
                    item,
                    provider,
                    command,
                    ai_mode=ai_mode,
                    context_mode=context_mode,
                    discard_pages=discard_pages,
                    clean_digital=clean_digital,
                    auto_build_html=auto_build_html,
                    cancel_event=cancel_event,
                    progress=progress,
                )
                for item in plan.items
            ]
            for future in as_completed(futures):
                results.append(future.result())

    if auto_build_hub:
        try:
            from .hub import build_central_hub
            from .models import Workspace
            ready_workspaces = [
                Workspace(
                    name=res.item.overview.name,
                    path=res.item.overview.workspace,
                    source_pdf=res.item.overview.pdf,
                )
                for res in results
                if res.success and (res.item.overview.workspace / "questions.md").is_file()
            ]
            if ready_workspaces:
                build_central_hub(plan.root, ready_workspaces, output=plan.root / "quiz_hub.html")
        except Exception:
            pass

    return tuple(results)
