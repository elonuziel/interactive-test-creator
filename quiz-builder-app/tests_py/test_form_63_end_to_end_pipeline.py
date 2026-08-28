from __future__ import annotations

import shutil
from pathlib import Path

from quizbuilder.commands import process_workspace
from quizbuilder.config import Config
from quizbuilder.exporter import build_standalone_quiz
from quizbuilder.form_numbers import resolve_form_number
from quizbuilder.markdown import load_questions
import pymupdf as fitz


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "form_pipeline"


def test_form_063_pdf_end_to_end_pipeline(tmp_path: Path):
    ws_dir = tmp_path / "exam_2022_b"
    ws_dir.mkdir(parents=True, exist_ok=True)

    pdf_src = FIXTURES_DIR / "form_063_exam.pdf"
    csv_src = FIXTURES_DIR / "answers_multi_form.csv"

    pdf_dest = ws_dir / "exam_2022_b.pdf"
    csv_dest = ws_dir / "answers.csv"

    shutil.copy(pdf_src, pdf_dest)
    shutil.copy(csv_src, csv_dest)

    # 1. Verify raw text extraction from synthetic PDF
    doc = fitz.open(pdf_dest)
    pdf_text = "\n".join(page.get_text() for page in doc)
    doc.close()
    assert "063" in pdf_text

    # 2. Verify form resolution from PDF text
    resolution = resolve_form_number(pdf_text, pdf_dest.name)
    assert resolution.status == "resolved"
    assert resolution.raw_value == "063"
    assert resolution.normalized_value == "63"

    # 3. Run full automated pipeline without manual form override (form=None)
    config = Config.defaults(root=ws_dir)
    config.scripts_root = Path(__file__).resolve().parents[1] / "python_scripts"

    artifacts = process_workspace(config, ws_dir, answer_key=csv_dest, form=None, pdf=pdf_dest)
    assert ws_dir / "questions.md" in artifacts
    assert ws_dir / "answers.json" in artifacts

    # 4. Verify questions and merged answers in questions.md
    questions = load_questions(ws_dir / "questions.md")
    assert len(questions) == 2

    # Q1: "מהו התהליך העיקרי המתרחש בכלורופלסט?" -> Ans 2 ("ב. פוטוסינתזה", index 1)
    q1 = questions[0]
    assert "כלורופלסט" in q1["question"]
    assert q1["correctIndex"] == 1
    assert "פוטוסינתזה" in q1["options"][1]

    # Q2: "איזה אברון אחראי על ייצור חלבונים בתא?" -> Ans 2 ("ב. ריבוזום", index 1)
    q2 = questions[1]
    assert "חלבונים" in q2["question"]
    assert q2["correctIndex"] == 1
    assert "ריבוזום" in q2["options"][1]

    # 5. Build standalone HTML quiz from workspace
    html_file = build_standalone_quiz(ws_dir, scripts_dir=config.scripts_root)
    assert html_file.is_file()
    html_content = html_file.read_text(encoding="utf-8")
    assert "כלורופלסט" in html_content


def test_form_000_companion_pdf_end_to_end_pipeline(tmp_path: Path):
    ws_dir = tmp_path / "exam_form_0"
    ws_dir.mkdir(parents=True, exist_ok=True)

    pdf_src = FIXTURES_DIR / "form_000_exam.pdf"
    csv_src = FIXTURES_DIR / "answers_multi_form.csv"

    pdf_dest = ws_dir / "exam_form_0.pdf"
    csv_dest = ws_dir / "answers.csv"

    shutil.copy(pdf_src, pdf_dest)
    shutil.copy(csv_src, csv_dest)

    # 1. Verify form resolution for Form 0
    doc = fitz.open(pdf_dest)
    pdf_text = "\n".join(page.get_text() for page in doc)
    doc.close()
    resolution = resolve_form_number(pdf_text, pdf_dest.name)
    assert resolution.status == "resolved"
    assert resolution.is_form_zero
    assert resolution.normalized_value == "0"

    # 2. Run automated pipeline
    config = Config.defaults(root=ws_dir)
    config.scripts_root = Path(__file__).resolve().parents[1] / "python_scripts"

    artifacts = process_workspace(config, ws_dir, answer_key=csv_dest, form=None, pdf=pdf_dest)
    assert ws_dir / "questions.md" in artifacts

    questions = load_questions(ws_dir / "questions.md")
    assert len(questions) == 2
    assert questions[0]["correctIndex"] == 1
    assert questions[1]["correctIndex"] == 1
