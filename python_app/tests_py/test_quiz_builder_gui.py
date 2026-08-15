"""
Unit tests for the Tkinter Desktop GUI Application in quiz_builder_gui.py
"""

import os
import sys
import tkinter as tk
import importlib.util
from pathlib import Path


def _load_gui_module():
    root = Path(__file__).resolve().parents[1]
    gui_path = root / 'quiz_builder_gui.py'
    spec = importlib.util.spec_from_file_location('quiz_builder_gui', str(gui_path))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_gui_themes_structure():
    gui = _load_gui_module()
    assert "dark" in gui.THEMES
    assert "light" in gui.THEMES

    required_keys = ["bg", "surface", "text_primary", "primary", "success", "border", "badge_built"]
    for theme_name in ["dark", "light"]:
        palette = gui.THEMES[theme_name]
        for key in required_keys:
            assert key in palette, f"Theme '{theme_name}' missing key '{key}'"


def test_gui_initialization_headless(tmp_path):
    gui = _load_gui_module()
    root = tk.Tk()
    root.withdraw()  # Headless mode (hide window during test)

    try:
        app = gui.QuizBuilderGUI(root, initial_dir=str(tmp_path))
        assert app is not None
        assert app.theme_name == "dark"
        assert app.target_dir == str(tmp_path)

        # Test theme toggle
        app.toggle_theme()
        assert app.theme_name == "light"

        # Test log queue
        app.log("Test log entry")
        assert not app.log_queue.empty()
    finally:
        root.destroy()
