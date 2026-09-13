"""Unit tests for quizbuilder.batch.discover_batch."""
from __future__ import annotations

from pathlib import Path

import pytest

from quizbuilder.batch import BatchCandidate, discover_batch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pdf(folder: Path, name: str = "exam.pdf") -> Path:
    p = folder / name
    p.write_bytes(b"%PDF-1.4")
    return p


def _make_questions(folder: Path) -> Path:
    p = folder / "questions.md"
    p.write_text("## Question 1\nQ?\n- A\n- B\nAnswer: A\n", encoding="utf-8")
    return p


def _make_csv(folder: Path, name: str = "answers.csv") -> Path:
    p = folder / name
    p.write_text("1,A\n2,B\n", encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# 1. Empty root
# ---------------------------------------------------------------------------

def test_empty_folder_returns_no_candidates(tmp_path: Path) -> None:
    """An empty root produces no candidates and does not raise."""
    result = discover_batch(tmp_path)
    assert result == []


# ---------------------------------------------------------------------------
# 2. Single subfolder with one PDF
# ---------------------------------------------------------------------------

def test_single_pdf_one_candidate(tmp_path: Path) -> None:
    folder = tmp_path / "exam_2024"
    folder.mkdir()
    _make_pdf(folder)
    candidates = discover_batch(tmp_path)
    assert len(candidates) == 1
    assert isinstance(candidates[0], BatchCandidate)
    assert candidates[0].workspace.path == folder


# ---------------------------------------------------------------------------
# 3. questions.md-only subfolder (no PDF) still appears
# ---------------------------------------------------------------------------

def test_questions_md_only_subfolder(tmp_path: Path) -> None:
    folder = tmp_path / "already_extracted"
    folder.mkdir()
    _make_questions(folder)
    candidates = discover_batch(tmp_path)
    assert len(candidates) == 1
    assert candidates[0].workspace.path == folder


# ---------------------------------------------------------------------------
# 4. Multiple PDFs → isolated .quizbuilder workspaces
# ---------------------------------------------------------------------------

def test_multiple_pdfs_isolated_workspaces(tmp_path: Path) -> None:
    folder = tmp_path / "multi_exams"
    folder.mkdir()
    _make_pdf(folder, "moed_a.pdf")
    _make_pdf(folder, "moed_b.pdf")

    candidates = discover_batch(tmp_path)

    assert len(candidates) == 2
    workspace_paths = {c.workspace.path for c in candidates}
    assert len(workspace_paths) == 2
    assert all(".quizbuilder" in str(p) for p in workspace_paths)


# ---------------------------------------------------------------------------
# 5. Moed-variant answer-key matching (matched case)
# ---------------------------------------------------------------------------

def test_moed_variant_answer_key_matched(tmp_path: Path) -> None:
    folder = tmp_path / "bio"
    folder.mkdir()
    _make_pdf(folder, "biology_moed_a.pdf")
    _make_csv(folder, "answers_moed_a.csv")
    _make_csv(folder, "answers_moed_b.csv")

    candidates = discover_batch(tmp_path)

    assert len(candidates) == 1
    c = candidates[0]
    # Only the matching key should survive — "no answer key matches" must not appear
    assert "no answer key matches this Moed variant" not in c.issues


# ---------------------------------------------------------------------------
# 6. Moed-variant mismatch → issue reported
# ---------------------------------------------------------------------------

def test_moed_variant_no_match_reports_issue(tmp_path: Path) -> None:
    """The 'no answer key matches' issue fires only for multi-PDF isolated workspaces
    (where source_pdf is set). Use two PDFs so isolation kicks in."""
    folder = tmp_path / "bio"
    folder.mkdir()
    _make_pdf(folder, "biology_moed_a.pdf")
    _make_pdf(folder, "biology_moed_b.pdf")
    _make_csv(folder, "answers_moed_a.csv")  # only key for moed-a exists

    candidates = discover_batch(tmp_path)

    # The moed-b PDF has no matching answer key → should get the issue
    moed_b_candidate = next(
        c for c in candidates if "moed_b" in str(c.workspace.source_pdf or "")
    )
    assert "no answer key matches this Moed variant" in moed_b_candidate.issues


# ---------------------------------------------------------------------------
# 7. Multiple answer keys (no variant info) → issue
# ---------------------------------------------------------------------------

def test_multiple_answer_keys_reports_issue(tmp_path: Path) -> None:
    folder = tmp_path / "exam"
    folder.mkdir()
    _make_pdf(folder, "exam.pdf")
    _make_csv(folder, "answers1.csv")
    _make_csv(folder, "answers2.csv")

    candidates = discover_batch(tmp_path)

    assert len(candidates) == 1
    assert "multiple answer keys; choose one" in candidates[0].issues


# ---------------------------------------------------------------------------
# 8. runs/ subdirectory is excluded
# ---------------------------------------------------------------------------

def test_excludes_runs_directory(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    _make_pdf(runs_dir, "run_output.pdf")

    candidates = discover_batch(tmp_path)
    assert candidates == []


# ---------------------------------------------------------------------------
# 9. .quizbuilder/ internals are excluded from top-level scan
# ---------------------------------------------------------------------------

def test_excludes_quizbuilder_internals(tmp_path: Path) -> None:
    # Create a multi-PDF folder so .quizbuilder gets created by the function,
    # then ensure a second call doesn't double-count those internal dirs.
    folder = tmp_path / "multi"
    folder.mkdir()
    _make_pdf(folder, "a.pdf")
    _make_pdf(folder, "b.pdf")

    first = discover_batch(tmp_path)
    # Simulate next call: .quizbuilder already exists with sub-dirs
    qb = folder / ".quizbuilder"
    qb.mkdir(exist_ok=True)
    inner = qb / "some-project-abc12345"
    inner.mkdir()
    _make_pdf(inner, "phantom.pdf")  # should not be discovered

    second = discover_batch(tmp_path)
    assert len(second) == len(first)  # count must not increase


# ---------------------------------------------------------------------------
# 10. Case-insensitive PDF suffix (.PDF on Linux)
# ---------------------------------------------------------------------------

def test_case_insensitive_pdf_suffix(tmp_path: Path) -> None:
    folder = tmp_path / "exam_caps"
    folder.mkdir()
    p = folder / "EXAM.PDF"
    p.write_bytes(b"%PDF-1.4")

    candidates = discover_batch(tmp_path)
    assert len(candidates) == 1


# ---------------------------------------------------------------------------
# 11. ready_to_run is True only when questions.md exists and no issues
# ---------------------------------------------------------------------------

def test_ready_to_run_true_when_extracted_and_no_issues(tmp_path: Path) -> None:
    folder = tmp_path / "done"
    folder.mkdir()
    _make_pdf(folder)
    _make_questions(folder)

    candidates = discover_batch(tmp_path)
    assert len(candidates) == 1
    assert candidates[0].ready_to_run is True


def test_ready_to_run_false_when_issues_present(tmp_path: Path) -> None:
    """ready_to_run is False when issues exist even if questions.md is present.
    Use multi-PDF isolation to produce a real issue (moed mismatch)."""
    folder = tmp_path / "broken"
    folder.mkdir()
    _make_pdf(folder, "bio_moed_a.pdf")
    _make_pdf(folder, "bio_moed_b.pdf")
    _make_csv(folder, "answers_moed_a.csv")  # moed-b will have no matching key

    candidates = discover_batch(tmp_path)

    moed_b = next(c for c in candidates if "moed_b" in str(c.workspace.source_pdf or ""))
    # Add questions.md to its isolated workspace so it's not blocked by that issue
    moed_b.workspace.path.mkdir(parents=True, exist_ok=True)
    _make_questions(moed_b.workspace.path)

    # Re-discover to pick up the questions.md
    candidates2 = discover_batch(tmp_path)
    moed_b2 = next(c for c in candidates2 if "moed_b" in str(c.workspace.source_pdf or ""))
    assert moed_b2.ready_to_run is False


# ---------------------------------------------------------------------------
# 12. Nested subfolders are discovered via rglob
# ---------------------------------------------------------------------------

def test_nested_subfolder_discovered(tmp_path: Path) -> None:
    deep = tmp_path / "level1" / "level2" / "exam_nested"
    deep.mkdir(parents=True)
    _make_pdf(deep)

    candidates = discover_batch(tmp_path)
    assert len(candidates) == 1
    assert candidates[0].workspace.path == deep


# ---------------------------------------------------------------------------
# 13. DOCX-only folder (no PDF) → issue reported
# ---------------------------------------------------------------------------

def test_docx_without_pdf_reports_issue(tmp_path: Path) -> None:
    folder = tmp_path / "docx_only"
    folder.mkdir()
    (folder / "exam.docx").write_bytes(b"PK")  # minimal ZIP magic

    candidates = discover_batch(tmp_path)
    assert len(candidates) == 1
    assert "PDF source is missing; convert DOCX to PDF" in candidates[0].issues


# ---------------------------------------------------------------------------
# 14. missing questions.md is flagged as an issue
# ---------------------------------------------------------------------------

def test_missing_questions_md_flagged(tmp_path: Path) -> None:
    folder = tmp_path / "not_extracted"
    folder.mkdir()
    _make_pdf(folder)

    candidates = discover_batch(tmp_path)
    assert len(candidates) == 1
    assert "questions.md is missing" in candidates[0].issues
