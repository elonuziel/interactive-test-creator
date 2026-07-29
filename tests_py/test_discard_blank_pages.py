"""Tests for manual page discarding in 3_render_pdf_pages.py."""

import os
import sys
import subprocess
import fitz

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'python_scripts')
sys.path.insert(0, SCRIPTS_DIR)

from importlib import import_module
render_module = import_module("3_render_pdf_pages")
parse_page_ranges = render_module.parse_page_ranges

class TestDiscardPages:
    def test_parse_page_ranges_empty(self):
        assert parse_page_ranges("") == set()

    def test_parse_page_ranges_single_pages(self):
        assert parse_page_ranges("1, 3, 5") == {1, 3, 5}

    def test_parse_page_ranges_mixed(self):
        assert parse_page_ranges("1-4, 6, 8-10") == {1, 2, 3, 4, 6, 8, 9, 10}

    def test_parse_page_ranges_standard(self):
        assert parse_page_ranges("std", total_pages=10) == {1, 2, 3, 4, 6, 8, 10}
        assert parse_page_ranges("standard", total_pages=5) == {1, 2, 3, 4}
        assert parse_page_ranges("none", total_pages=10) == set()

    def test_render_pdf_pages_cli_discards_pages(self, tmp_path):
        """CLI rendering should skip saving pages specified in --discard-pages."""
        pdf_path = os.path.join(tmp_path, "sample_test.pdf")
        out_dir = os.path.join(tmp_path, "pages_output")

        doc = fitz.open()
        p1 = doc.new_page(width=595, height=842)
        p2 = doc.new_page(width=595, height=842)
        p3 = doc.new_page(width=595, height=842)
        p4 = doc.new_page(width=595, height=842)
        doc.save(pdf_path)
        doc.close()

        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "3_render_pdf_pages.py"), pdf_path, "-o", out_dir, "--discard-pages", "2, 4"],
            capture_output=True, text=True, encoding="utf-8"
        )

        assert result.returncode == 0
        assert os.path.exists(os.path.join(out_dir, "page_1.png"))
        assert not os.path.exists(os.path.join(out_dir, "page_2.png"))
        assert os.path.exists(os.path.join(out_dir, "page_3.png"))
        assert not os.path.exists(os.path.join(out_dir, "page_4.png"))
        assert "Skipped blank page 2" in result.stdout

    def test_render_pdf_pages_cli_creates_merged_pdf(self, tmp_path):
        """CLI rendering should save a merged PDF containing only non-discarded pages."""
        pdf_path = os.path.join(tmp_path, "sample_test.pdf")
        out_dir = os.path.join(tmp_path, "pages_output")
        merged_pdf_path = os.path.join(tmp_path, "clean_test.pdf")

        doc = fitz.open()
        doc.new_page(width=595, height=842)
        doc.new_page(width=595, height=842)
        doc.new_page(width=595, height=842)
        doc.save(pdf_path)
        doc.close()

        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "3_render_pdf_pages.py"), pdf_path, "-o", out_dir, "--discard-pages", "1-2", "--merged-pdf", merged_pdf_path],
            capture_output=True, text=True, encoding="utf-8"
        )

        assert result.returncode == 0
        assert os.path.exists(merged_pdf_path)
        
        merged_doc = fitz.open(merged_pdf_path)
        assert len(merged_doc) == 1  # Only 1 page left
        merged_doc.close()

