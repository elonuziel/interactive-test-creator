"""Extract tab component for QuizBuilder GUI: exam discovery, PDF loading, cleaning & AI prompt creation."""

from __future__ import annotations

from pathlib import Path
import threading
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ...commands import generate_workspace_prompt, process_workspace, process_workspaces
from ...documents import (
    DocumentError,
    classify_pdf,
    clean_pdf,
    convert_docx_with_soffice,
    describe_page_cleaning,
)
from ...preview import render_pdf_page
from ...providers import WEB_PROVIDERS, detect_providers, open_web_provider
from ...prompts import send_to_provider
from ..dialogs import (
    CliAgentGuideDialog,
    SuperBatchDialog,
    SuperBatchProgressDialog,
    SuperBatchSummaryDialog,
)
from ..web_batch_dialog import WebAIBatchDialog
from ..workers import Worker

if TYPE_CHECKING:
    from ..app import MainWindow


class ExtractTabWidget(QWidget):
    """Tab 1: Choose an exam folder, select files, clean PDF, and extract questions with AI."""

    def __init__(self, main_window: MainWindow, parent: QWidget | None = None):
        super().__init__(parent)
        self.main_window = main_window
        self.config = main_window.config
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        tab_layout = QVBoxLayout(self)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        self.extract_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.extract_splitter.setChildrenCollapsible(False)

        # Left panel: Choose an exam
        self.exam_group = QGroupBox("1. Choose an exam")
        left = QVBoxLayout(self.exam_group)
        self.exam_search = QLineEdit()
        self.exam_search.setPlaceholderText("Search exams...")
        self.exam_list = QListWidget()
        self.exam_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        exam_sel_row = QHBoxLayout()
        self.exam_select_all_btn = QPushButton("Select all")
        self.exam_select_all_btn.setToolTip("Check all visible exams in the list")
        self.exam_deselect_all_btn = QPushButton("Deselect all")
        self.exam_deselect_all_btn.setToolTip("Uncheck all exams in the list")
        exam_sel_row.addWidget(self.exam_select_all_btn)
        exam_sel_row.addWidget(self.exam_deselect_all_btn)

        self.batch_button = QPushButton("Process selected exams")

        super_batch_row = QHBoxLayout()
        self.super_batch_button = QPushButton("Super Batch (local AI)")
        self.super_batch_button.setToolTip("Review and generate questions.md for multiple exams automatically using a detected local CLI AI.")
        self.super_batch_info_btn = QPushButton("ℹ️")
        self.super_batch_info_btn.setMaximumWidth(32)
        self.super_batch_info_btn.setToolTip("Why use a local CLI AI agent? Click to learn the advantages and see how to install one.")
        super_batch_row.addWidget(self.super_batch_button, 1)
        super_batch_row.addWidget(self.super_batch_info_btn)

        left.addWidget(self.exam_search)
        left.addWidget(self.exam_list, 1)
        left.addLayout(exam_sel_row)
        left.addWidget(self.batch_button)

        self.web_batch_button = QPushButton("🌐 Web AI Batch")
        self.web_batch_button.setToolTip("Step-by-step batch assistant for ChatGPT, Claude, Gemini Web, and Google AI Studio (1 PDF at a time with auto prompt copying and answer merging).")
        left.addWidget(self.web_batch_button)
        left.addLayout(super_batch_row)
        self.extract_splitter.addWidget(self.exam_group)

        # Right panel: Prepare questions
        self.extract_group = QGroupBox("2. Prepare questions (saved as questions.md)")
        right = QVBoxLayout(self.extract_group)
        self.current_exam_title = QLabel("Choose an exam from the list")
        self.pdf_combo = QComboBox()
        self.pdf_combo.addItem("No exam file selected", None)
        self.browse_pdf_button = QPushButton("Choose file...")
        self.browse_pdf_button.setToolTip("Select a custom PDF or Word (DOCX) exam file")
        pdf_row = QHBoxLayout()
        pdf_row.addWidget(QLabel("Exam file:"))
        pdf_row.addWidget(self.pdf_combo, 1)
        pdf_row.addWidget(self.browse_pdf_button)
        self.detection_title = QLabel("PDF type: waiting for an exam")
        self.detection_description = QLabel("Choose an exam to check whether its text can be extracted automatically.")
        self.detection_description.setWordWrap(True)
        self.extract_button = QPushButton("Extract questions from PDF")
        self.extract_button.setObjectName("primary")
        self.ai_hint = QLabel("Digital PDFs can be extracted automatically. Scanned PDFs need an AI prompt. Results are saved as questions.md.")
        self.ai_hint.setWordWrap(True)
        self.ai_provider_combo = QComboBox()
        local_items = detect_providers(self.config.provider.freebuff_commands)
        for provider, command in local_items:
            self.ai_provider_combo.addItem(f"Local: {provider.label} ({command})", (provider, command))
        for provider in WEB_PROVIDERS:
            self.ai_provider_combo.addItem(f"Web: {provider.label}", (provider, None))
        self.launch_ai_button = QPushButton("Create AI prompt")
        self._on_ai_provider_changed()
        self.launch_ai_button.setToolTip("Create a prompt for extracting questions into questions.md.")

        self.ai_info_btn = QPushButton("ℹ️")
        self.ai_info_btn.setMaximumWidth(32)
        self.ai_info_btn.setToolTip("What is a CLI AI agent? Click to learn the advantages and how to install one.")

        self.answer_combo = QComboBox()
        self.answer_combo.addItem("No answer key", None)
        self.browse_answer_button = QPushButton("Choose file...")
        self.browse_answer_button.setToolTip("Select a custom CSV or Excel (XLS/XLSX) answer key")
        self.form_edit = QLineEdit(self.config.default_form)
        self.form_edit.setMaximumWidth(70)
        self.preview = QLabel("No exam preview available")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(200, 150)
        self.preview_button = QPushButton("Preview first page")
        self.next_review_button = QPushButton("Next: review questions")
        right.addWidget(self.current_exam_title)
        right.addLayout(pdf_row)
        right.addWidget(self.detection_title)
        right.addWidget(self.detection_description)
        right.addWidget(self.extract_button)
        right.addWidget(self.ai_hint)
        ai_row = QHBoxLayout()
        ai_row.addWidget(self.ai_provider_combo, 2)
        ai_row.addWidget(self.launch_ai_button, 3)
        ai_row.addWidget(self.ai_info_btn)
        right.addLayout(ai_row)

        # Clean PDF section for scanned exams
        self.clean_group = QGroupBox("Clean PDF (Discard blank & cover pages)")
        clean_layout = QVBoxLayout(self.clean_group)
        self.clean_hint = QLabel("Discard blank/cover pages for clean AI prompts & accurate OCR.")
        self.clean_hint.setWordWrap(True)
        clean_layout.addWidget(self.clean_hint)

        preset_row = QHBoxLayout()
        self.preset_std_button = QPushButton("🧹 Standard clean (std)")
        self.preset_std_button.setToolTip("Discards cover pages 1-4 and even pages (6, 8, 10...)")
        self.preset_even_button = QPushButton("📄 Even pages")
        self.preset_odd_button = QPushButton("📄 Odd pages")
        self.preset_clear_button = QPushButton("☐ Reset")
        preset_row.addWidget(self.preset_std_button)
        preset_row.addWidget(self.preset_even_button)
        preset_row.addWidget(self.preset_odd_button)
        preset_row.addWidget(self.preset_clear_button)
        clean_layout.addLayout(preset_row)

        range_row = QHBoxLayout()
        range_row.addWidget(QLabel("Discard pages:"))
        self.discard_range_edit = QLineEdit("std")
        self.discard_range_edit.setPlaceholderText("e.g. std, 1-4, 6, 8")
        range_row.addWidget(self.discard_range_edit, 1)
        self.clean_pdf_button = QPushButton("🧹 Create clean PDF")
        self.clean_pdf_button.setToolTip("Creates <name>_clean.pdf without discarded pages")
        range_row.addWidget(self.clean_pdf_button)
        clean_layout.addLayout(range_row)

        self.clean_summary_label = QLabel("Select an exam to calculate kept pages.")
        self.clean_summary_label.setStyleSheet("color: var(--muted-color); font-size: 11px;")
        clean_layout.addWidget(self.clean_summary_label)
        right.addWidget(self.clean_group)
        answer_row = QHBoxLayout()
        answer_row.addWidget(QLabel("Answer key (optional):"))
        answer_row.addWidget(self.answer_combo, 1)
        answer_row.addWidget(self.browse_answer_button)
        answer_row.addWidget(QLabel("Form number:"))
        answer_row.addWidget(self.form_edit)
        right.addLayout(answer_row)
        right.addWidget(self.preview, 1)
        actions = QHBoxLayout()
        actions.addWidget(self.preview_button)
        actions.addStretch()
        actions.addWidget(self.next_review_button)
        right.addLayout(actions)

        extract_scroll = QScrollArea()
        extract_scroll.setWidgetResizable(True)
        extract_scroll.setFrameShape(QFrame.Shape.NoFrame)
        extract_scroll.setWidget(self.extract_group)
        self.extract_splitter.addWidget(extract_scroll)

        self.extract_splitter.setStretchFactor(0, 4)
        self.extract_splitter.setStretchFactor(1, 6)
        tab_layout.addWidget(self.extract_splitter)

    def _connect_signals(self) -> None:
        self.exam_search.textChanged.connect(self.filter_exams)
        self.exam_list.currentItemChanged.connect(self.main_window.select_exam)
        self.exam_list.customContextMenuRequested.connect(self._show_exam_list_context_menu)
        self.exam_select_all_btn.clicked.connect(self.select_all_extract_exams)
        self.exam_deselect_all_btn.clicked.connect(self.deselect_all_extract_exams)
        self.pdf_combo.currentIndexChanged.connect(self._on_pdf_selection_changed)
        self.browse_pdf_button.clicked.connect(self.choose_custom_exam_file)
        self.browse_answer_button.clicked.connect(self.choose_custom_answer_key)
        self.preset_std_button.clicked.connect(lambda: self.set_discard_preset("std"))
        self.preset_even_button.clicked.connect(lambda: self.set_discard_preset("even"))
        self.preset_odd_button.clicked.connect(lambda: self.set_discard_preset("odd"))
        self.preset_clear_button.clicked.connect(lambda: self.set_discard_preset(""))
        self.discard_range_edit.textChanged.connect(lambda: self.update_clean_summary())
        self.clean_pdf_button.clicked.connect(self.run_clean_pdf)
        self.extract_button.clicked.connect(self.process_selected_exam)
        self.batch_button.clicked.connect(self.process_batch_checked)
        self.web_batch_button.clicked.connect(self.open_web_batch_wizard)
        self.super_batch_button.clicked.connect(self.open_super_batch)
        self.super_batch_info_btn.clicked.connect(self.show_cli_agent_guide)
        self.ai_info_btn.clicked.connect(self.show_cli_agent_guide)
        self.ai_provider_combo.currentIndexChanged.connect(self._on_ai_provider_changed)
        self.launch_ai_button.clicked.connect(self.launch_ai)
        self.preview_button.clicked.connect(self.preview_first_page)
        self.next_review_button.clicked.connect(lambda: self.main_window.tabs.setCurrentIndex(1))

    def _show_exam_list_context_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        sel_all = menu.addAction("Select all visible")
        sel_all.triggered.connect(self.select_all_extract_exams)
        desel_all = menu.addAction("Deselect all")
        desel_all.triggered.connect(self.deselect_all_extract_exams)
        invert = menu.addAction("Invert selection")
        invert.triggered.connect(self.invert_extract_exams_selection)
        menu.exec(self.exam_list.mapToGlobal(pos))

    def select_all_extract_exams(self) -> None:
        """Check all visible exams in the main extract exam list."""
        for index in range(self.exam_list.count()):
            item = self.exam_list.item(index)
            if not item.isHidden():
                item.setCheckState(Qt.CheckState.Checked)

    def deselect_all_extract_exams(self) -> None:
        """Uncheck all exams in the main extract exam list."""
        for index in range(self.exam_list.count()):
            self.exam_list.item(index).setCheckState(Qt.CheckState.Unchecked)

    def invert_extract_exams_selection(self) -> None:
        """Invert checked state for all visible exams in the main exam list."""
        for index in range(self.exam_list.count()):
            item = self.exam_list.item(index)
            if not item.isHidden():
                new_state = (
                    Qt.CheckState.Unchecked
                    if item.checkState() == Qt.CheckState.Checked
                    else Qt.CheckState.Checked
                )
                item.setCheckState(new_state)

    def filter_exams(self, query: str) -> None:
        query = query.strip().casefold()
        for index in range(self.exam_list.count()):
            self.exam_list.item(index).setHidden(query not in self.exam_list.item(index).text().casefold())

    def choose_custom_exam_file(self) -> None:
        workspace = self.main_window.state["workspace"]
        if not workspace:
            QMessageBox.warning(self, "No exam selected", "Choose an exam folder before selecting a custom exam file.")
            return
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select Exam Document (PDF or Word DOCX)",
            str(workspace.path),
            "Exam Files (*.pdf *.docx *.doc);;PDF Files (*.pdf);;Word Documents (*.docx *.doc);;All Files (*)",
        )
        if filename:
            file_path = Path(filename)
            if file_path.suffix.lower() in {".docx", ".doc"}:
                self.main_window._set_status(f"Converting Word document {file_path.name} to PDF...", "busy")
                def _do_convert():
                    return convert_docx_with_soffice(file_path)
                def _convert_done(converted_pdf):
                    self.main_window._set_status("Word document converted to PDF successfully!", "success")
                    self._add_and_select_pdf(converted_pdf)
                def _convert_fail(err):
                    self.main_window._set_status(f"DOCX conversion failed: {err}", "error")
                    QMessageBox.warning(self, "DOCX Conversion Failed", f"Could not convert {file_path.name} to PDF automatically:\n\n{err}\n\nPlease convert to PDF manually or ensure LibreOffice (soffice) is installed.")
                worker = Worker(_do_convert)
                worker.signals.finished.connect(_convert_done)
                worker.signals.failed.connect(_convert_fail)
                self.main_window.start_worker(worker)
            else:
                self._add_and_select_pdf(file_path)

    def _add_and_select_pdf(self, file_path: Path) -> None:
        rel_label = f"Custom: {file_path.name}"
        for i in range(self.pdf_combo.count()):
            if self.pdf_combo.itemData(i) == file_path:
                self.pdf_combo.setCurrentIndex(i)
                return
        self.pdf_combo.addItem(rel_label, file_path)
        self.pdf_combo.setCurrentIndex(self.pdf_combo.count() - 1)

    def choose_custom_answer_key(self) -> None:
        workspace = self.main_window.state["workspace"]
        if not workspace:
            QMessageBox.warning(self, "No exam selected", "Choose an exam folder before selecting an answer key.")
            return
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select Answer Key File",
            str(workspace.path),
            "Answer Keys (*.csv *.xlsx *.xls *.json *.txt);;CSV Files (*.csv);;Excel Files (*.xlsx *.xls);;All Files (*)",
        )
        if filename:
            file_path = Path(filename)
            rel_label = f"Custom: {file_path.name}"
            for i in range(self.answer_combo.count()):
                if self.answer_combo.itemData(i) == file_path:
                    self.answer_combo.setCurrentIndex(i)
                    return
            self.answer_combo.addItem(rel_label, file_path)
            self.answer_combo.setCurrentIndex(self.answer_combo.count() - 1)

    def _on_pdf_selection_changed(self) -> None:
        workspace = self.main_window.state["workspace"]
        selected_pdf = self.pdf_combo.currentData()
        if not workspace or not selected_pdf or not selected_pdf.is_file():
            self.update_clean_summary()
            return
        self.main_window._set_status("Analyzing selected PDF...", "busy")
        def _classify():
            return classify_pdf(selected_pdf)
        def _classified(report):
            self.main_window._set_status("")
            self.detection_title.setText(f"PDF type: {'Digital text' if report.is_digital else 'Scanned / images'}")
            self.detection_description.setText(report.reason)
            self.extract_button.setEnabled(report.is_digital)
            self.update_clean_summary()
        def _classify_failed(_err):
            self.main_window._set_status("")
            self.detection_title.setText("PDF type: unknown")
            self.detection_description.setText("Could not inspect the selected PDF.")
            self.extract_button.setEnabled(False)
            self.update_clean_summary()
        worker = Worker(_classify)
        worker.signals.finished.connect(_classified)
        worker.signals.failed.connect(_classify_failed)
        self.main_window.start_worker(worker)

    def preview_first_page(self) -> None:
        target = self.pdf_combo.currentData()
        if not target or not Path(target).is_file():
            self.preview.setText("No valid exam file selected.")
            return
        self.preview.setText("Loading preview...")
        worker = Worker(lambda: render_pdf_page(Path(target)))
        worker.signals.finished.connect(self._apply_preview)
        worker.signals.failed.connect(lambda error: self.preview.setText(f"Preview error:\n{error}"))
        self.main_window.start_worker(worker)

    def _apply_preview(self, image_path: Path) -> None:
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            self.preview.setText("Preview could not be displayed.")
            return
        scaled = pixmap.scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.preview.setPixmap(scaled)

    def set_discard_preset(self, rule: str) -> None:
        self.discard_range_edit.setText(rule)
        self.update_clean_summary()

    def update_clean_summary(self) -> None:
        rule = self.discard_range_edit.text().strip()
        target = self.pdf_combo.currentData()
        if not target or not Path(target).is_file():
            self.clean_summary_label.setText("Select an exam to calculate kept pages.")
            return
        try:
            desc = describe_page_cleaning(Path(target), rule)
            self.clean_summary_label.setText(f"📊 {desc}")
        except Exception:
            self.clean_summary_label.setText("⚠️ Invalid page range or rule.")

    def run_clean_pdf(self) -> None:
        workspace = self.main_window.state["workspace"]
        target = self.pdf_combo.currentData()
        if not workspace or not target or not Path(target).is_file():
            QMessageBox.warning(self, "No PDF Selected", "Please select a valid PDF to clean.")
            return
        rule = self.discard_range_edit.text().strip()
        if not rule:
            QMessageBox.warning(self, "No Pages Discarded", "Enter a discard rule or page range (e.g. 'std', '1-4, 6, 8').")
            return
        self.main_window._set_status(f"Creating clean PDF for {workspace.name}...", "busy")
        self.clean_pdf_button.setEnabled(False)
        def _clean_worker():
            return clean_pdf(Path(target), rule=rule)
        def _clean_done(clean_path: Path):
            self.clean_pdf_button.setEnabled(True)
            self.main_window._set_status(f"Created clean PDF: {clean_path.name}", "success")
            QMessageBox.information(
                self,
                "Clean PDF Created",
                f"Successfully created clean PDF without discarded pages:\n\n{clean_path.name}\n\nThis clean PDF is now selected for question extraction.",
            )
            self.main_window.load_workspace(workspace)
            for i in range(self.pdf_combo.count()):
                if self.pdf_combo.itemData(i) == clean_path:
                    self.pdf_combo.setCurrentIndex(i)
                    break
        def _clean_failed(err):
            self.clean_pdf_button.setEnabled(True)
            self.main_window._set_status(f"PDF cleanup failed: {err}", "error")
            QMessageBox.critical(self, "Cleanup Error", f"Could not create clean PDF:\n\n{err}")
        worker = Worker(_clean_worker)
        worker.signals.finished.connect(_clean_done)
        worker.signals.failed.connect(_clean_failed)
        self.main_window.start_worker(worker)

    def _on_ai_provider_changed(self) -> None:
        data = self.ai_provider_combo.currentData()
        if data:
            provider, command = data
            if command:
                self.launch_ai_button.setText(f"🚀 Run {provider.label}")
                self.launch_ai_button.setToolTip(f"Run {provider.label} automatically via CLI command: {command}")
            else:
                self.launch_ai_button.setText(f"📋 Copy prompt for {provider.label}")
                self.launch_ai_button.setToolTip(f"Copy the complete prompt to clipboard and open {provider.label} in your browser.")

    def reload_ai_providers(self) -> None:
        current_data = self.ai_provider_combo.currentData()
        current_id = (current_data[0].id, current_data[1]) if current_data else None
        self.ai_provider_combo.clear()
        local_items = detect_providers(self.config.provider.freebuff_commands)
        for provider, command in local_items:
            self.ai_provider_combo.addItem(f"Local: {provider.label} ({command})", (provider, command))
        for provider in WEB_PROVIDERS:
            self.ai_provider_combo.addItem(f"Web: {provider.label}", (provider, None))
        if current_id:
            for idx in range(self.ai_provider_combo.count()):
                p, cmd = self.ai_provider_combo.itemData(idx)
                if (p.id, cmd) == current_id:
                    self.ai_provider_combo.setCurrentIndex(idx)
                    break
        self._on_ai_provider_changed()

    def show_cli_agent_guide(self) -> None:
        dialog = CliAgentGuideDialog(self, on_refresh=self.reload_ai_providers)
        dialog.exec()

    def process_selected_exam(self) -> None:
        workspace = self.main_window.state["workspace"]
        if not workspace:
            QMessageBox.warning(self, "No exam selected", "Select an exam before extracting questions.")
            return
        if not self.main_window.confirm_discard_changes():
            return
        self.main_window._set_status(f"Extracting questions from {workspace.name}...", "busy")
        self.extract_button.setEnabled(False)
        def run_extraction():
            return process_workspace(
                workspace,
                self.config,
                pdf_path=self.pdf_combo.currentData(),
                answers_path=self.answer_combo.currentData(),
                form_value=self.form_edit.text(),
            )
        def on_done(report):
            self.extract_button.setEnabled(True)
            self.main_window._set_status(report.message, "success")
            self.main_window.populate_tests()
            self.main_window.load_workspace(workspace)
            self.main_window.tabs.setCurrentIndex(1)
        def on_failed(error):
            self.extract_button.setEnabled(True)
            self.main_window._set_status(f"Extraction failed: {error}", "error")
            QMessageBox.critical(self, "Extraction failed", str(error))
        worker = Worker(run_extraction)
        worker.signals.finished.connect(on_done)
        worker.signals.failed.connect(on_failed)
        self.main_window.start_worker(worker)

    def process_batch_checked(self) -> None:
        selected = [
            self.exam_list.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(self.exam_list.count())
            if self.exam_list.item(index).checkState() == Qt.CheckState.Checked
        ]
        if not selected:
            QMessageBox.warning(self, "No exams selected", "Check one or more exams to process.")
            return
        if not self.main_window.confirm_discard_changes():
            return
        self.main_window._set_status(f"Extracting questions for {len(selected)} exam(s)...", "busy")
        self.batch_button.setEnabled(False)
        def run_batch():
            return process_workspaces(selected, self.config)
        def on_done(reports):
            self.batch_button.setEnabled(True)
            successes = sum(1 for r in reports if r.success)
            self.main_window._set_status(f"Batch complete: {successes}/{len(reports)} exams processed successfully.", "success")
            self.main_window.populate_tests()
            if selected:
                self.main_window.load_workspace(selected[0])
            self.main_window.tabs.setCurrentIndex(1)
        def on_failed(error):
            self.batch_button.setEnabled(True)
            self.main_window._set_status(f"Batch failed: {error}", "error")
            QMessageBox.critical(self, "Batch failed", str(error))
        worker = Worker(run_batch)
        worker.signals.finished.connect(on_done)
        worker.signals.failed.connect(on_failed)
        self.main_window.start_worker(worker)

    def launch_ai(self) -> None:
        workspace = self.main_window.state["workspace"]
        if not workspace:
            QMessageBox.warning(self, "No exam selected", "Choose an exam before creating an AI prompt.")
            return
        data = self.ai_provider_combo.currentData()
        if not data:
            return
        provider, custom_command = data
        self.main_window._set_status(f"Generating AI prompt for {workspace.name}...", "busy")
        self.launch_ai_button.setEnabled(False)
        def make_prompt():
            return generate_workspace_prompt(
                workspace,
                self.config,
                pdf_path=self.pdf_combo.currentData(),
                answers_path=self.answer_combo.currentData(),
                form_value=self.form_edit.text(),
            )
        def on_done(prompt_text):
            self.launch_ai_button.setEnabled(True)
            if not custom_command:
                opened = open_web_provider(provider, prompt_text)
                self.main_window._set_status(f"Prompt copied to clipboard! Opening {provider.label}...", "success")
                msg = (
                    f"The full question extraction prompt has been copied to your clipboard!\n\n"
                    f"1. Paste it into {provider.label}.\n"
                    f"2. Attach the exam PDF ({self.pdf_combo.currentText()}).\n"
                    f"3. When done, copy the response and paste into questions.md in the review tab."
                )
                if not opened:
                    msg += f"\n\n(Could not open browser automatically — navigate to {provider.url} manually.)"
                QMessageBox.information(self, f"AI Prompt Ready ({provider.label})", msg)
            else:
                self.main_window._set_status(f"Running {provider.label} ({custom_command})...", "busy")
                self.launch_ai_button.setEnabled(False)
                def run_local():
                    return send_to_provider(provider, prompt_text, command=custom_command)
                def on_local_done(result):
                    self.launch_ai_button.setEnabled(True)
                    if result.success:
                        self.main_window._set_status(f"{provider.label} finished successfully!", "success")
                        self.main_window.load_workspace(workspace)
                        self.main_window.tabs.setCurrentIndex(1)
                        QMessageBox.information(self, "AI Execution Finished", f"{provider.label} extracted questions successfully!\n\nSaved to: questions.md")
                    else:
                        self.main_window._set_status(f"{provider.label} failed: {result.error}", "error")
                        QMessageBox.critical(self, "AI Execution Failed", f"Local AI execution returned an error:\n\n{result.error}")
                def on_local_failed(err):
                    self.launch_ai_button.setEnabled(True)
                    self.main_window._set_status(f"Local AI error: {err}", "error")
                    QMessageBox.critical(self, "AI Execution Error", str(err))
                local_worker = Worker(run_local)
                local_worker.signals.finished.connect(on_local_done)
                local_worker.signals.failed.connect(on_local_failed)
                self.main_window.start_worker(local_worker)
        def on_failed(error):
            self.launch_ai_button.setEnabled(True)
            self.main_window._set_status(f"Prompt generation failed: {error}", "error")
            QMessageBox.critical(self, "Prompt Generation Error", str(error))
        worker = Worker(make_prompt)
        worker.signals.finished.connect(on_done)
        worker.signals.failed.connect(on_failed)
        self.main_window.start_worker(worker)

    def open_super_batch(self) -> None:
        if not self.main_window.state["root"]:
            QMessageBox.warning(self, "No exam folder", "Choose an exam folder first.")
            return
        local_providers = detect_providers(self.config.provider.freebuff_commands)
        if not local_providers:
            guide = QMessageBox(self)
            guide.setIcon(QMessageBox.Icon.Information)
            guide.setWindowTitle("Local CLI AI Agent Required")
            guide.setText(
                "Super Batch requires a locally installed CLI AI agent (such as gemini, claude, codex, or a local ollama runner).\n\n"
                "Would you like to open the CLI Agent Setup Guide to see how to install one?"
            )
            guide.addButton("Open Setup Guide", QMessageBox.ButtonRole.AcceptRole)
            guide.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            if guide.exec() == 0:
                self.show_cli_agent_guide()
            return
        dialog = SuperBatchDialog(
            self,
            root=self.main_window.state["root"],
            config=self.config,
            local_providers=local_providers,
            discard_rule=self.discard_range_edit.text().strip() or "std",
        )
        if dialog.exec() == SuperBatchDialog.DialogCode.Accepted:
            exec_plan = dialog.get_execution_plan()
            if not exec_plan.items:
                QMessageBox.information(self, "Super Batch", "No exams selected for Super Batch.")
                return
            provider_opt, command_opt = dialog.get_selected_provider()
            self._start_super_batch_execution(exec_plan, provider_opt, command_opt, dialog.workers_spin.value())

    def _start_super_batch_execution(self, exec_plan, provider_opt, command_opt: str, workers: int) -> None:
        cancel_event = threading.Event()
        progress_dlg = SuperBatchProgressDialog(
            self,
            exec_plan=exec_plan,
            provider_label=f"{provider_opt.label} ({command_opt})",
            cancel_event=cancel_event,
        )
        self.main_window._set_status(f"Running Super Batch ({len(exec_plan.items)} exams) with {provider_opt.label}...", "busy")
        def _batch_worker():
            from ...super_batch import process_plan
            return process_plan(
                plan=exec_plan,
                config=self.config,
                provider_command=command_opt,
                workers=workers,
                cancel_event=cancel_event,
                on_item_completed=progress_dlg.on_item_completed,
            )
        def _batch_done(results):
            progress_dlg.accept()
            self.main_window._set_status("Super Batch run completed.", "success")
            self.main_window.populate_tests()
            def _handle_retry_failed(failed_items):
                retry_plan = type(exec_plan)(root=exec_plan.root, items=tuple(failed_items))
                self._start_super_batch_execution(retry_plan, provider_opt, command_opt, workers)
            summary_dlg = SuperBatchSummaryDialog(self, results, on_retry_failed=_handle_retry_failed)
            summary_dlg.exec()
        def _batch_failed(err):
            progress_dlg.accept()
            self.main_window._set_status(f"Super Batch failed: {err}", "error")
            QMessageBox.critical(self, "Super Batch Error", f"Super Batch encountered an unexpected error:\n\n{err}")
        worker = Worker(_batch_worker)
        worker.signals.finished.connect(_batch_done)
        worker.signals.failed.connect(_batch_failed)
        self.main_window.start_worker(worker)
        progress_dlg.exec()

    def open_web_batch_wizard(self) -> None:
        selected = [
            self.exam_list.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(self.exam_list.count())
            if self.exam_list.item(index).checkState() == Qt.CheckState.Checked
        ]
        if not selected:
            if self.main_window.state["workspace"]:
                selected = [self.main_window.state["workspace"]]
            else:
                all_ws = [
                    self.exam_list.item(i).data(Qt.ItemDataRole.UserRole)
                    for i in range(self.exam_list.count())
                    if self.exam_list.item(i).data(Qt.ItemDataRole.UserRole) is not None
                ]
                if all_ws:
                    selected = all_ws
                else:
                    QMessageBox.warning(self, "No exams available", "Please select or check one or more exams first.")
                    return
        dialog = WebAIBatchDialog(
            parent=self,
            workspaces=selected,
            config=self.config,
            dark_mode=self.main_window.dark_mode,
        )
        dialog.exec()
        self.main_window.populate_tests()
        if self.main_window.state["workspace"]:
            self.main_window.load_workspace(self.main_window.state["workspace"])

