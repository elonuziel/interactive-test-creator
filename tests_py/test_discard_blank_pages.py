"""Tests for automatic blank page detection and discarding in 3_render_pdf_pages.py."""

import os
import sys
import subprocess
import pytest
import fitz

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'python_scripts')
sys.path.insert(0, SCRIPTS_DIR)

from importlib import import_module
render_module = import_module("3_render_pdf_pages")
is_blank_page = render_module.is_blank_page


class TestDiscardBlankPages:
    def test_empty_page_is_blank(self, tmp_path):
        """A completely empty PDF page should be identified as blank."""
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        assert is_blank_page(page) is True
        doc.close()

    def test_noise_only_page_is_blank(self, tmp_path):
        """A page containing only page number or test code noise should be identified as blank."""
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text((50, 50), "Page 1 of 10", fontsize=12)
        page.insert_text((50, 800), "Exam Code: 12345", fontsize=12)
        assert is_blank_page(page) is True
        doc.close()

    def test_question_content_page_is_not_blank(self, tmp_path):
        """A page containing actual test question text should NOT be identified as blank."""
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text((50, 100), "Question 1: What is the primary function of chlorophyll in photosynthesis?", fontsize=14)
        assert is_blank_page(page) is False
        doc.close()

    def test_render_pdf_pages_cli_discards_blank(self, tmp_path):
        """CLI rendering should skip saving blank pages when --discard-blank (default) is enabled."""
        pdf_path = os.path.join(tmp_path, "sample_test.pdf")
        out_dir = os.path.join(tmp_path, "pages_output")

        doc = fitz.open()
        # Page 1: content
        p1 = doc.new_page(width=595, height=842)
        p1.insert_text((50, 100), "Question 1: Which of the following is a greenhouse gas?", fontsize=14)

        # Page 2: blank
        p2 = doc.new_page(width=595, height=842)

        # Page 3: content
        p3 = doc.new_page(width=595, height=842)
        p3.insert_text((50, 100), "Question 2: Which organ filters blood in the human body?", fontsize=14)

        doc.save(pdf_path)
        doc.close()

        # Run 3_render_pdf_pages.py
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "3_render_pdf_pages.py"), pdf_path, "-o", out_dir],
            capture_output=True, text=True, encoding="utf-8"
        )

        assert result.returncode == 0
        assert os.path.exists(os.path.join(out_dir, "page_1.png"))
        assert not os.path.exists(os.path.join(out_dir, "page_2.png"))
        assert os.path.exists(os.path.join(out_dir, "page_3.png"))
        assert "Skipped blank page 2" in result.stdout

    def test_render_pdf_pages_cli_keep_blank(self, tmp_path):
        """CLI rendering should keep blank pages when --keep-blank is passed."""
        pdf_path = os.path.join(tmp_path, "sample_test.pdf")
        out_dir = os.path.join(tmp_path, "pages_output")

        doc = fitz.open()
        p1 = doc.new_page(width=595, height=842)
        p1.insert_text((50, 100), "Question 1: Which of the following is a greenhouse gas?", fontsize=14)
        p2 = doc.new_page(width=595, height=842)
        doc.save(pdf_path)
        doc.close()

        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "3_render_pdf_pages.py"), pdf_path, "-o", out_dir, "--keep-blank"],
            capture_output=True, text=True, encoding="utf-8"
        )

        assert result.returncode == 0
        assert os.path.exists(os.path.join(out_dir, "page_1.png"))
        assert os.path.exists(os.path.join(out_dir, "page_2.png"))

    def test_render_pdf_pages_cli_creates_merged_pdf(self, tmp_path):
        """CLI rendering should save a merged PDF containing only non-blank pages when --merged-pdf is specified."""
        pdf_path = os.path.join(tmp_path, "sample_test.pdf")
        out_dir = os.path.join(tmp_path, "pages_output")
        merged_pdf_path = os.path.join(tmp_path, "clean_test.pdf")

        doc = fitz.open()
        p1 = doc.new_page(width=595, height=842)
        p1.insert_text((50, 100), "Question 1: Which element has atomic number 1?", fontsize=14)
        p2 = doc.new_page(width=595, height=842) # blank
        p3 = doc.new_page(width=595, height=842)
        p3.insert_text((50, 100), "Question 2: What is the speed of light?", fontsize=14)
        doc.save(pdf_path)
        doc.close()

        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "3_render_pdf_pages.py"), pdf_path, "-o", out_dir, "--merged-pdf", merged_pdf_path],
            capture_output=True, text=True, encoding="utf-8"
        )

        assert result.returncode == 0
        assert os.path.exists(merged_pdf_path)
        
        merged_doc = fitz.open(merged_pdf_path)
        assert len(merged_doc) == 2  # Only 2 non-blank pages
        merged_doc.close()

