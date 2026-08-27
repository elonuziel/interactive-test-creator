from __future__ import annotations

import json
from pathlib import Path
import webbrowser

from .batch import discover_batch
from .commands import generate_workspace_prompt, process_workspace, process_workspaces
from .config import Config
from .documents import classify_pdf
from .exporter import build_run_standalone_quiz
from .providers import WEB_PROVIDERS, detect_providers, open_web_provider
from .prompts import send_to_provider
from .preview import render_pdf_page
from .runs import RunError, assemble_run, write_run_questions
from .validation import ValidationError, load_questions
from .workspace import discover_sources

LITE_STYLESHEET = """
QWidget {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    color: #1e293b;
    font-size: 13px;
}

QTabWidget::pane {
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    background: #ffffff;
    top: -1px;
}

QTabBar::tab {
    background: #f1f5f9;
    color: #64748b;
    border: 1px solid #e2e8f0;
    border-bottom: none;
    padding: 10px 22px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: 600;
    font-size: 13px;
}

QTabBar::tab:selected {
    background: #ffffff;
    color: #2563eb;
    border-bottom: 2px solid #2563eb;
}

QTabBar::tab:hover:!selected {
    background: #e2e8f0;
    color: #334155;
}

QGroupBox {
    font-weight: 600;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    margin-top: 12px;
    padding: 14px 10px 10px 10px;
    background: #ffffff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: #475569;
}

QPushButton {
    background-color: #f1f5f9;
    color: #334155;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #e2e8f0;
    border-color: #94a3b8;
}

QPushButton:pressed {
    background-color: #cbd5e1;
}

QPushButton:disabled {
    background-color: #f8fafc;
    color: #94a3b8;
    border-color: #e2e8f0;
}

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 10px;
    color: #0f172a;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1.5px solid #3b82f6;
}

QListWidget {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 4px;
}

QListWidget::item {
    padding: 7px 10px;
    border-radius: 5px;
    margin-bottom: 2px;
}

QListWidget::item:selected {
    background-color: #e0e7ff;
    color: #1e1b4b;
    font-weight: 500;
}

QListWidget::item:hover:!selected {
    background-color: #f8fafc;
}
"""


