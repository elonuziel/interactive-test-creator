"""
Tests for modernized batch runner & grouping in quiz_builder_cli.py
"""

import os
import sys
import json
import importlib.util
from pathlib import Path


def _load_cli_module():
    root = Path(__file__).resolve().parents[1]
    cli_path = root / 'quiz_builder_cli.py'
    spec = importlib.util.spec_from_file_location('quiz_builder_cli', str(cli_path))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_normalize_stem_name():
    cli = _load_cli_module()
    assert cli.normalize_stem_name("chemistry_2026_answers.csv") == "chemistry_2026"
    assert cli.normalize_stem_name("bio_101_ans.xlsx") == "bio_101"
    assert cli.normalize_stem_name("exam_form0.csv") == "exam"
    assert cli.normalize_stem_name("physics_פתרונות.csv") == "physics"
    assert cli.normalize_stem_name("standalone_exam.pdf") == "standalone_exam"


def test_scan_and_group_flat_files(tmp_path):
    cli = _load_cli_module()
    drop_dir = tmp_path / "drop_here"
    drop_dir.mkdir()
    tests_target = tmp_path / "organized_tests"

    # Create dropped files
    (drop_dir / "math_2025.pdf").write_text("fake pdf", encoding="utf-8")
    (drop_dir / "math_2025_answers.csv").write_text("1,1\n2,2", encoding="utf-8")
    (drop_dir / "history_moed_a.docx").write_text("fake docx", encoding="utf-8")

    workspaces = cli.scan_and_group_inputs(str(drop_dir), str(tests_target))
    assert len(workspaces) >= 2

    math_ws = tests_target / "math_2025"
    assert math_ws.is_dir()
    assert (math_ws / "math_2025.pdf").exists()
    assert (math_ws / "math_2025_answers.csv").exists()

    hist_ws = tests_target / "history_moed_a"
    assert hist_ws.is_dir()
    assert (hist_ws / "history_moed_a.docx").exists()


def test_analyze_workspace_statuses(tmp_path):
    cli = _load_cli_module()
    ws = tmp_path / "sample_test"
    ws.mkdir()

    # Empty
    info = cli.analyze_workspace(str(ws))
    assert info['status'] == "EMPTY"

    # With PDF -> NEEDS_EXTRACTION
    (ws / "exam.pdf").write_text("pdf", encoding="utf-8")
    info = cli.analyze_workspace(str(ws))
    assert info['status'] == "NEEDS_EXTRACTION"
    assert info['form_number'] == "0"

    # With CSV -> form 1 default
    (ws / "answers.csv").write_text("1,1", encoding="utf-8")
    info = cli.analyze_workspace(str(ws))
    assert info['form_number'] == "1"

    # With questions.json -> READY_TO_BUILD
    (ws / "questions.json").write_text("[]", encoding="utf-8")
    info = cli.analyze_workspace(str(ws))
    assert info['status'] == "READY_TO_BUILD"

    # With HTML -> BUILT
    (ws / "exam.html").write_text("<html></html>", encoding="utf-8")
    info = cli.analyze_workspace(str(ws))
    assert info['status'] == "BUILT"


def test_generate_master_portal(tmp_path):
    cli = _load_cli_module()
    output_dir = tmp_path / "portal_out"

    quizzes = [
        {'name': 'exam_1', 'title': 'Exam 1', 'question_count': 25, 'html_name': 'exam_1.html'},
        {'name': 'exam_2', 'title': 'Exam 2', 'question_count': 40, 'html_name': 'exam_2.html'},
    ]

    portal_path = cli.generate_master_portal(str(output_dir), quizzes)
    assert os.path.isfile(portal_path)

    content = Path(portal_path).read_text(encoding="utf-8")
    assert "פורטל המבחנים האינטראקטיביים" in content
    assert "Exam 1" in content
    assert "25 שאלות" in content
    assert "exam_2.html" in content
