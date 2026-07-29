"""Tests for 7_check_json.py — the QA validation checker."""

import json
import subprocess
import sys
import os

import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'python_scripts')


class TestCheckJson:
    def test_valid_json_passes(self, write_json, tmp_path):
        """A well-formed questions.json should produce no errors."""
        questions = [
            {"question": "שאלה 1?", "options": ["א", "ב", "ג", "ד"], "correctIndex": 0},
            {"question": "שאלה 2?", "options": ["א", "ב", "ג", "ד"], "correctIndex": 2},
        ]
        q_path = write_json(questions, "questions.json")

        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, '7_check_json.py'), q_path],
            capture_output=True, text=True, encoding='utf-8'
        )
        assert result.returncode == 0
        assert "No errors found" in result.stdout
        assert "All questions look good" in result.stdout

    def test_empty_question_flagged(self, write_json, tmp_path):
        """Empty question text should be flagged as an error."""
        questions = [
            {"question": "", "options": ["א", "ב", "ג", "ד"], "correctIndex": 0},
        ]
        q_path = write_json(questions, "questions.json")

        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, '7_check_json.py'), q_path],
            capture_output=True, text=True, encoding='utf-8'
        )
        assert "EMPTY question text" in result.stdout
        assert "ERRORS" in result.stdout

    def test_correct_index_out_of_range(self, write_json, tmp_path):
        """correctIndex >= len(options) should be flagged as an error."""
        questions = [
            {"question": "שאלה?", "options": ["א", "ב", "ג", "ד"], "correctIndex": 5},
        ]
        q_path = write_json(questions, "questions.json")

        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, '7_check_json.py'), q_path],
            capture_output=True, text=True, encoding='utf-8'
        )
        assert "out of range" in result.stdout
        assert "ERRORS" in result.stdout

    def test_negative_correct_index(self, write_json, tmp_path):
        """Negative correctIndex should be flagged as an error."""
        questions = [
            {"question": "שאלה?", "options": ["א", "ב", "ג", "ד"], "correctIndex": -1},
        ]
        q_path = write_json(questions, "questions.json")

        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, '7_check_json.py'), q_path],
            capture_output=True, text=True, encoding='utf-8'
        )
        assert "negative" in result.stdout
        assert "ERRORS" in result.stdout

    def test_duplicate_options_warning(self, write_json, tmp_path):
        """Duplicate option text should produce a warning."""
        questions = [
            {"question": "שאלה?", "options": ["אותו דבר", "אותו דבר", "ג", "ד"], "correctIndex": 0},
        ]
        q_path = write_json(questions, "questions.json")

        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, '7_check_json.py'), q_path],
            capture_output=True, text=True, encoding='utf-8'
        )
        assert "Duplicate" in result.stdout
        assert "WARNINGS" in result.stdout

    def test_non_standard_option_count_warning(self, write_json, tmp_path):
        """Having != 4 options should produce a warning (not an error)."""
        questions = [
            {"question": "שאלה?", "options": ["א", "ב", "ג"], "correctIndex": 0},
        ]
        q_path = write_json(questions, "questions.json")

        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, '7_check_json.py'), q_path],
            capture_output=True, text=True, encoding='utf-8'
        )
        assert "Option count" in result.stdout
        assert "WARNINGS" in result.stdout
        # Should NOT be an error
        assert "No errors found" in result.stdout

    def test_empty_option_flagged(self, write_json, tmp_path):
        """Empty option string should be flagged as an error."""
        questions = [
            {"question": "שאלה?", "options": ["א", "", "ג", "ד"], "correctIndex": 0},
        ]
        q_path = write_json(questions, "questions.json")

        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, '7_check_json.py'), q_path],
            capture_output=True, text=True, encoding='utf-8'
        )
        assert "Empty option" in result.stdout
        assert "ERRORS" in result.stdout