def main() -> int:
    try:
        from PySide6.QtWidgets import (
            QApplication,
            QButtonGroup,
            QCheckBox,
            QComboBox,
            QFileDialog,
            QFrame,
            QGroupBox,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QListWidget,
            QListWidgetItem,
            QMessageBox,
            QPlainTextEdit,
            QPushButton,
            QRadioButton,
            QScrollArea,
            QTabWidget,
            QVBoxLayout,
            QWidget,
        )
        from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal
        from PySide6.QtGui import QImage, QPixmap
    except ImportError as exc:
        raise RuntimeError(
            "The GUI requires PySide6. Install it with: python -m pip install PySide6"
        ) from exc

    application = QApplication.instance() or QApplication([])
    application.setStyleSheet(LITE_STYLESHEET)

    class WorkerSignals(QObject):
        finished = Signal(object)
        failed = Signal(str)

    class Worker(QRunnable):
        def __init__(self, function):
            super().__init__()
            self.function = function
            self.signals = WorkerSignals()

        def run(self):
            try:
                self.signals.finished.emit(self.function())
            except Exception as exc:
                self.signals.failed.emit(str(exc))

    thread_pool = QThreadPool.globalInstance()

    window = QWidget()
    window.setWindowTitle("Interactive Quiz Builder")
    window.resize(1100, 760)
    main_layout = QVBoxLayout(window)
    main_layout.setSpacing(10)
    window.resize(1120, 780)
    window.setStyleSheet("background-color: #f8fafc;")

    # ── Top Bar: Folder Selection ──────────────────────────────────────────
    top_bar = QHBoxLayout()
    root_label = QLabel("Projects Folder: (no folder chosen)")
    root_label.setStyleSheet("font-weight: bold;")
    choose_root = QPushButton("📁 Choose projects folder")
    refresh_root = QPushButton("🔄 Refresh")
    top_bar.addWidget(root_label, 1)
    top_bar.addWidget(choose_root)
    top_bar.addWidget(refresh_root)
    main_layout.addLayout(top_bar)
    root_layout = QVBoxLayout(window)
    root_layout.setContentsMargins(14, 12, 14, 12)
    root_layout.setSpacing(10)

    # ── Center Area: 3-Column Layout ───────────────────────────────────────
    content = QHBoxLayout()
    content.setSpacing(10)
    # ── Top Bar: Folder Selection & Breadcrumb ─────────────────────────────
    top_bar = QFrame()
    top_bar.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 6px 12px;")
    top_layout = QHBoxLayout(top_bar)
    top_layout.setContentsMargins(4, 4, 4, 4)

    # Column 1: Test Projects List & Batch Selection
    projects_group = QGroupBox("1. Projects & Selection")
    projects_layout = QVBoxLayout(projects_group)
    tests = QListWidget()
    projects_layout.addWidget(tests)
    mix = QCheckBox("Mix questions from checked tests")
    projects_layout.addWidget(mix)
    content.addWidget(projects_group, 2)
    root_label = QLabel("📁 Projects Folder: (no folder chosen)")
    root_label.setStyleSheet("font-weight: 600; color: #1e293b;")
    choose_root_btn = QPushButton("📁 Choose Folder...")
    choose_root_btn.setStyleSheet("background-color: #2563eb; color: #ffffff; font-weight: 600; border-color: #1d4ed8;")
    refresh_root_btn = QPushButton("🔄 Refresh")

    # Column 2: Source PDF & Preview
    preview_group = QGroupBox("2. Source PDF & Preview")
    preview_layout = QVBoxLayout(preview_group)
    pdf_source_layout = QHBoxLayout()
    pdf_source_layout.addWidget(QLabel("PDF:"))
    pdf_source = QComboBox()
    pdf_source.addItem("No PDF selected", None)
    pdf_source_layout.addWidget(pdf_source, 1)
    preview_layout.addLayout(pdf_source_layout)
    top_layout.addWidget(root_label, 1)
    top_layout.addWidget(choose_root_btn)
    top_layout.addWidget(refresh_root_btn)
    root_layout.addWidget(top_bar)

    preview = QLabel("No PDF preview loaded")
    preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
    preview.setMinimumSize(260, 300)
    preview.setFrameShape(QFrame.Shape.StyledPanel)
    preview.setStyleSheet("background-color: #f5f5f5; border: 1px solid #ddd;")
    preview_layout.addWidget(preview, 1)
    # ── Main 3-Tab Stepper ─────────────────────────────────────────────────
    tabs = QTabWidget()
    root_layout.addWidget(tabs, 1)

    preview_button = QPushButton("🔍 Preview first page")
    preview_layout.addWidget(preview_button)
    content.addWidget(preview_group, 3)
    state = {
        "root": None,
        "workspace": None,
        "questions": [],
        "index": -1,
        "is_digital": None,
        "batch_candidates": [],
    }

    # Column 3: Question Editor
    editor_group = QGroupBox("3. Hebrew Question Editor (RTL)")
    editor_layout = QVBoxLayout(editor_group)
    question_list = QListWidget()
    editor_layout.addWidget(question_list, 1)
    # =========================================================================
    # TAB 1: 📄 1. Select & Extract Exam
    # =========================================================================
    tab1 = QWidget()
    tab1_layout = QHBoxLayout(tab1)
    tab1_layout.setContentsMargins(10, 10, 10, 10)
    tab1_layout.setSpacing(12)

    question_text_label = QLabel("Question Text:")
    editor_layout.addWidget(question_text_label)
    question_text = QLineEdit()
    question_text.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    question_text.setPlaceholderText("טקסט השאלה...")
    editor_layout.addWidget(question_text)
    # Left: Exam list & search
    tab1_left = QGroupBox("Exams in Folder")
    tab1_left_layout = QVBoxLayout(tab1_left)
    tab1_left_layout.setSpacing(8)

    editor_layout.addWidget(QLabel("Answer Options:"))
    option_fields = [QLineEdit() for _ in range(4)]
    placeholders = ["אפשרות 1 (א)...", "אפשרות 2 (ב)...", "אפשרות 3 (ג)...", "אפשרות 4 (ד)..."]
    for field, placeholder in zip(option_fields, placeholders):
        field.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        field.setPlaceholderText(placeholder)
        editor_layout.addWidget(field)
    exam_search = QLineEdit()
    exam_search.setPlaceholderText("🔍 Filter exams...")
    tab1_left_layout.addWidget(exam_search)

    correct_layout = QHBoxLayout()
    correct_layout.addWidget(QLabel("Correct Answer:"))
    correct_index = QComboBox()
    correct_index.addItems([
        "Option 1 (א)",
        "Option 2 (ב)",
        "Option 3 (ג)",
        "Option 4 (ד)",
    ])
    correct_layout.addWidget(correct_index, 1)
    editor_layout.addLayout(correct_layout)
    tab1_exam_list = QListWidget()
    tab1_left_layout.addWidget(tab1_exam_list, 1)

    question_actions = QHBoxLayout()
    add_question = QPushButton("➕ Add question")
    remove_question = QPushButton("➖ Remove question")
    save_project = QPushButton("💾 Save test")
    question_actions.addWidget(add_question)
    question_actions.addWidget(remove_question)
    question_actions.addWidget(save_project)
    editor_layout.addLayout(question_actions)
    content.addWidget(editor_group, 4)
    batch_proc_btn = QPushButton("⚡ Process Checked Exams")
    batch_proc_btn.setStyleSheet("background-color: #f1f5f9; color: #334155; font-weight: 600;")
    tab1_left_layout.addWidget(batch_proc_btn)
    tab1_layout.addWidget(tab1_left, 4)

    main_layout.addLayout(content, 1)
    # Right: Source PDF, Smart Detection, Preview & Actions
    tab1_right = QGroupBox("Document Inspection & Extraction")
    tab1_right_layout = QVBoxLayout(tab1_right)
    tab1_right_layout.setSpacing(10)

    # ── Bottom Control Panels: Action Groups ───────────────────────────────
    bottom_panels = QHBoxLayout()
    bottom_panels.setSpacing(10)
    # Header with active exam name
    current_exam_title = QLabel("Select an exam from the list")
    current_exam_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #0f172a;")
    tab1_right_layout.addWidget(current_exam_title)

    # Action Group 1: Pipeline & Extraction
    process_group = QGroupBox("Pipeline & Extraction")
    process_layout = QVBoxLayout(process_group)
    key_form_layout = QHBoxLayout()
    key_form_layout.addWidget(QLabel("Key:"))
    answer_key = QComboBox()
    answer_key.addItem("No answer key", None)
    key_form_layout.addWidget(answer_key, 1)
    key_form_layout.addWidget(QLabel("Form:"))
    form_number = QLineEdit("0")
    form_number.setMaximumWidth(60)
    key_form_layout.addWidget(form_number)
    process_layout.addLayout(key_form_layout)
    # PDF source picker
    pdf_source_row = QHBoxLayout()
    pdf_source_row.addWidget(QLabel("Source PDF:"))
    pdf_source_combo = QComboBox()
    pdf_source_combo.addItem("No PDF selected", None)
    pdf_source_row.addWidget(pdf_source_combo, 1)
    tab1_right_layout.addLayout(pdf_source_row)

    proc_btn_layout = QHBoxLayout()
    process_button = QPushButton("⚙️ Process selected test")
    process_batch_button = QPushButton("⚡ Process checked")
    proc_btn_layout.addWidget(process_button)
    proc_btn_layout.addWidget(process_batch_button)
    process_layout.addLayout(proc_btn_layout)
    bottom_panels.addWidget(process_group, 3)
    # Smart Detection Banner
    detection_card = QFrame()
    detection_card.setStyleSheet("background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 10px;")
    detection_layout = QVBoxLayout(detection_card)
    detection_layout.setContentsMargins(6, 6, 6, 6)
    detection_title = QLabel("🔍 Auto-Detection: Select a PDF")
    detection_title.setStyleSheet("font-weight: bold; color: #166534;")
    detection_desc = QLabel("The builder will analyze whether this is a digital or scanned exam.")
    detection_desc.setStyleSheet("color: #15803d; font-size: 12px;")
    detection_layout.addWidget(detection_title)
    detection_layout.addWidget(detection_desc)
    tab1_right_layout.addWidget(detection_card)

    # Action Group 2: AI Assistance
    ai_group = QGroupBox("AI Prompts & Assistance")
    ai_layout = QVBoxLayout(ai_group)
    provider_layout = QHBoxLayout()
    provider_layout.addWidget(QLabel("Target:"))
    provider = QComboBox()
    for web_provider in WEB_PROVIDERS:
        provider.addItem(web_provider.label, (web_provider, None))
    for local_provider, command in detect_providers():
        provider.addItem(f"{local_provider.label} ({command})", (local_provider, command))
    provider_layout.addWidget(provider, 1)
    ai_layout.addLayout(provider_layout)
    # Extraction Actions
    action_box = QFrame()
    action_box.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px;")
    action_box_layout = QVBoxLayout(action_box)
    action_box_layout.setSpacing(8)

    ai_btn_layout = QHBoxLayout()
    launch_provider = QPushButton("🚀 Launch provider")
    prompt_button = QPushButton("📄 Offline prompt")
    ai_btn_layout.addWidget(launch_provider)
    ai_btn_layout.addWidget(prompt_button)
    ai_layout.addLayout(ai_btn_layout)
    bottom_panels.addWidget(ai_group, 3)
    extract_digital_btn = QPushButton("⚡ Extract Questions Automatically (Digital)")
    extract_digital_btn.setStyleSheet("background-color: #16a34a; color: #ffffff; font-weight: bold; padding: 9px; font-size: 13px;")
    action_box_layout.addWidget(extract_digital_btn)

    # Action Group 3: Standalone Quiz Run
    run_group = QGroupBox("Standalone Quiz Run")
    run_layout = QVBoxLayout(run_group)
    run_button = QPushButton("▶️ Prepare & Open Standalone Quiz")
    run_button.setStyleSheet("font-weight: bold; padding: 10px;")
    run_layout.addWidget(run_button)
    bottom_panels.addWidget(run_group, 2)
    ai_row = QHBoxLayout()
    ai_provider_combo = QComboBox()
    for web_p in WEB_PROVIDERS:
        ai_provider_combo.addItem(f"Web: {web_p.label}", (web_p, None))
    for local_p, cmd in detect_providers():
        ai_provider_combo.addItem(f"Local: {local_p.label} ({cmd})", (local_p, cmd))

    main_layout.addLayout(bottom_panels)
    launch_ai_btn = QPushButton("🤖 Generate AI Prompt & Launch")
    launch_ai_btn.setStyleSheet("background-color: #6366f1; color: #ffffff; font-weight: 600; padding: 8px;")
    ai_row.addWidget(ai_provider_combo, 2)
    ai_row.addWidget(launch_ai_btn, 3)
    action_box_layout.addLayout(ai_row)

    # ── Status Bar ─────────────────────────────────────────────────────────
    # Expandable Answer Key row
    key_row = QHBoxLayout()
    key_row.addWidget(QLabel("Answer Key:"))
    answer_key_combo = QComboBox()
    answer_key_combo.addItem("No answer key", None)
    key_row.addWidget(answer_key_combo, 2)
    key_row.addWidget(QLabel("Form:"))
    form_num_edit = QLineEdit("0")
    form_num_edit.setMaximumWidth(50)
    key_row.addWidget(form_num_edit)
    action_box_layout.addLayout(key_row)

    tab1_right_layout.addWidget(action_box)

    # PDF Preview viewport
    preview_row = QHBoxLayout()
    tab1_preview = QLabel("No PDF preview loaded")
    tab1_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
    tab1_preview.setMinimumSize(280, 240)
    tab1_preview.setFrameShape(QFrame.Shape.StyledPanel)
    tab1_preview.setStyleSheet("background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px;")
    preview_row.addWidget(tab1_preview, 1)
    tab1_right_layout.addLayout(preview_row, 1)

    tab1_bottom_nav = QHBoxLayout()
    preview_btn = QPushButton("🔍 Preview First Page")
    proceed_to_step2_btn = QPushButton("Next: Review & Edit Questions ➡️")
    proceed_to_step2_btn.setStyleSheet("background-color: #2563eb; color: #ffffff; font-weight: bold; padding: 8px 16px;")
    tab1_bottom_nav.addWidget(preview_btn)
    tab1_bottom_nav.addStretch()
    tab1_bottom_nav.addWidget(proceed_to_step2_btn)
    tab1_right_layout.addLayout(tab1_bottom_nav)

    tab1_layout.addWidget(tab1_right, 6)
    tabs.addTab(tab1, "📄 1. Select & Extract Exam")

    # =========================================================================
    # TAB 2: ✏️ 2. Review & Edit Questions
    # =========================================================================
    tab2 = QWidget()
    tab2_layout = QHBoxLayout(tab2)
    tab2_layout.setContentsMargins(10, 10, 10, 10)
    tab2_layout.setSpacing(12)

    # Left: Questions List & Validation Status
    tab2_left = QGroupBox("Exam Questions")
    tab2_left_layout = QVBoxLayout(tab2_left)
    tab2_left_layout.setSpacing(8)

    q_status_badge = QLabel("No exam loaded")
    q_status_badge.setStyleSheet("background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 8px; font-weight: 600; color: #475569;")
    tab2_left_layout.addWidget(q_status_badge)

    q_list = QListWidget()
    tab2_left_layout.addWidget(q_list, 1)

    q_list_actions = QHBoxLayout()
    add_q_btn = QPushButton("➕ Add Question")
    del_q_btn = QPushButton("🗑️ Delete")
    del_q_btn.setStyleSheet("background-color: #fee2e2; color: #991b1b; border-color: #fca5a5;")
    q_list_actions.addWidget(add_q_btn)
    q_list_actions.addWidget(del_q_btn)
    tab2_left_layout.addLayout(q_list_actions)
    tab2_layout.addWidget(tab2_left, 4)

    # Right: Question Editor Form (Hebrew RTL)
    tab2_right = QGroupBox("Hebrew Question Editor (RTL)")
    tab2_right_layout = QVBoxLayout(tab2_right)
    tab2_right_layout.setSpacing(10)

    tab2_right_layout.addWidget(QLabel("Question Text (נוסח השאלה):"))
    q_text_edit = QPlainTextEdit()
    q_text_edit.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    q_text_edit.setPlaceholderText("הקלד את נוסח השאלה בעברית...")
    q_text_edit.setMaximumHeight(110)
    tab2_right_layout.addWidget(q_text_edit)

    tab2_right_layout.addWidget(QLabel("Answer Options & Correct Answer (בחר את התשובה הנכונה):"))

    option_edits = []
    option_radios = []
    radio_group = QButtonGroup(window)

    hebrew_letters = ["א.", "ב.", "ג.", "ד."]
    for idx, letter in enumerate(hebrew_letters):
        opt_row = QHBoxLayout()
        radio = QRadioButton()
        radio_group.addButton(radio, idx)
        if idx == 0:
            radio.setChecked(True)
        option_radios.append(radio)

        badge = QLabel(f"  {letter}  ")
        badge.setStyleSheet("background: #e2e8f0; font-weight: bold; border-radius: 4px; padding: 4px;")

        opt_edit = QLineEdit()
        opt_edit.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        opt_edit.setPlaceholderText(f"אפשרות {letter}...")
        option_edits.append(opt_edit)

        opt_row.addWidget(radio)
        opt_row.addWidget(badge)
        opt_row.addWidget(opt_edit, 1)
        tab2_right_layout.addLayout(opt_row)

    tab2_right_layout.addStretch()

    # Save & Proceed Bar
    tab2_actions = QHBoxLayout()
    save_test_btn = QPushButton("💾 Save Test Changes")
    save_test_btn.setStyleSheet("background-color: #16a34a; color: #ffffff; font-weight: bold; padding: 8px 16px;")
    proceed_to_step3_btn = QPushButton("Next: Play & Export Quiz ➡️")
    proceed_to_step3_btn.setStyleSheet("background-color: #2563eb; color: #ffffff; font-weight: bold; padding: 8px 16px;")
    tab2_actions.addWidget(save_test_btn)
    tab2_actions.addStretch()
    tab2_actions.addWidget(proceed_to_step3_btn)
    tab2_right_layout.addLayout(tab2_actions)

    tab2_layout.addWidget(tab2_right, 6)
    tabs.addTab(tab2, "✏️ 2. Review & Edit Questions")

    # =========================================================================
    # TAB 3: 🎯 3. Play & Export Quiz
    # =========================================================================
    tab3 = QWidget()
    tab3_layout = QHBoxLayout(tab3)
    tab3_layout.setContentsMargins(14, 14, 14, 14)
    tab3_layout.setSpacing(14)

    # Left: Exam Selection Checklist
    tab3_left = QGroupBox("Select Practice Exams")
    tab3_left_layout = QVBoxLayout(tab3_left)
    tab3_left_layout.setSpacing(8)

    tab3_exam_list = QListWidget()
    tab3_left_layout.addWidget(tab3_exam_list, 1)

    check_controls = QHBoxLayout()
    select_all_btn = QPushButton("Select All")
    clear_all_btn = QPushButton("Clear All")
    check_controls.addWidget(select_all_btn)
    check_controls.addWidget(clear_all_btn)
    tab3_left_layout.addLayout(check_controls)

    mix_checkbox = QCheckBox("🔀 Mix and shuffle questions across selected exams")
    mix_checkbox.setStyleSheet("font-weight: 600; color: #1e293b; padding: 4px 0;")
    tab3_left_layout.addWidget(mix_checkbox)
    tab3_layout.addWidget(tab3_left, 5)

    # Right: Summary & Action Card
    tab3_right = QGroupBox("Launch & Export Standalone Quiz")
    tab3_right_layout = QVBoxLayout(tab3_right)
    tab3_right_layout.setSpacing(12)

    # Summary card
    summary_card = QFrame()
    summary_card.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 14px;")
    summary_layout = QVBoxLayout(summary_card)
    summary_title = QLabel("📊 Quiz Configuration Summary")
    summary_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #0f172a;")
    summary_questions_count = QLabel("• Total questions selected: 0")
    summary_questions_count.setStyleSheet("font-size: 13px; color: #334155;")
    summary_sources_count = QLabel("• Selected exams: None")
    summary_sources_count.setStyleSheet("font-size: 13px; color: #334155;")
    summary_mode = QLabel("• Mode: Single Exam")
    summary_mode.setStyleSheet("font-size: 13px; color: #334155;")
    summary_layout.addWidget(summary_title)
    summary_layout.addWidget(summary_questions_count)
    summary_layout.addWidget(summary_sources_count)
    summary_layout.addWidget(summary_mode)
    tab3_right_layout.addWidget(summary_card)

    # Launch buttons
    play_browser_btn = QPushButton("🚀 Play Interactive Quiz in Browser Now")
    play_browser_btn.setStyleSheet("""
        QPushButton {
            background-color: #2563eb;
            color: #ffffff;
            font-size: 16px;
            font-weight: bold;
            border-radius: 8px;
            padding: 14px;
        }
        QPushButton:hover {
            background-color: #1d4ed8;
        }
    """)
    tab3_right_layout.addWidget(play_browser_btn)

    export_html_btn = QPushButton("📦 Export Standalone HTML Quiz File...")
    export_html_btn.setStyleSheet("font-size: 13px; font-weight: 600; padding: 10px;")
    tab3_right_layout.addWidget(export_html_btn)

    open_runs_dir_btn = QPushButton("📁 Open Runs Folder")
    tab3_right_layout.addWidget(open_runs_dir_btn)

    tab3_right_layout.addStretch()
    tab3_layout.addWidget(tab3_right, 5)
    tabs.addTab(tab3, "🎯 3. Play & Export Quiz")

    # ── Bottom Global Status Bar ───────────────────────────────────────────
    status_bar = QFrame()
    status_bar.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 4px 10px;")
    status_layout = QHBoxLayout(status_bar)
    status_layout.setContentsMargins(4, 2, 4, 2)
    status_label = QLabel("Ready")
    status_label.setStyleSheet("color: #555; padding: 2px;")
    main_layout.addWidget(status_label)
    status_label.setStyleSheet("color: #64748b; font-size: 12px;")
    status_layout.addWidget(status_label, 1)
    root_layout.addWidget(status_bar)

    state = {"root": None, "workspace": None, "questions": [], "index": -1}
    # =========================================================================
    # CORE LOGIC & EVENT HANDLERS
    # =========================================================================

    def get_selected_workspaces_for_play() -> list:
        selected = []
        for i in range(tab3_exam_list.count()):
            item = tab3_exam_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.data(Qt.ItemDataRole.UserRole))
        if not selected and state["workspace"]:
            selected.append(state["workspace"])
        return selected

    def update_tab3_summary() -> None:
        selected = get_selected_workspaces_for_play()
        total_q = 0
        names = []
        for ws in selected:
            names.append(ws.name)
            if ws.questions_path.is_file():
                try:
                    total_q += len(json.loads(ws.questions_path.read_text(encoding="utf-8")))
                except Exception:
                    pass
        is_mix = mix_checkbox.isChecked()
        summary_questions_count.setText(f"• Total questions ready: {total_q}")
        summary_sources_count.setText(f"• Selected exams ({len(selected)}): {', '.join(names) if names else 'None'}")
        summary_mode.setText(f"• Mode: {'🔀 Mixed / Shuffled Questions' if is_mix else 'Standard Sequential Run'}")

    def save_active_question() -> None:
        idx = state["index"]
        if idx < 0 or idx >= len(state["questions"]):
            return
        question = state["questions"][idx]
        question["question"] = q_text_edit.toPlainText().strip()
        question["options"] = [field.text().strip() for field in option_edits if field.text().strip()]
        question["correctIndex"] = radio_group.checkedId() if radio_group.checkedId() >= 0 else 0

        # Update status icon in list
        item = q_list.item(idx)
        if item:
            valid = bool(question["question"] and len(question["options"]) >= 2)
            prefix = "✓" if valid else "⚠️"
            title = (question["question"] or "שאלה ריקה")[:70]
            item.setText(f"{prefix} {idx + 1}. {title}")

    def update_editor_fields(question: dict | None) -> None:
        if question is None:
            question_text.clear()
            for field in option_fields:
                field.clear()
            correct_index.setCurrentIndex(0)
            q_text_edit.clear()
            for opt_field in option_edits:
                opt_field.clear()
            if option_radios:
                option_radios[0].setChecked(True)
            return
        question_text.setText(question.get("question", ""))

        q_text_edit.setPlainText(question.get("question", ""))
        options = question.get("options", [])
        for option_number, field in enumerate(option_fields):
            field.setText(options[option_number] if option_number < len(options) else "")
        answer = question.get("correctIndex", 0)
        correct_index.setCurrentIndex(answer if isinstance(answer, int) and 0 <= answer < 4 else 0)
        for i, opt_field in enumerate(option_edits):
            opt_field.setText(options[i] if i < len(options) else "")
        ans_idx = question.get("correctIndex", 0)
        if isinstance(ans_idx, int) and 0 <= ans_idx < len(option_radios):
            option_radios[ans_idx].setChecked(True)
        elif option_radios:
            option_radios[0].setChecked(True)

    def refresh_question_list_labels() -> None:
        question_list.clear()
        for number, question in enumerate(state["questions"], 1):
            title = (question.get("question", "") or "שאלה ללא טקסט").strip()[:80]
            question_list.addItem(f"{number}. {title}")

    def save_question() -> None:
        index = state["index"]
        if index < 0 or index >= len(state["questions"]):
            return
        question = state["questions"][index]
        question["question"] = question_text.text()
        question["options"] = [field.text() for field in option_fields if field.text()]
        question["correctIndex"] = correct_index.currentIndex()
        item = question_list.item(index)
        if item:
            title = (question["question"] or "שאלה ללא טקסט").strip()[:80]
            item.setText(f"{index + 1}. {title}")

    def show_question(index: int) -> None:
        save_question()
        save_active_question()
        state["index"] = index
        if 0 <= index < len(state["questions"]):
            update_editor_fields(state["questions"][index])
        else:
            update_editor_fields(None)

    def refresh_question_list_ui() -> None:
        q_list.clear()
        valid_count = 0
        for i, q in enumerate(state["questions"], 1):
            q_text = (q.get("question", "") or "").strip()
            opts = q.get("options", [])
            is_valid = bool(q_text and len(opts) >= 2)
            if is_valid:
                valid_count += 1
            prefix = "✓" if is_valid else "⚠️"
            title = (q_text or "שאלה ללא טקסט")[:70]
            q_list.addItem(f"{prefix} {i}. {title}")

        total = len(state["questions"])
        if total > 0:
            if valid_count == total:
                q_status_badge.setText(f"✓ All {total} Questions Valid & Ready")
                q_status_badge.setStyleSheet("background: #dcfce7; border: 1px solid #86efac; border-radius: 4px; padding: 4px 8px; font-weight: 600; color: #166534;")
            else:
                q_status_badge.setText(f"⚠️ {valid_count}/{total} Valid ({total - valid_count} need review)")
                q_status_badge.setStyleSheet("background: #fef9c3; border: 1px solid #fde047; border-radius: 4px; padding: 4px 8px; font-weight: 600; color: #854d0e;")
        else:
            q_status_badge.setText("No questions in this test")
            q_status_badge.setStyleSheet("background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 8px; font-weight: 600; color: #475569;")

    def check_pdf_classification(pdf_path: Path) -> None:
        def run_classify():
            try:
                return classify_pdf(pdf_path)
            except Exception:
                return None

        detection_title.setText("🔍 Analyzing PDF type...")
        detection_desc.setText("Inspecting text streams and structure...")
        detection_card.setStyleSheet("background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px;")

        worker = Worker(run_classify)

        def on_classify_done(is_digital):
            state["is_digital"] = is_digital
            if is_digital is True:
                detection_title.setText("✨ Digital PDF Detected (Extractable Text)")
                detection_desc.setText("This exam has clean text. Click 'Extract Questions Automatically' for instant conversion.")
                detection_card.setStyleSheet("background: #f0fdf4; border: 1px solid #86efac; border-radius: 6px; padding: 10px;")
                extract_digital_btn.setEnabled(True)
            elif is_digital is False:
                detection_title.setText("📷 Scanned / Vector PDF Detected (Images Only)")
                detection_desc.setText("This exam requires AI vision/rendering. Click 'Generate AI Prompt' to extract questions.")
                detection_card.setStyleSheet("background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; padding: 10px;")
            else:
                detection_title.setText("📄 Document Ready")
                detection_desc.setText("Select extraction mode below.")
                detection_card.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px;")

        worker.signals.finished.connect(on_classify_done)
        thread_pool.start(worker)

    def load_workspace(workspace) -> None:
        if workspace is None:
            state["workspace"] = None
            state["questions"] = []
            state["index"] = -1
            question_list.clear()
            current_exam_title.setText("Select an exam from the list")
            update_editor_fields(None)
            pdf_source.clear()
            pdf_source.addItem("No PDF selected", None)
            answer_key.clear()
            answer_key.addItem("No answer key", None)
            refresh_question_list_ui()
            return

        pdf_source.clear()
        state["workspace"] = workspace
        state["index"] = -1
        current_exam_title.setText(f"Exam: {workspace.name}")

        # Update PDF dropdown
        pdf_source_combo.clear()
        pdf_paths = [workspace.source_pdf] if workspace.source_pdf else (
            sorted(
                (item for item in workspace.path.iterdir() if item.is_file() and item.suffix.lower() == ".pdf"),
                key=lambda item: item.name.lower(),
                (p for p in workspace.path.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"),
                key=lambda p: p.name.lower(),
            )
            if workspace.path.is_dir()
            else []
        )
        for path in pdf_paths:
            if path:
                pdf_source.addItem(path.name, path)
        if pdf_source.count() == 0:
            pdf_source.addItem("No PDF selected", None)
        for p in pdf_paths:
            if p:
                pdf_source_combo.addItem(p.name, p)
        if pdf_source_combo.count() == 0:
            pdf_source_combo.addItem("No PDF selected", None)

        answer_key.clear()
        answer_key.addItem("No answer key", None)
        for path in discover_sources(workspace).answer_keys:
            answer_key.addItem(path.name, path)
        # Update Answer Keys dropdown
        answer_key_combo.clear()
        answer_key_combo.addItem("No answer key", None)
        for key_path in discover_sources(workspace).answer_keys:
            answer_key_combo.addItem(key_path.name, key_path)

        state["workspace"] = workspace
        state["index"] = -1
        # Smart classification
        chosen_pdf = pdf_source_combo.currentData()
        if chosen_pdf and chosen_pdf.is_file():
            check_pdf_classification(chosen_pdf)
            # Auto-preview
            preview_first_page(chosen_pdf)

        # Load questions for Step 2
        try:
            questions = load_questions(workspace.questions_path)
            state["questions"] = questions
            refresh_question_list_labels()
            refresh_question_list_ui()
            if questions:
                question_list.setCurrentRow(0)
                q_list.setCurrentRow(0)
            else:
                update_editor_fields(None)
            status_label.setText(f"Loaded {workspace.name} ({len(questions)} questions)")
        except (ValidationError, OSError):
            state["questions"] = []
            question_list.clear()
            refresh_question_list_ui()
            update_editor_fields(None)
            status_label.setText(f"Selected {workspace.name} (no questions.json yet)")
            status_label.setText(f"Selected {workspace.name} (not extracted yet)")

    def save_workspace() -> None:
        workspace = state["workspace"]
        if workspace is None:
            QMessageBox.warning(window, "No test selected", "Choose a test first.")
        update_tab3_summary()

    def preview_first_page(pdf_path: Path | None = None) -> None:
        target = pdf_path or pdf_source_combo.currentData()
        if not target or not Path(target).is_file():
            tab1_preview.setText("No PDF selected to preview")
            return
        save_question()
        workspace.questions_path.parent.mkdir(parents=True, exist_ok=True)
        workspace.questions_path.write_text(
            json.dumps(state["questions"], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        status_label.setText(f"Saved {len(state['questions'])} questions to {workspace.questions_path.name}")
        QMessageBox.information(window, "Saved", f"Successfully saved {len(state['questions'])} question(s) to:\n{workspace.questions_path}")

    def populate_tests_list() -> None:
        tab1_preview.setText("Rendering PDF preview...")
        status_label.setText(f"Rendering page preview for {target.name}...")

        worker = Worker(lambda: render_pdf_page(target))

        def on_preview_ready(image_bytes):
            pixmap = QPixmap.fromImage(QImage.fromData(image_bytes))
            tab1_preview.setPixmap(
                pixmap.scaled(
                    tab1_preview.width() - 10,
                    tab1_preview.height() - 10,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            status_label.setText(f"Preview loaded for {target.name}")

        worker.signals.finished.connect(on_preview_ready)
        worker.signals.failed.connect(lambda err: (tab1_preview.setText(f"Preview error: {err}"), status_label.setText("Preview failed")))
        thread_pool.start(worker)

    def populate_tests() -> None:
        if state["root"] is None:
            return
        tests.clear()
        for candidate in discover_batch(state["root"]):
            label = candidate.workspace.name
            if candidate.issues:
                label += f"  ({'; '.join(candidate.issues)})"
            item = QListWidgetItem(label, tests)
            item.setData(Qt.ItemDataRole.UserRole, candidate.workspace)
            item.setCheckState(Qt.CheckState.Unchecked)
        root_label.setText(f"Projects Folder: {state['root']}")
        status_label.setText(f"Discovered {tests.count()} project(s) in {state['root'].name}")
        candidates = discover_batch(state["root"])
        state["batch_candidates"] = candidates

    def refresh() -> None:
        root = QFileDialog.getExistingDirectory(window, "Choose projects folder")
        if not root:
            return
        state["root"] = Path(root)
        populate_tests_list()
        tab1_exam_list.clear()
        tab3_exam_list.clear()

    def prepare() -> None:
        selected = [
            tests.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(tests.count())
            if tests.item(index).checkState() == Qt.CheckState.Checked
        ]
        if not selected and state["workspace"]:
            selected = [state["workspace"]]
        for c in candidates:
            label = c.workspace.name
            if c.issues:
                label += f"  ({'; '.join(c.issues)})"

        if not selected:
            QMessageBox.warning(window, "No tests selected", "Select or check at least one test first.")
            return
            # Tab 1 List
            item1 = QListWidgetItem(label, tab1_exam_list)
            item1.setData(Qt.ItemDataRole.UserRole, c.workspace)
            item1.setCheckState(Qt.CheckState.Unchecked)

        try:
            save_question()
            run = assemble_run(selected, mix=mix.isChecked())
            root = state["root"] or (selected[0].path.parent if selected else None)
            if root is None:
                raise RunError("Choose a projects folder first.")
            output = root / "runs" / f"{run.name}.json"
            write_run_questions(run, output)
            html_output = output.with_suffix(".html")
            build_run_standalone_quiz(run, html_output)
        except RunError as exc:
            QMessageBox.warning(window, "Cannot prepare run", str(exc))
            # Tab 3 List
            item3 = QListWidgetItem(label, tab3_exam_list)
            item3.setData(Qt.ItemDataRole.UserRole, c.workspace)
            item3.setCheckState(Qt.CheckState.Checked if c.ready_to_run else Qt.CheckState.Unchecked)

        root_label.setText(f"📁 Projects Folder: {state['root']}")
        status_label.setText(f"Found {len(candidates)} test project(s) in {state['root'].name}")
        if candidates:
            tab1_exam_list.setCurrentRow(0)

        update_tab3_summary()

    def choose_folder() -> None:
        chosen = QFileDialog.getExistingDirectory(window, "Choose Projects Folder")
        if not chosen:
            return
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.critical(window, "Cannot export run", str(exc))
            return
        webbrowser.open(html_output.as_uri())
        status_label.setText(f"Prepared run: {html_output.name}")
        QMessageBox.information(
            window,
            "Run prepared",
            f"{len(run.questions)} question(s) from {len(run.sources)} test(s)\n{html_output}",
        )
        state["root"] = Path(chosen)
        populate_tests()

    def process_selected() -> None:
        workspace = state["workspace"]
        root = state["root"] or (workspace.path.parent if workspace else None)
        if workspace is None or root is None:
            QMessageBox.warning(window, "No test selected", "Choose a test first.")
    def filter_exams(query: str) -> None:
        query = query.strip().lower()
        for i in range(tab1_exam_list.count()):
            item = tab1_exam_list.item(i)
            item.setHidden(query not in item.text().lower())

    def process_selected_exam() -> None:
        ws = state["workspace"]
        root = state["root"] or (ws.path.parent if ws else None)
        if not ws or not root:
            QMessageBox.warning(window, "No exam selected", "Select an exam from the list first.")
            return
        process_button.setEnabled(False)
        process_batch_button.setEnabled(False)
        run_button.setEnabled(False)
        status_label.setText(f"Processing {workspace.name}...")

        selected_answer_key = answer_key.currentData()
        selected_pdf = pdf_source.currentData()
        extract_digital_btn.setEnabled(False)
        launch_ai_btn.setEnabled(False)
        status_label.setText(f"Processing {ws.name}...")

        sel_key = answer_key_combo.currentData()
        sel_pdf = pdf_source_combo.currentData()
        f_num = form_num_edit.text().strip() or "0"

        worker = Worker(
            lambda: process_workspace(
                Config.defaults(root=root),
                workspace.path,
                selected_answer_key,
                form_number.text().strip() or "0",
                selected_pdf,
                ws.path,
                sel_key,
                f_num,
                sel_pdf,
            )
        )
        worker.signals.finished.connect(
            lambda _result: (
                process_button.setEnabled(True),
                process_batch_button.setEnabled(True),
                run_button.setEnabled(True),
                status_label.setText(f"Processed {workspace.name}"),
                load_workspace(workspace),

        def on_done(_res):
            extract_digital_btn.setEnabled(True)
            launch_ai_btn.setEnabled(True)
            status_label.setText(f"Extraction complete for {ws.name}")
            load_workspace(ws)
            reply = QMessageBox.information(
                window,
                "Extraction Complete",
                f"Successfully extracted {ws.name}!\nWould you like to review and edit the questions now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
        )
        worker.signals.failed.connect(
            lambda message: (
                process_button.setEnabled(True),
                process_batch_button.setEnabled(True),
                run_button.setEnabled(True),
                status_label.setText("Processing failed"),
                QMessageBox.critical(window, "Cannot process test", message),
            )
        )
            if reply == QMessageBox.StandardButton.Yes:
                tabs.setCurrentIndex(1)

        def on_fail(err):
            extract_digital_btn.setEnabled(True)
            launch_ai_btn.setEnabled(True)
            status_label.setText("Extraction failed")
            QMessageBox.critical(window, "Extraction Failed", err)

        worker.signals.finished.connect(on_done)
        worker.signals.failed.connect(on_fail)
        thread_pool.start(worker)

    def process_batch() -> None:
    def process_batch_checked() -> None:
        root = state["root"]
        selected = [
            tests.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(tests.count())
            if tests.item(index).checkState() == Qt.CheckState.Checked
            tab1_exam_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(tab1_exam_list.count())
            if tab1_exam_list.item(i).checkState() == Qt.CheckState.Checked
        ]
        if root is None or not selected:
            QMessageBox.warning(window, "No tests checked", "Check at least one test in the list first.")
        if not root or not selected:
            QMessageBox.warning(window, "No exams checked", "Check the boxes next to the exams you want to batch-process.")
            return
        process_batch_button.setEnabled(False)
        process_button.setEnabled(False)
        run_button.setEnabled(False)
        status_label.setText(f"Processing {len(selected)} test(s)...")

        def process_all():
            results = process_workspaces(
                Config.defaults(root=root), selected
            )
        batch_proc_btn.setEnabled(False)
        status_label.setText(f"Batch processing {len(selected)} exam(s)...")

        def run_all():
            results = process_workspaces(Config.defaults(root=root), selected)
            return (
                [result.workspace.name for result in results if result.success],
                [f"{result.workspace.name}: {result.error}" for result in results if not result.success],
                [r.workspace.name for r in results if r.success],
                [f"{r.workspace.name}: {r.error}" for r in results if not r.success],
            )

        worker = Worker(process_all)
        worker.signals.finished.connect(
            lambda result: (
                process_batch_button.setEnabled(True),
                process_button.setEnabled(True),
                run_button.setEnabled(True),
                status_label.setText(f"Batch complete: {len(result[0])} succeeded"),
                load_workspace(state["workspace"]) if state["workspace"] else None,
                QMessageBox.information(
                    window,
                    "Batch processing complete",
                    "Succeeded: " + (", ".join(result[0]) or "none")
                    + "\nFailed: " + ("\n".join(result[1]) or "none"),
                ),
        worker = Worker(run_all)

        def on_batch_done(res):
            batch_proc_btn.setEnabled(True)
            status_label.setText(f"Batch complete: {len(res[0])} succeeded")
            if state["workspace"]:
                load_workspace(state["workspace"])
            QMessageBox.information(
                window,
                "Batch Processing Complete",
                f"Succeeded: {', '.join(res[0]) or 'None'}\nFailed: {'\n'.join(res[1]) or 'None'}",
            )
        )
        worker.signals.failed.connect(
            lambda message: (
                process_batch_button.setEnabled(True),
                process_button.setEnabled(True),
                run_button.setEnabled(True),
                status_label.setText("Batch processing failed"),
                QMessageBox.critical(window, "Batch processing failed", message),
            )
        )
        thread_pool.start(worker)

    def create_prompt() -> None:
        workspace = state["workspace"]
        root = state["root"] or (workspace.path.parent if workspace else None)
        if workspace is None or root is None:
            QMessageBox.warning(window, "No test selected", "Choose a test first.")
            return
        try:
            prompt_path = generate_workspace_prompt(Config.defaults(root=root), workspace.path)
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.critical(window, "Cannot create prompt", str(exc))
            return
        status_label.setText(f"Prompt created: {prompt_path.name}")
        QMessageBox.information(window, "Prompt created", str(prompt_path))
        def on_batch_fail(err):
            batch_proc_btn.setEnabled(True)
            status_label.setText("Batch processing failed")
            QMessageBox.critical(window, "Batch Processing Failed", err)

    def preview_selected() -> None:
        workspace = state["workspace"]
        source = pdf_source.currentData() or (discover_sources(workspace).pdf if workspace else None)
        if source is None:
            QMessageBox.warning(window, "No PDF selected", "This test has no PDF source selected.")
            return
        preview.setText("Rendering preview...")
        status_label.setText(f"Rendering preview for {source.name}...")
        worker = Worker(lambda: render_pdf_page(source))
        worker.signals.finished.connect(
            lambda image: (
                preview.setPixmap(
                    QPixmap.fromImage(QImage.fromData(image)).scaled(
                        preview.width() - 10,
                        preview.height() - 10,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                ),
                status_label.setText(f"Preview ready for {source.name}"),
            )
        )
        worker.signals.failed.connect(
            lambda message: (
                preview.setText(message),
                status_label.setText("Preview failed"),
            )
        )
        worker.signals.finished.connect(on_batch_done)
        worker.signals.failed.connect(on_batch_fail)
        thread_pool.start(worker)

    def launch_generation_provider() -> None:
        workspace = state["workspace"]
        root = state["root"] or (workspace.path.parent if workspace else None)
        if workspace is None or root is None:
            QMessageBox.warning(window, "No test selected", "Choose a test first.")
    def launch_ai() -> None:
        ws = state["workspace"]
        root = state["root"] or (ws.path.parent if ws else None)
        if not ws or not root:
            QMessageBox.warning(window, "No exam selected", "Select an exam first.")
            return
        selected_provider, command = provider.currentData()

        prov, cmd = ai_provider_combo.currentData()
        try:
            if selected_provider.kind == "web":
                prompt_path = generate_workspace_prompt(
                    Config.defaults(root=root), workspace.path, "web"
                )
                open_web_provider(selected_provider)
            if prov.kind == "web":
                prompt_path = generate_workspace_prompt(Config.defaults(root=root), ws.path, "web")
                open_web_provider(prov)
            else:
                prompt_path = generate_workspace_prompt(
                    Config.defaults(root=root), workspace.path, "local"
                )
                send_to_provider(selected_provider, command, prompt_path)
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.critical(window, "Cannot launch provider", str(exc))
                prompt_path = generate_workspace_prompt(Config.defaults(root=root), ws.path, "local")
                send_to_provider(prov, cmd, prompt_path)
            status_label.setText(f"AI Prompt generated: {prompt_path.name}")
            QMessageBox.information(window, "Prompt Ready", f"Created prompt at:\n{prompt_path}")
        except Exception as exc:
            QMessageBox.critical(window, "Could not launch AI provider", str(exc))

    def save_test() -> None:
        ws = state["workspace"]
        if not ws:
            QMessageBox.warning(window, "No test selected", "Select a test first.")
            return
        status_label.setText(f"Provider launched for {workspace.name}")
        QMessageBox.information(window, "Prompt ready", str(prompt_path))
        save_active_question()
        ws.questions_path.parent.mkdir(parents=True, exist_ok=True)
        ws.questions_path.write_text(
            json.dumps(state["questions"], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        refresh_question_list_ui()
        update_tab3_summary()
        status_label.setText(f"Saved {len(state['questions'])} question(s) to {ws.questions_path.name}")
        QMessageBox.information(window, "Saved", f"Successfully saved {len(state['questions'])} question(s) to:\n{ws.questions_path}")

    def on_add_question() -> None:
        save_question()
    def add_question() -> None:
        save_active_question()
        new_q = {
            "question": "שאלה חדשה",
            "options": ["אפשרות 1", "אפשרות 2", "אפשרות 3", "אפשרות 4"],
            "correctIndex": 0,
        }
        state["questions"].append(new_q)
        refresh_question_list_labels()
        question_list.setCurrentRow(len(state["questions"]) - 1)
        refresh_question_list_ui()
        q_list.setCurrentRow(len(state["questions"]) - 1)

    def on_remove_question() -> None:
    def delete_question() -> None:
        idx = state["index"]
        if 0 <= idx < len(state["questions"]):
            state["questions"].pop(idx)
            state["index"] = -1
            refresh_question_list_labels()
            refresh_question_list_ui()
            if state["questions"]:
                new_idx = min(idx, len(state["questions"]) - 1)
                question_list.setCurrentRow(new_idx)
                q_list.setCurrentRow(min(idx, len(state["questions"]) - 1))
            else:
                update_editor_fields(None)

    choose_root.clicked.connect(refresh)
    refresh_root.clicked.connect(populate_tests_list)
    tests.currentItemChanged.connect(
        lambda current, _previous: load_workspace(current.data(Qt.ItemDataRole.UserRole))
        if current else None
    def prepare_and_play_quiz(custom_export_path: Path | None = None) -> None:
        selected = get_selected_workspaces_for_play()
        if not selected:
            QMessageBox.warning(window, "No exams selected", "Select or check at least one exam to run.")
            return

        try:
            save_active_question()
            run = assemble_run(selected, mix=mix_checkbox.isChecked())
            root = state["root"] or (selected[0].path.parent if selected else None)
            if root is None:
                raise RunError("Choose a projects folder first.")

            output = root / "runs" / f"{run.name}.json"
            write_run_questions(run, output)

            html_output = custom_export_path or output.with_suffix(".html")
            build_run_standalone_quiz(run, html_output)

            status_label.setText(f"Quiz built: {html_output.name}")
            if not custom_export_path:
                webbrowser.open(html_output.as_uri())
                QMessageBox.information(
                    window,
                    "Quiz Ready & Launched!",
                    f"✓ Generated standalone quiz with {len(run.questions)} question(s) from {len(run.sources)} exam(s).\nOpening in your default browser now:\n{html_output}",
                )
            else:
                QMessageBox.information(
                    window,
                    "Export Successful",
                    f"✓ Saved self-contained quiz HTML to:\n{html_output}",
                )
        except Exception as exc:
            QMessageBox.critical(window, "Could not launch quiz", str(exc))

    def export_quiz_as() -> None:
        selected = get_selected_workspaces_for_play()
        if not selected:
            QMessageBox.warning(window, "No exams selected", "Select at least one exam first.")
            return
        default_name = "mixed_quiz.html" if mix_checkbox.isChecked() else f"{selected[0].name}.html"
        save_path, _ = QFileDialog.getSaveFileName(window, "Export Standalone Quiz HTML", default_name, "HTML Files (*.html)")
        if save_path:
            prepare_and_play_quiz(Path(save_path))

    def open_runs_folder() -> None:
        root = state["root"]
        if not root:
            QMessageBox.warning(window, "No folder", "Choose a projects folder first.")
            return
        runs_dir = root / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        webbrowser.open(runs_dir.as_uri())

    # ── Signal Connections ─────────────────────────────────────────────────
    choose_root_btn.clicked.connect(choose_folder)
    refresh_root_btn.clicked.connect(populate_tests)
    exam_search.textChanged.connect(filter_exams)

    tab1_exam_list.currentItemChanged.connect(
        lambda curr, _prev: load_workspace(curr.data(Qt.ItemDataRole.UserRole)) if curr else None
    )
    question_list.currentRowChanged.connect(
        lambda index: show_question(index) if index >= 0 else None
    pdf_source_combo.currentIndexChanged.connect(
        lambda _i: preview_first_page()
    )
    add_question.clicked.connect(on_add_question)
    remove_question.clicked.connect(on_remove_question)
    save_project.clicked.connect(save_workspace)
    preview_button.clicked.connect(preview_selected)
    process_button.clicked.connect(process_selected)
    process_batch_button.clicked.connect(process_batch)
    prompt_button.clicked.connect(create_prompt)
    launch_provider.clicked.connect(launch_generation_provider)
    run_button.clicked.connect(prepare)

    extract_digital_btn.clicked.connect(process_selected_exam)
    batch_proc_btn.clicked.connect(process_batch_checked)
    launch_ai_btn.clicked.connect(launch_ai)
    preview_btn.clicked.connect(lambda: preview_first_page())
    proceed_to_step2_btn.clicked.connect(lambda: tabs.setCurrentIndex(1))

    q_list.currentRowChanged.connect(
        lambda idx: show_question(idx) if idx >= 0 else None
    )
    add_q_btn.clicked.connect(add_question)
    del_q_btn.clicked.connect(delete_question)
    save_test_btn.clicked.connect(save_test)
    proceed_to_step3_btn.clicked.connect(lambda: (save_active_question(), tabs.setCurrentIndex(2)))

    select_all_btn.clicked.connect(
        lambda: [tab3_exam_list.item(i).setCheckState(Qt.CheckState.Checked) for i in range(tab3_exam_list.count())] + [update_tab3_summary()]
    )
    clear_all_btn.clicked.connect(
        lambda: [tab3_exam_list.item(i).setCheckState(Qt.CheckState.Unchecked) for i in range(tab3_exam_list.count())] + [update_tab3_summary()]
    )
    tab3_exam_list.itemChanged.connect(lambda _item: update_tab3_summary())
    mix_checkbox.toggled.connect(lambda _v: update_tab3_summary())

    play_browser_btn.clicked.connect(lambda: prepare_and_play_quiz())
    export_html_btn.clicked.connect(export_quiz_as)
    open_runs_dir_btn.clicked.connect(open_runs_folder)

    window.show()
    return application.exec()

