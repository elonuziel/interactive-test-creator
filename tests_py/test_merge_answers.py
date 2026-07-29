"""Tests for 6_merge_json_answers.py — the answer key merger."""

import json
import subprocess
import sys
import os

import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'python_scripts')


class TestMergeAnswers:
    def test_basic_merge(self, write_json, tmp_path):
        """Merge answers into questions with correct 1-based to 0-based conversion."""
        questions = [
            {"question": "שאלה 1", "options": ["א", "ב", "ג", "ד"], "correctIndex": 0},
            {"question": "שאלה 2", "options": ["א", "ב", "ג", "ד"], "correctIndex": 0},
            {"question": "שאלה 3", "options": ["א", "ב", "ג", "ד"], "correctIndex": 0},
        ]
        answers = {"1": 3, "2": 1, "3": 4}  # 1-based

        q_path = write_json(questions, "questions.json")
        a_path = write_json(answers, "answers.json")
        output_path = str(tmp_path / "merged.json")

        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, '6_merge_json_answers.py'),
             q_path, a_path, '-o', output_path],
            capture_output=True, text=True, encoding='utf-8'
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

        with open(output_path, 'r', encoding='utf-8') as f:
            merged = json.load(f)

        # 1-based answers should become 0-based correctIndex
        assert merged[0]['correctIndex'] == 2  # 3 → 2
        assert merged[1]['correctIndex'] == 0  # 1 → 0
        assert merged[2]['correctIndex'] == 3  # 4 → 3

    def test_null_cancelled_answer(self, write_json, tmp_path):
        """Cancelled/null answers should not update correctIndex."""
        questions = [
            {"question": "שאלה 1", "options": ["א", "ב", "ג", "ד"], "correctIndex": 0},
            {"question": "שאלה 2", "options": ["א", "ב", "ג", "ד"], "correctIndex": 0},
        ]
        answers = {"1": 2, "2": None}  # Q2 is cancelled

        q_path = write_json(questions, "questions.json")
        a_path = write_json(answers, "answers.json")
        output_path = str(tmp_path / "merged.json")

        subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, '6_merge_json_answers.py'),
             q_path, a_path, '-o', output_path],
            capture_output=True, text=True, encoding='utf-8'
        )

        with open(output_path, 'r', encoding='utf-8') as f:
            merged = json.load(f)

        assert merged[0]['correctIndex'] == 1  # 2 → 1
        assert merged[1]['correctIndex'] == 0  # unchanged (null answer)

    def test_missing_answer_key(self, write_json, tmp_path):
        """Questions without a matching answer key entry keep their original correctIndex."""
        questions = [
            {"question": "שאלה 1", "options": ["א", "ב", "ג", "ד"], "correctIndex": 0},
            {"question": "שאלה 2", "options": ["א", "ב", "ג", "ד"], "correctIndex": 0},
        ]
        answers = {"1": 3}  # Only Q1 has an answer

        q_path = write_json(questions, "questions.json")
        a_path = write_json(answers, "answers.json")
        output_path = str(tmp_path / "merged.json")

        subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, '6_merge_json_answers.py'),
             q_path, a_path, '-o', output_path],
            capture_output=True, text=True, encoding='utf-8'
        )

        with open(output_path, 'r', encoding='utf-8') as f:
            merged = json.load(f)

        assert merged[0]['correctIndex'] == 2  # 3 → 2
        assert merged[1]['correctIndex'] == 0  # unchanged

    def test_extra_answers_ignored(self, write_json, tmp_path):
        """Answer keys for questions beyond the count are ignored."""
        questions = [
            {"question": "שאלה 1", "options": ["א", "ב", "ג", "ד"], "correctIndex": 0},
        ]
        answers = {"1": 2, "2": 3, "3": 1}  # Q2, Q3 don't exist

        q_path = write_json(questions, "questions.json")
        a_path = write_json(answers, "answers.json")
        output_path = str(tmp_path / "merged.json")

        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, '6_merge_json_answers.py'),
             q_path, a_path, '-o', output_path],
            capture_output=True, text=True, encoding='utf-8'
        )
        assert result.returncode == 0

        with open(output_path, 'r', encoding='utf-8') as f:
            merged = json.load(f)

        assert len(merged) == 1
        assert merged[0]['correctIndex'] == 1  # 2 → 1
