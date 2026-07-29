"""Tests for 5_parse_questions_md.py — the Hebrew Markdown → JSON parser."""

import json
import subprocess
import sys
import os

import pytest

# Import functions directly for unit tests
SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'python_scripts')
sys.path.insert(0, SCRIPTS_DIR)

# noinspection PyUnresolvedReferences
from importlib import import_module
parse_mod = import_module('5_parse_questions_md')

clean_question_text = parse_mod.clean_question_text
clean_option_text = parse_mod.clean_option_text
normalize_whitespace = parse_mod.normalize_whitespace
is_noise = parse_mod.is_noise
try_match_patterns = parse_mod.try_match_patterns
try_split_midline_answer = parse_mod.try_split_midline_answer
reverse_words = parse_mod.reverse_words


# ── Unit tests for clean_question_text ─────────────────────────────────────

class TestCleanQuestionText:
    def test_misplaced_question_mark(self):
        assert clean_question_text("?מה התשובה הנכונה") == "מה התשובה הנכונה?"

    def test_misplaced_colon(self):
        assert clean_question_text(":בחר את התשובה") == "בחר את התשובה:"

    def test_misplaced_colon_paren(self):
        assert clean_question_text(":(הנתונים הבאים") == "הנתונים הבאים:"

    def test_leading_dot_removal(self):
        assert clean_question_text(".מה התשובה") == "מה התשובה"

    def test_trailing_hyphen_removal(self):
        assert clean_question_text("שאלה כלשהי-") == "שאלה כלשהי"

    def test_merged_digit_hebrew(self):
        assert clean_question_text("הן6 מיליון") == "הן 6 מיליון"

    def test_merged_hebrew_digit(self):
        assert clean_question_text("6מיליון") == "6 מיליון"

    def test_nbsp_normalization(self):
        assert clean_question_text("שאלה\u00A0כלשהי") == "שאלה כלשהי"

    def test_whitespace_collapse(self):
        assert clean_question_text("שאלה   עם   רווחים") == "שאלה עם רווחים"


# ── Unit tests for clean_option_text ───────────────────────────────────────

class TestCleanOptionText:
    def test_leading_dot(self):
        assert clean_option_text(".תשובה כלשהי") == "תשובה כלשהי"

    def test_trailing_hyphen(self):
        assert clean_option_text("אפשרות-") == "אפשרות"

    def test_merged_digits(self):
        assert clean_option_text("תשובה3") == "תשובה 3"


# ── Unit tests for noise detection ─────────────────────────────────────────

class TestNoiseDetection:
    def test_page_number_hebrew(self):
        assert is_noise("עמוד 1 מתוך 5")

    def test_page_number_reversed(self):
        assert is_noise("1 מתוך5 עמוד")

    def test_exam_code_noise(self):
        assert is_noise("קוד מבחן 076")

    def test_normal_line_not_noise(self):
        assert not is_noise("מה התשובה הנכונה?")


# ── Unit tests for answer pattern matching ─────────────────────────────────

class TestAnswerPatterns:
    def test_start_pattern_hebrew_letter(self):
        letter, text = try_match_patterns("א. תשובה ראשונה")
        assert letter == "א"
        assert text == "תשובה ראשונה"

    def test_start_pattern_digit(self):
        letter, text = try_match_patterns("1) first answer")
        assert letter == "1"
        assert text == "first answer"

    def test_end_pattern(self):
        letter, text = try_match_patterns("תשובה ראשונה א.")
        assert letter == "א"
        assert text == "תשובה ראשונה"

    def test_dot_first_ltr(self):
        letter, text = try_match_patterns(".א תשובה ראשונה")
        assert letter == "א"
        assert text == "תשובה ראשונה"

    def test_no_match(self):
        letter, text = try_match_patterns("just some regular text")
        assert letter is None
        assert text is None


# ── Unit tests for reverse_words ───────────────────────────────────────────

