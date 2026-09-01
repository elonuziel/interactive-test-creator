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
    QSpinBox,
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
from ...form_numbers import resolve_form_number
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

        # ── LEFT panel: Choose an exam ──────────────────────────────────
        self.exam_group = QGroupBox("1. Choose an exam")
        left = QVBoxLayout(self.exam_group)
        self.exam_search = QLineEdit()
        self.exam_search.setPlaceholderText("🔍 Search exams…")

        self.exam_list = QListWidget()
        self.exam_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        exam_sel_row = QHBoxLayout()
        self.exam_select_all_btn = QPushButton("Select all")
        self.exam_select_all_btn.setObjectName("secondary")
        self.exam_select_all_btn.setToolTip("Check all visible exams in the list")
        self.exam_deselect_all_btn = QPushButton("Deselect all")
        self.exam_deselect_all_btn.setObjectName("secondary")
        self.exam_deselect_all_btn.setToolTip("Uncheck all exams in the list")
        exam_sel_row.addWidget(self.exam_select_all_btn)
        exam_sel_row.addWidget(self.exam_deselect_all_btn)

        # Separator before batch actions
        batch_sep = QFrame()
        batch_sep.setObjectName("separator")
        batch_sep.setFrameShape(QFrame.Shape.HLine)
        batch_sep.setFixedHeight(1)

        batch_label = QLabel("Batch actions")
        batch_label.setObjectName("sectionHeader")

        self.batch_button = QPushButton("⚙️ Extract checked exams")
        self.batch_button.setToolTip("Extract questions from all checked exams at once (digital PDFs only)")

        self.web_batch_button = QPushButton("🌐 Web AI Batch…")
        self.web_batch_button.setToolTip(
            "Step-by-step batch assistant for ChatGPT, Claude, Gemini Web, and Google AI Studio "
            "(1 PDF at a time with auto prompt copying and answer merging)."
        )

        super_batch_row = QHBoxLayout()
        self.super_batch_button = QPushButton("🤖 Super Batch (Local AI)…")
        self.super_batch_button.setToolTip(
            "Run a local CLI AI agent on multiple exams automatically."
        )
        self.super_batch_info_btn = QPushButton("ℹ️")
        self.super_batch_info_btn.setObjectName("secondary")
        self.super_batch_info_btn.setMaximumWidth(32)
        self.super_batch_info_btn.setToolTip("Learn about local CLI AI agents and how to install one.")
        super_batch_row.addWidget(self.super_batch_button, 1)
        super_batch_row.addWidget(self.super_batch_info_btn)

        left.addWidget(self.exam_search)
        left.addWidget(self.exam_list, 1)
        left.addLayout(exam_sel_row)
        left.addWidget(batch_sep)
        left.addWidget(batch_label)
        left.addWidget(self.batch_button)
        left.addWidget(self.web_batch_button)
        left.addLayout(super_batch_row)
        self.extract_splitter.addWidget(self.exam_group)

        # ── RIGHT panel: Prepare questions ──────────────────────────────
        self.extract_group = QGroupBox("2. Prepare questions (saved as questions.md)")
        right = QVBoxLayout(self.extract_group)
        right.setSpacing(8)

        # Current exam title
        self.current_exam_title = QLabel("Choose an exam from the list")
        self.current_exam_title.setObjectName("sectionHeader")

        # — File selection row —
        self.pdf_combo = QComboBox()
        self.pdf_combo.addItem("No exam file selected", None)
        self.browse_pdf_button = QPushButton("Browse…")
        self.browse_pdf_button.setObjectName("secondary")
        self.browse_pdf_button.setToolTip("Select a custom PDF or Word (DOCX) exam file")
        pdf_row = QHBoxLayout()
        pdf_row.addWidget(QLabel("Exam file:"))
        pdf_row.addWidget(self.pdf_combo, 1)
        pdf_row.addWidget(self.browse_pdf_button)

        # — Detection badge (compact single line) —
        detection_row = QHBoxLayout()
        self.detection_title = QLabel("◦ PDF type: awaiting selection")
        self.detection_title.setObjectName("sectionHint")
        self.detection_description = QLabel("")
        self.detection_description.setObjectName("sectionHint")
        self.detection_description.setWordWrap(True)
        detection_row.addWidget(self.detection_title)
        detection_row.addStretch()

        # — Clean PDF group (moved up: logically follows file selection) —
        self.clean_group = QGroupBox("Clean PDF  —  discard blank & cover pages")
        clean_layout = QVBoxLayout(self.clean_group)
        clean_layout.setSpacing(6)
        self.clean_hint = QLabel(
            "Remove blank/cover pages before AI extraction or OCR to reduce noise."
        )
        self.clean_hint.setObjectName("sectionHint")
        self.clean_hint.setWordWrap(True)
        clean_layout.addWidget(self.clean_hint)

        preset_row = QHBoxLayout()
        self.preset_std_button = QPushButton("🧹 Standard (std)")
        self.preset_std_button.setObjectName("secondary")
        self.preset_std_button.setToolTip("Discards cover pages 1-4 and even pages (6, 8, 10…)")
        self.preset_even_button = QPushButton("Even pages")
        self.preset_even_button.setObjectName("secondary")
        self.preset_odd_button = QPushButton("Odd pages")
        self.preset_odd_button.setObjectName("secondary")
        self.preset_clear_button = QPushButton("↺ Reset")
        self.preset_clear_button.setObjectName("secondary")
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
        self.clean_pdf_button.setToolTip("Creates <name>_clean.pdf without the discarded pages")
        range_row.addWidget(self.clean_pdf_button)
        clean_layout.addLayout(range_row)

        self.clean_summary_label = QLabel("Select an exam to calculate kept pages.")
        self.clean_summary_label.setObjectName("sectionHint")
        clean_layout.addWidget(self.clean_summary_label)

        # — Answer key + form number (below Clean PDF) —
        answer_row = QHBoxLayout()
        self.answer_combo = QComboBox()
        self.answer_combo.addItem("No answer key", None)
        self.browse_answer_button = QPushButton("Browse…")
        self.browse_answer_button.setObjectName("secondary")
        self.browse_answer_button.setToolTip("Select a custom CSV or Excel (XLS/XLSX) answer key")
        self.form_edit = QLineEdit("")
        self.form_edit.setPlaceholderText("Auto")
        self.form_edit.setMaximumWidth(72)
        self.form_edit.setToolTip(
            "Detected from the selected PDF. Edit only to override."
        )
        answer_row.addWidget(QLabel("Answer key:"))
        answer_row.addWidget(self.answer_combo, 1)
        answer_row.addWidget(self.browse_answer_button)
        answer_row.addWidget(QLabel("Form:"))
        answer_row.addWidget(self.form_edit)

        # — Separator before extraction actions —
        extract_sep = QFrame()
        extract_sep.setObjectName("separator")
        extract_sep.setFrameShape(QFrame.Shape.HLine)
        extract_sep.setFixedHeight(1)

        extract_label = QLabel("Extract questions")
        extract_label.setObjectName("sectionHeader")

        # — Extract button (digital PDFs) —
        self.extract_button = QPushButton("⚙️ Extract questions from PDF")
        self.extract_button.setObjectName("primary")
        self.extract_button.setToolTip(
            "Automatically extract questions from this digital PDF. "
            "Results are saved as questions.md."
        )

        # — AI row (scanned / manual path) —
        ai_row = QHBoxLayout()
        self.ai_provider_combo = QComboBox()
        local_items = detect_providers(self.config.provider.freebuff_commands)
        for provider, command in local_items:
            self.ai_provider_combo.addItem(f"Local: {provider.label} ({command})", (provider, command))
        for provider in WEB_PROVIDERS:
            self.ai_provider_combo.addItem(f"Web: {provider.label}", (provider, None))
        self.launch_ai_button = QPushButton("Create AI prompt")
        self._on_ai_provider_changed()
        self.launch_ai_button.setToolTip("Generate a prompt for extracting questions into questions.md.")
        self.ai_info_btn = QPushButton("ℹ️")
        self.ai_info_btn.setObjectName("secondary")
        self.ai_info_btn.setMaximumWidth(32)
        self.ai_info_btn.setToolTip("What is a CLI AI agent? Click to learn how to install one.")
        ai_row.addWidget(self.ai_provider_combo, 2)
        ai_row.addWidget(self.launch_ai_button, 3)
        ai_row.addWidget(self.ai_info_btn)

        # — Description under detection (word-wrapped, shown below AI row) —
        self.detection_description.setVisible(False)  # hidden until PDF is selected

        # — Collapsible PDF Preview —
        self.preview_toggle_btn = QPushButton("▶  PDF Preview  (collapsed)")
        self.preview_toggle_btn.setObjectName("secondary")
        self.preview_toggle_btn.setToolTip("Click to expand / collapse the PDF preview panel")
        self.preview_toggle_btn.setCheckable(True)

        self.preview_container = QWidget()
        self.preview_container.setVisible(False)
        preview_inner = QVBoxLayout(self.preview_container)
        preview_inner.setContentsMargins(0, 4, 0, 4)
        preview_inner.setSpacing(4)

        # Page navigation
        page_nav_row = QHBoxLayout()
        page_nav_row.addWidget(QLabel("Page:"))
        self.preview_page_spin = QSpinBox()
        self.preview_page_spin.setRange(1, 9999)
        self.preview_page_spin.setValue(1)
        self.preview_page_spin.setMaximumWidth(70)
        self.preview_page_spin.setToolTip("Jump to any page in the PDF")
        self.preview_button = QPushButton("⟳ Load page")
        self.preview_button.setObjectName("secondary")
        page_nav_row.addWidget(self.preview_page_spin)
        page_nav_row.addWidget(self.preview_button)
        page_nav_row.addStretch()
        preview_inner.addLayout(page_nav_row)

        self.preview = QLabel("No preview loaded")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(200, 180)
        preview_inner.addWidget(self.preview, 1)

        # — Navigation (bottom) —
        self.next_review_button = QPushButton("Next: Review →")
        self.next_review_button.setObjectName("primary")

        # Assemble right panel
        right.addWidget(self.current_exam_title)
        right.addLayout(pdf_row)
        right.addLayout(detection_row)
        right.addWidget(self.detection_description)
        right.addWidget(self.clean_group)
        right.addLayout(answer_row)
        right.addWidget(extract_sep)
        right.addWidget(extract_label)
        right.addWidget(self.extract_button)
        right.addLayout(ai_row)
        right.addWidget(self.preview_toggle_btn)
        right.addWidget(self.preview_container)
        right.addStretch()

        nav_row = QHBoxLayout()
        nav_row.addStretch()
        nav_row.addWidget(self.next_review_button)
        right.addLayout(nav_row)

        # Stub for removed ai_hint (kept as a QLabel property for any backward refs)
        self.ai_hint = QLabel()
        self.ai_hint.setVisible(False)

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
        self.preview_button.clicked.connect(self.preview_current_page)
        self.preview_page_spin.valueChanged.connect(self.preview_current_page)
        self.preview_toggle_btn.toggled.connect(self._on_preview_toggled)
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
        if not workspace or not selected_pdf or not Path(selected_pdf).is_file():
            self.update_clean_summary()
            return
        pdf_path = Path(selected_pdf)
        try:
            import fitz
            text = "\n".join(page.get_text() for page in fitz.open(pdf_path))
        except Exception:
            text = ""
        detected = resolve_form_number(text, pdf_path.name)
        if detected.status == "resolved" and detected.raw_value:
            self.form_edit.setText(detected.raw_value)
            self.form_edit.setToolTip(f"Auto-detected from {detected.candidate.source}; normalized lookup value: {detected.normalized_value}. Edit to override.")
        elif detected.status == "ambiguous":
            self.form_edit.clear()
            self.form_edit.setToolTip("Multiple possible form numbers detected. Confirm one before using an answer key.")
        else:
            self.form_edit.clear()
            self.form_edit.setToolTip("No form number detected. Enter one only as an explicit override.")
        self.main_window._set_status("Analyzing selected PDF...", "busy")
        pdf_path = Path(selected_pdf)
        def _classify():
            return classify_pdf(pdf_path)
        worker = Worker(_classify)

        def _classified(is_digital):
            self.main_window._set_status("")
            if is_digital:
                self.detection_title.setText("◦ Digital PDF — extract automatically")
                self.detection_description.setText(
                    "This PDF contains selectable text. Use the Extract button below."
                )
                self.extract_button.setEnabled(True)
            else:
                self.detection_title.setText("◦ Scanned PDF — use AI prompt")
                self.detection_description.setText(
                    "This is an image-based PDF. Use the AI provider below to generate a prompt."
                )
                self.extract_button.setEnabled(False)
            self.detection_description.setVisible(True)
            self.update_clean_summary()

        def _classify_failed(err):
            self.main_window._set_status("")
            self.detection_title.setText("◦ PDF analysis unavailable")
            self.detection_description.setText(
                f"{err}\nYou can still create an AI prompt or check the PDF manually."
            )
            self.detection_description.setVisible(True)
            self.extract_button.setEnabled(True)
            self.update_clean_summary()

        worker.signals.finished.connect(_classified)
        worker.signals.failed.connect(_classify_failed)
        self.main_window.start_worker(worker)

    def _on_preview_toggled(self, checked: bool) -> None:
        """Expand or collapse the preview panel."""
        self.preview_container.setVisible(checked)
        if checked:
            self.preview_toggle_btn.setText("▼  PDF Preview  (expanded)")
            self.preview_current_page()
        else:
            self.preview_toggle_btn.setText("▶  PDF Preview  (collapsed)")

    def preview_first_page(self) -> None:
        """Kept for backward compatibility — open preview at page 1."""
        self.preview_page_spin.setValue(1)
        self.preview_current_page()

    def preview_current_page(self) -> None:
        """Load the page currently selected in preview_page_spin."""
        target = self.pdf_combo.currentData()
        if not target or not Path(target).is_file():
            self.preview.setText("No valid exam file selected.")
            return
        if not self.preview_container.isVisible():
            return  # don't load if preview is collapsed
        page_num = self.preview_page_spin.value() - 1  # 0-indexed
        self.preview.setText("Loading preview…")

        # Update max page count (try to open PDF to read page count)
        pdf_path = Path(target)
        try:
            import fitz
            doc = fitz.open(pdf_path)
            page_count = len(doc)
            doc.close()
            self.preview_page_spin.setRange(1, max(1, page_count))
            self.preview_page_spin.setToolTip(f"Page (1–{page_count})")
        except Exception:
            pass

        worker = Worker(lambda: render_pdf_page(pdf_path, page_number=page_num))
        worker.signals.finished.connect(self._apply_preview)
        worker.signals.failed.connect(
            lambda error: self.preview.setText(f"Preview error:\n{error}")
        )
        self.main_window.start_worker(worker)

    def _apply_preview(self, png_bytes: bytes) -> None:
        """Render PNG bytes returned by render_pdf_page into the preview label."""
        from PySide6.QtGui import QImage
        image = QImage.fromData(png_bytes, "PNG")
        if image.isNull():
            self.preview.setText("Preview could not be displayed.")
            return
        pixmap = QPixmap.fromImage(image)
        scaled = pixmap.scaled(
            self.preview.width() or 400, 600,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview.setPixmap(scaled)

    def set_discard_preset(self, rule: str) -> None:
        self.discard_range_edit.setText(rule)
        self.update_clean_summary()

    def update_clean_summary(self) -> None:
        pdf = self.pdf_combo.currentData()
        if not pdf or not Path(pdf).is_file() or Path(pdf).suffix.lower() != ".pdf":
            self.clean_summary_label.setText("Select a PDF exam to calculate kept pages.")
            return
        try:
            info = describe_page_cleaning(Path(pdf), self.discard_range_edit.text().strip())
            if info["total"] == 0:
                self.clean_summary_label.setText("Could not inspect PDF page count.")
            else:
                self.clean_summary_label.setText(
                    f"Total {info['total']} page(s) → Keeping {info['kept_count']} page(s) ({info['discarded_count']} discarded)"
                )
        except Exception:
            self.clean_summary_label.setText("⚠️ Invalid page range or rule.")

    def run_clean_pdf(self) -> None:
        workspace = self.main_window.state["workspace"]
        if not workspace:
            QMessageBox.warning(self, "No exam selected", "Choose an exam from the list first.")
            return
        pdf = self.pdf_combo.currentData()
        if not pdf or not Path(pdf).is_file():
            QMessageBox.warning(self, "No PDF selected", "Choose a valid PDF file to clean.")
            return
        source_pdf = Path(pdf)
        clean_name = f"{source_pdf.stem}_clean.pdf" if not source_pdf.stem.endswith("_clean") else source_pdf.name
        clean_path = workspace.path / clean_name
        discard_spec = self.discard_range_edit.text().strip() or "std"
        self.clean_pdf_button.setEnabled(False)
        self.main_window._set_status("Cleaning PDF pages...", "busy")

        def _do_clean():
            return clean_pdf(source_pdf, clean_path, discard_spec)

        def _on_done(result):
            self.clean_pdf_button.setEnabled(True)
            total, kept = result
            self.main_window._set_status(f"Created clean PDF with {kept}/{total} pages.", "success")
            self._add_and_select_pdf(clean_path)
            QMessageBox.information(
                self,
                "PDF Cleaned",
                f"Cleaned PDF created successfully!\n\nKept {kept} of {total} pages.\nSaved as: {clean_name}",
            )

        def _on_failed(err):
            self.clean_pdf_button.setEnabled(True)
            self.main_window._set_status(f"Failed to clean PDF: {err}", "error")
            QMessageBox.critical(self, "Clean PDF Failed", str(err))

        worker = Worker(_do_clean)
        worker.signals.finished.connect(_on_done)
        worker.signals.failed.connect(_on_failed)
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
                self.config,
                workspace.path,
                answer_key=self.answer_combo.currentData(),
                form=self.form_edit.text().strip() or None,
                pdf=self.pdf_combo.currentData(),
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
                self.config,
                workspace.path,
                kind="web" if not custom_command else "local",
                form=self.form_edit.text().strip() or None,
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
        checked_names = {
            self.exam_list.item(i).data(Qt.ItemDataRole.UserRole).name
            for i in range(self.exam_list.count())
            if self.exam_list.item(i).checkState() == Qt.CheckState.Checked and self.exam_list.item(i).data(Qt.ItemDataRole.UserRole)
        }

        dialog = SuperBatchDialog(
            self,
            root=self.main_window.state["root"],
            config=self.config,
            local_providers=local_providers,
            discard_rule=self.discard_range_edit.text().strip() or "std",
            initially_checked_names=checked_names if checked_names else None,
        )
        if dialog.exec() == SuperBatchDialog.DialogCode.Accepted:
            exec_plan = dialog.get_execution_plan()
            if not exec_plan.items:
                QMessageBox.information(self, "Super Batch", "No exams selected for Super Batch.")
                return
            provider_opt, command_opt = dialog.get_selected_provider()
            params = dialog.get_execution_params()
            self._start_super_batch_execution(exec_plan, provider_opt, command_opt, params["workers"], params)

    def _start_super_batch_execution(self, exec_plan, provider_opt, command_opt: str, workers: int, params: dict | None = None) -> None:
        params = params or {}
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
                provider=provider_opt,
                command=command_opt,
                ai_mode=params.get("ai_mode", "two_phase"),
                context_mode=params.get("context_mode", "path"),
                discard_pages=params.get("discard_pages", ""),
                clean_digital=params.get("clean_digital", False),
                auto_build_html=params.get("auto_build_html", True),
                auto_build_hub=params.get("auto_build_hub", True),
                workers=workers,
                cancel_event=cancel_event,
                progress=progress_dlg.update_item_progress,
            )
        def _batch_done(results):
            progress_dlg.accept()
            self.main_window._set_status("Super Batch run completed.", "success")
            self.main_window.populate_tests()
            def _handle_retry_failed(failed_items):
                retry_plan = type(exec_plan)(root=exec_plan.root, items=tuple(failed_items))
                self._start_super_batch_execution(retry_plan, provider_opt, command_opt, workers, params)
            summary_dlg = SuperBatchSummaryDialog(self, list(results), self.config, on_retry_failed=_handle_retry_failed)
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

