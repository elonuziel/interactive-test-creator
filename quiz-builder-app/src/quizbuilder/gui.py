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
    window.resize(1120, 780)
    window.setStyleSheet("background-color: #f8fafc;")

    root_layout = QVBoxLayout(window)
    root_layout.setContentsMargins(14, 12, 14, 12)
    root_layout.setSpacing(10)

    # ── Top Bar: Folder Selection & Breadcrumb ─────────────────────────────
    top_bar = QFrame()
    top_bar.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 6px 12px;")
    top_layout = QHBoxLayout(top_bar)
    top_layout.setContentsMargins(4, 4, 4, 4)

    root_label = QLabel("📁 Projects Folder: (no folder chosen)")
    root_label.setStyleSheet("font-weight: 600; color: #1e293b;")
    choose_root_btn = QPushButton("📁 Choose Folder...")
    choose_root_btn.setStyleSheet("background-color: #2563eb; color: #ffffff; font-weight: 600; border-color: #1d4ed8;")
    refresh_root_btn = QPushButton("🔄 Refresh")

    top_layout.addWidget(root_label, 1)
    top_layout.addWidget(choose_root_btn)
    top_layout.addWidget(refresh_root_btn)
    root_layout.addWidget(top_bar)

    # ── Main 3-Tab Stepper ─────────────────────────────────────────────────
    tabs = QTabWidget()
    root_layout.addWidget(tabs, 1)

    state = {
        "root": None,
        "workspace": None,
        "questions": [],
        "index": -1,
        "is_digital": None,
        "batch_candidates": [],
        "loading": False,   # guard: suppresses combo signals while repopulating
    }
    config = Config.load()

    def config_for_root(root: Path) -> Config:
        return Config(
            workspace_root=root,
            scripts_root=config.scripts_root,
            default_form=config.default_form,
            default_discard_pages=config.default_discard_pages,
            auto_build=config.auto_build,
            provider=config.provider,
        )

    # =========================================================================
    # TAB 1: 📄 1. Select & Extract Exam
    # =========================================================================
    tab1 = QWidget()
    tab1_layout = QHBoxLayout(tab1)
    tab1_layout.setContentsMargins(10, 10, 10, 10)
    tab1_layout.setSpacing(12)

    # Left: Exam list & search
    tab1_left = QGroupBox("Exams in Folder")
    tab1_left_layout = QVBoxLayout(tab1_left)
    tab1_left_layout.setSpacing(8)

    exam_search = QLineEdit()
    exam_search.setPlaceholderText("🔍 Filter exams...")
    tab1_left_layout.addWidget(exam_search)

    tab1_exam_list = QListWidget()
    tab1_left_layout.addWidget(tab1_exam_list, 1)

    batch_proc_btn = QPushButton("⚡ Process Checked Exams")
    batch_proc_btn.setStyleSheet("background-color: #f1f5f9; color: #334155; font-weight: 600;")
    tab1_left_layout.addWidget(batch_proc_btn)
    tab1_layout.addWidget(tab1_left, 4)

    # Right: Source PDF, Smart Detection, Preview & Actions
    tab1_right = QGroupBox("Document Inspection & Extraction")
    tab1_right_layout = QVBoxLayout(tab1_right)
    tab1_right_layout.setSpacing(10)

    # Header with active exam name
    current_exam_title = QLabel("Select an exam from the list")
    current_exam_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #0f172a;")
    tab1_right_layout.addWidget(current_exam_title)

    # PDF source picker
    pdf_source_row = QHBoxLayout()
    pdf_source_row.addWidget(QLabel("Source PDF:"))
    pdf_source_combo = QComboBox()
    pdf_source_combo.addItem("No PDF selected", None)
    pdf_source_row.addWidget(pdf_source_combo, 1)
    tab1_right_layout.addLayout(pdf_source_row)

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

    # Extraction Actions
    action_box = QFrame()
    action_box.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px;")
    action_box_layout = QVBoxLayout(action_box)
    action_box_layout.setSpacing(8)

    extract_digital_btn = QPushButton("⚡ Extract Questions Automatically (Digital)")
    extract_digital_btn.setStyleSheet("background-color: #16a34a; color: #ffffff; font-weight: bold; padding: 9px; font-size: 13px;")
    action_box_layout.addWidget(extract_digital_btn)

    ai_row = QHBoxLayout()
    ai_provider_combo = QComboBox()
    for web_p in WEB_PROVIDERS:
        ai_provider_combo.addItem(f"Web: {web_p.label}", (web_p, None))
    for local_p, cmd in detect_providers(config.provider.freebuff_commands):
        ai_provider_combo.addItem(f"Local: {local_p.label} ({cmd})", (local_p, cmd))

    launch_ai_btn = QPushButton("🤖 Generate AI Prompt & Launch")
    launch_ai_btn.setStyleSheet("background-color: #6366f1; color: #ffffff; font-weight: 600; padding: 8px;")
    ai_row.addWidget(ai_provider_combo, 2)
    ai_row.addWidget(launch_ai_btn, 3)
    action_box_layout.addLayout(ai_row)

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
    status_label.setStyleSheet("color: #64748b; font-size: 12px;")
    status_layout.addWidget(status_label, 1)
    root_layout.addWidget(status_bar)

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
            q_text_edit.clear()
            for opt_field in option_edits:
                opt_field.clear()
            if option_radios:
                option_radios[0].setChecked(True)
            return

        q_text_edit.setPlainText(question.get("question", ""))
        options = question.get("options", [])
        for i, opt_field in enumerate(option_edits):
            opt_field.setText(options[i] if i < len(options) else "")
        ans_idx = question.get("correctIndex", 0)
        if isinstance(ans_idx, int) and 0 <= ans_idx < len(option_radios):
            option_radios[ans_idx].setChecked(True)
        elif option_radios:
            option_radios[0].setChecked(True)

    def show_question(index: int) -> None:
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
        from .documents import DocumentError

        def run_classify():
            # Returns True (digital), False (scanned), or the exception string to
            # distinguish "fitz missing" from a genuine scan result.
            try:
                return classify_pdf(pdf_path)
            except DocumentError as exc:
                return exc  # propagate as value so the GUI thread handles it
            except Exception as exc:
                return exc

        detection_title.setText("🔍 Analyzing PDF type...")
        detection_desc.setText("Inspecting text streams and structure...")
        detection_card.setStyleSheet("background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px;")
        extract_digital_btn.setEnabled(False)  # reset while we re-analyse

        worker = Worker(run_classify)

        def on_classify_done(result):
            if isinstance(result, Exception):
                # Bug 4: fitz/PyMuPDF not installed or PDF unreadable
                state["is_digital"] = None
                detection_title.setText("⚠️ PDF Analysis Unavailable")
                detection_desc.setText(f"{result}  — Install PyMuPDF to enable auto-detection.")
                detection_card.setStyleSheet("background: #fef9c3; border: 1px solid #fde047; border-radius: 6px; padding: 10px;")
                extract_digital_btn.setEnabled(True)  # allow manual attempt
                return

            state["is_digital"] = result
            if result is True:
                detection_title.setText("✨ Digital PDF Detected (Extractable Text)")
                detection_desc.setText("This exam has clean text. Click 'Extract Questions Automatically' for instant conversion.")
                detection_card.setStyleSheet("background: #f0fdf4; border: 1px solid #86efac; border-radius: 6px; padding: 10px;")
                extract_digital_btn.setEnabled(True)   # Bug 5 fix: enable only for digital
            else:
                # Bug 5 fix: explicitly disable for scanned PDFs
                detection_title.setText("📷 Scanned / Vector PDF Detected (Images Only)")
                detection_desc.setText("This exam requires AI vision/rendering. Use 'Generate AI Prompt & Launch' below.")
                detection_card.setStyleSheet("background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; padding: 10px;")
                extract_digital_btn.setEnabled(False)

        worker.signals.finished.connect(on_classify_done)
        thread_pool.start(worker)

    def load_workspace(workspace) -> None:
        if workspace is None:
            state["workspace"] = None
            state["questions"] = []
            state["index"] = -1
            current_exam_title.setText("Select an exam from the list")
            update_editor_fields(None)
            refresh_question_list_ui()
            return

        state["workspace"] = workspace
        state["index"] = -1
        current_exam_title.setText(f"Exam: {workspace.name}")

        # Bug 2 fix: block currentIndexChanged while repopulating combos
        state["loading"] = True

        # Update PDF dropdown
        pdf_source_combo.clear()
        pdf_paths = [workspace.source_pdf] if workspace.source_pdf else (
            sorted(
                (p for p in workspace.path.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"),
                key=lambda p: p.name.lower(),
            )
            if workspace.path.is_dir()
            else []
        )
        for p in pdf_paths:
            if p:
                pdf_source_combo.addItem(p.name, p)
        if pdf_source_combo.count() == 0:
            pdf_source_combo.addItem("No PDF selected", None)

        # Update Answer Keys dropdown
        answer_key_combo.clear()
        answer_key_combo.addItem("No answer key", None)
        for key_path in discover_sources(workspace).answer_keys:
            answer_key_combo.addItem(key_path.name, key_path)

        state["loading"] = False  # unlock before triggering classification/preview

        # Smart classification
        chosen_pdf = pdf_source_combo.currentData()
        if chosen_pdf and chosen_pdf.is_file():
            check_pdf_classification(chosen_pdf)
            # Auto-preview
            preview_first_page(chosen_pdf)
        else:
            detection_title.setText("📂 No PDF Found")
            detection_desc.setText("Add a PDF to the exam folder, then Refresh.")
            detection_card.setStyleSheet("background: #fef9c3; border: 1px solid #fde047; border-radius: 6px; padding: 10px;")
            extract_digital_btn.setEnabled(False)

        # Load questions for Step 2
        try:
            questions = load_questions(workspace.questions_path)
            state["questions"] = questions
            refresh_question_list_ui()
            if questions:
                q_list.setCurrentRow(0)
            else:
                update_editor_fields(None)
            status_label.setText(f"Loaded {workspace.name} ({len(questions)} questions)")
        except (ValidationError, OSError):
            state["questions"] = []
            refresh_question_list_ui()
            update_editor_fields(None)
            status_label.setText(f"Selected {workspace.name} (not extracted yet)")

        update_tab3_summary()

    def preview_first_page(pdf_path: Path | None = None) -> None:
        target = pdf_path or pdf_source_combo.currentData()
        if not target or not Path(target).is_file():
            tab1_preview.setText("No PDF selected to preview")
            return

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
        candidates = discover_batch(state["root"])
        state["batch_candidates"] = candidates

        tab1_exam_list.clear()
        tab3_exam_list.clear()

        for c in candidates:
            label = c.workspace.name
            if c.issues:
                label += f"  ({'; '.join(c.issues)})"

            # Tab 1 List
            item1 = QListWidgetItem(label, tab1_exam_list)
            item1.setData(Qt.ItemDataRole.UserRole, c.workspace)
            item1.setCheckState(Qt.CheckState.Unchecked)

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
        state["root"] = Path(chosen)
        populate_tests()

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

        extract_digital_btn.setEnabled(False)
        launch_ai_btn.setEnabled(False)
        status_label.setText(f"Processing {ws.name}...")

        sel_key = answer_key_combo.currentData()
        sel_pdf = pdf_source_combo.currentData()
        f_num = form_num_edit.text().strip() or "0"

        worker = Worker(
            lambda: process_workspace(
                config_for_root(root),
                ws.path,
                sel_key,
                f_num,
                sel_pdf,
            )
        )

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

    def process_batch_checked() -> None:
        root = state["root"]
        selected = [
            tab1_exam_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(tab1_exam_list.count())
            if tab1_exam_list.item(i).checkState() == Qt.CheckState.Checked
        ]
        if not root or not selected:
            QMessageBox.warning(window, "No exams checked", "Check the boxes next to the exams you want to batch-process.")
            return

        batch_proc_btn.setEnabled(False)
        status_label.setText(f"Batch processing {len(selected)} exam(s)...")

        def run_all():
            results = process_workspaces(config_for_root(root), selected)
            return (
                [r.workspace.name for r in results if r.success],
                [f"{r.workspace.name}: {r.error}" for r in results if not r.success],
            )

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

        def on_batch_fail(err):
            batch_proc_btn.setEnabled(True)
            status_label.setText("Batch processing failed")
            QMessageBox.critical(window, "Batch Processing Failed", err)

        worker.signals.finished.connect(on_batch_done)
        worker.signals.failed.connect(on_batch_fail)
        thread_pool.start(worker)

    def launch_ai() -> None:
        ws = state["workspace"]
        root = state["root"] or (ws.path.parent if ws else None)
        if not ws or not root:
            QMessageBox.warning(window, "No exam selected", "Select an exam first.")
            return

        prov, cmd = ai_provider_combo.currentData()
        try:
            if prov.kind == "web":
                prompt_path = generate_workspace_prompt(config_for_root(root), ws.path, "web")
                if config.provider.open_browser and not open_web_provider(prov):
                    raise RuntimeError(f"Could not open {prov.label} in the browser.")
            else:
                prompt_path = generate_workspace_prompt(config_for_root(root), ws.path, "local")
                send_to_provider(prov, cmd, prompt_path)
            status_label.setText(f"AI Prompt generated: {prompt_path.name}")
            browser_note = "" if config.provider.open_browser else "\nBrowser opening is disabled in configuration."
            QMessageBox.information(window, "Prompt Ready", f"Created prompt at:\n{prompt_path}{browser_note}")
        except Exception as exc:
            QMessageBox.critical(window, "Could not launch AI provider", str(exc))

    def save_test() -> None:
        ws = state["workspace"]
        if not ws:
            QMessageBox.warning(window, "No test selected", "Select a test first.")
            return
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

    def add_question() -> None:
        save_active_question()
        new_q = {
            "question": "שאלה חדשה",
            "options": ["אפשרות 1", "אפשרות 2", "אפשרות 3", "אפשרות 4"],
            "correctIndex": 0,
        }
        state["questions"].append(new_q)
        refresh_question_list_ui()
        q_list.setCurrentRow(len(state["questions"]) - 1)

    def delete_question() -> None:
        idx = state["index"]
        if 0 <= idx < len(state["questions"]):
            state["questions"].pop(idx)
            state["index"] = -1
            refresh_question_list_ui()
            if state["questions"]:
                q_list.setCurrentRow(min(idx, len(state["questions"]) - 1))
            else:
                update_editor_fields(None)

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
    # Bug 2 fix: only re-preview when not currently repopulating the combo
    pdf_source_combo.currentIndexChanged.connect(
        lambda _i: preview_first_page() if not state["loading"] else None
    )

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

    # Bug 1 fix: named handlers so update_tab3_summary() is actually called
    def select_all_exams() -> None:
        for i in range(tab3_exam_list.count()):
            tab3_exam_list.item(i).setCheckState(Qt.CheckState.Checked)
        update_tab3_summary()

    def clear_all_exams() -> None:
        for i in range(tab3_exam_list.count()):
            tab3_exam_list.item(i).setCheckState(Qt.CheckState.Unchecked)
        update_tab3_summary()

    select_all_btn.clicked.connect(select_all_exams)
    clear_all_btn.clicked.connect(clear_all_exams)
    tab3_exam_list.itemChanged.connect(lambda _item: update_tab3_summary())
    mix_checkbox.toggled.connect(lambda _v: update_tab3_summary())


    play_browser_btn.clicked.connect(lambda: prepare_and_play_quiz())
    export_html_btn.clicked.connect(export_quiz_as)
    open_runs_dir_btn.clicked.connect(open_runs_folder)

    state["root"] = config.workspace_root
    populate_tests()
    window.show()
    return application.exec()