class TestReverseWords:
    def test_basic(self):
        assert reverse_words("hello world") == "world hello"

    def test_empty(self):
        assert reverse_words("") == ""

    def test_single_word(self):
        assert reverse_words("hello") == "hello"


# ── Unit tests for midline answer splitting ────────────────────────────────

class TestMidlineSplit:
    def test_basic_midline(self):
        result = try_split_midline_answer("שאלה כלשהי א. תשובה")
        assert result is not None
        before, letter, text = result
        assert letter == "א"

    def test_no_midline(self):
        result = try_split_midline_answer("just regular text here")
        assert result is None


# ── Integration test: full parse pipeline ──────────────────────────────────

class TestFullParse:
    def test_basic_parsing(self, write_md, tmp_path):
        """Parse a simple markdown with 2 questions and verify JSON output."""
        md_content = """\
שאלה מספר 1:
מה הצבע של השמיים?
א. ירוק
ב. כחול
ג. אדום
ד. צהוב

שאלה מספר 2:
מה 1 + 1?
א. 3
ב. 2
ג. 1
ד. 0
"""
        md_path = write_md(md_content)
        output_path = str(tmp_path / "output.json")

        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, '5_parse_questions_md.py'),
             md_path, '-o', output_path],
            capture_output=True, text=True, encoding='utf-8'
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

        with open(output_path, 'r', encoding='utf-8') as f:
            questions = json.load(f)

        assert len(questions) == 2
        assert "השמיים" in questions[0]['question']
        assert len(questions[0]['options']) == 4
        assert questions[0]['options'][0] == "ירוק"
        assert questions[0]['options'][1] == "כחול"

    def test_reversed_question_format(self, write_md, tmp_path):
        """Parse question with reversed Hebrew format '1 :מספר שאלה'."""
        md_content = """\
1 :מספר שאלה
מה התשובה?
א. אפשרות א
ב. אפשרות ב
ג. אפשרות ג
ד. אפשרות ד
"""
        md_path = write_md(md_content)
        output_path = str(tmp_path / "output.json")

        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, '5_parse_questions_md.py'),
             md_path, '-o', output_path],
            capture_output=True, text=True, encoding='utf-8'
        )
        assert result.returncode == 0

        with open(output_path, 'r', encoding='utf-8') as f:
            questions = json.load(f)

        assert len(questions) == 1
        assert len(questions[0]['options']) == 4

    def test_noise_lines_filtered(self, write_md, tmp_path):
        """Verify that page number lines are filtered out."""
        md_content = """\
שאלה מספר 1:
עמוד 1 מתוך 5
מה הצבע?
א. ירוק
ב. כחול
ג. אדום
ד. צהוב
"""
        md_path = write_md(md_content)
        output_path = str(tmp_path / "output.json")

        subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, '5_parse_questions_md.py'),
             md_path, '-o', output_path],
            capture_output=True, text=True, encoding='utf-8'
        )

        with open(output_path, 'r', encoding='utf-8') as f:
            questions = json.load(f)

        assert len(questions) == 1
        # The noise line should NOT appear in the question text
        assert "עמוד" not in questions[0]['question']

    def test_alternative_question_format(self, write_md, tmp_path):
        """Parse questions using 'שאלה N:' format (no מספר)."""
        md_content = """\
שאלה 1:
מה הצבע?
א. ירוק
ב. כחול
ג. אדום
ד. צהוב

שאלה 2:
מה המספר?
א. אחד
ב. שתיים
ג. שלוש
ד. ארבע
"""
        md_path = write_md(md_content)
        output_path = str(tmp_path / "output.json")

        subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, '5_parse_questions_md.py'),
             md_path, '-o', output_path],
            capture_output=True, text=True, encoding='utf-8'
        )

        with open(output_path, 'r', encoding='utf-8') as f:
            questions = json.load(f)

        assert len(questions) == 2
        assert "הצבע" in questions[0]['question']
        assert "המספר" in questions[1]['question']
