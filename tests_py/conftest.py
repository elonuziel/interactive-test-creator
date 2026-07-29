"""Shared fixtures for the quiz pipeline test suite."""

import json
import os
import sys

import pytest

# Add python_scripts to the import path
SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'python_scripts')
sys.path.insert(0, SCRIPTS_DIR)


@pytest.fixture
def write_md(tmp_path):
    """Fixture that returns a helper to write a .md file and return its path."""
    def _write(content, filename="test_input.md"):
        p = tmp_path / filename
        p.write_text(content, encoding='utf-8')
        return str(p)
    return _write


@pytest.fixture
def write_json(tmp_path):
    """Fixture that returns a helper to write a .json file and return its path."""
    def _write(data, filename="test_data.json"):
        p = tmp_path / filename
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        return str(p)
    return _write
