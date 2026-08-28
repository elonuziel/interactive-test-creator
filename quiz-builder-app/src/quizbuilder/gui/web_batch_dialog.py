from __future__ import annotations

import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any
import webbrowser

from PySide6.QtCore import QFileSystemWatcher, QMimeData, QPoint, QRect, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QCursor, QDrag, QFont, QIcon, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..commands import generate_workspace_prompt
from ..config import Config
from ..documents import classify_pdf, clean_pdf, preferred_pdf
from ..exporter import build_standalone_quiz
from ..markdown import dump_questions, load_questions as load_markdown_questions, write_questions
from ..pipeline import PipelineRunner
from ..prompts import extract_markdown_from_response
from ..providers import WEB_PROVIDERS, Provider, open_web_provider
from ..validation import ValidationError, load_questions
from ..workspace import Workspace, discover_sources
from .workers import Worker

LOGGER = logging.getLogger(__name__)


def reveal_in_file_manager(path: Path) -> None:
    """Reveal a file in the operating system's native file manager with the file selected."""
    path = path.resolve()
    if not path.exists():
        return
    try:
        if os.name == "nt":
            subprocess.Popen(f'explorer /select,"{path}"')
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
        else:
            # Linux: try file managers supporting --select, otherwise open parent folder
            if shutil.which("nautilus"):
                subprocess.Popen(["nautilus", "--select", str(path)])
            elif shutil.which("dolphin"):
                subprocess.Popen(["dolphin", "--select", str(path)])
            elif shutil.which("nemo"):
                subprocess.Popen(["nemo", "--select", str(path)])
            else:
                webbrowser.open(path.parent.as_uri())
    except Exception as exc:
        LOGGER.warning("Could not reveal file in manager: %s", exc)
        try:
            webbrowser.open(path.parent.as_uri())
        except Exception:
            pass


def copy_file_to_clipboard(path: Path) -> bool:
    """Copy a file reference and path to system clipboard for pasting into file pickers or chats."""
    path = path.resolve()
    if not path.is_file():
        return False
    try:
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(path))])
        mime.setText(str(path))
        QApplication.clipboard().setMimeData(mime)
        return True
    except Exception as exc:
        LOGGER.warning("Could not copy file to clipboard: %s", exc)
        return False


class DraggablePdfWidget(QFrame):
    """A dedicated widget representing a single PDF file that can be dragged directly into a browser."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.pdf_path: Path | None = None
        self._drag_start_pos: QPoint | None = None
        self.setObjectName("draggablePdf")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setToolTip("Click and drag this PDF directly into ChatGPT, Claude, Gemini Web, or Google AI Studio!")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        self.icon_label = QLabel("📄")
        self.icon_label.setStyleSheet("font-size: 26px;")
        layout.addWidget(self.icon_label)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        self.name_label = QLabel("No PDF file")
        self.name_label.setStyleSheet("font-weight: 700; font-size: 13px;")
        self.meta_label = QLabel("Drag into browser window")
        self.meta_label.setStyleSheet("color: #64748b; font-size: 11px;")
        info_layout.addWidget(self.name_label)
        info_layout.addWidget(self.meta_label)
        layout.addLayout(info_layout, 1)

        self.drag_hint_badge = QLabel("✋ Drag to Web AI")
        self.drag_hint_badge.setStyleSheet(
            "background: #2563eb; color: #ffffff; padding: 4px 10px; border-radius: 5px; font-weight: 600; font-size: 11px;"
        )
        layout.addWidget(self.drag_hint_badge)

    def set_pdf(self, path: Path | None) -> None:
        self.pdf_path = path
        if path and path.is_file():
            size_kb = path.stat().st_size / 1024
            size_str = f"{size_kb / 1024:.1f} MB" if size_kb > 1024 else f"{size_kb:.0f} KB"
            self.name_label.setText(path.name)
            self.meta_label.setText(f"{size_str} • Click & drag directly into web chat")
            self.setEnabled(True)
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.name_label.setText("No PDF found in exam folder")
            self.meta_label.setText("Add a PDF or DOCX file to continue")
            self.setEnabled(False)
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.pdf_path and self.pdf_path.is_file():
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if not (event.buttons() & Qt.MouseButton.LeftButton) or not self._drag_start_pos or not self.pdf_path:
            return
        if (event.pos() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(self.pdf_path.resolve()))])
        mime.setText(str(self.pdf_path.resolve()))
        drag.setMimeData(mime)

        pixmap = self.grab()
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.pos())

        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        drag.exec(Qt.DropAction.CopyAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._drag_start_pos = None


class BatchQueueItem:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.status = "pending"  # "pending", "in_progress", "saved", "skipped"
        self.questions_count = 0
        self.error: str | None = None
        self.pdf_path: Path | None = None
        self.answer_key_path: Path | None = None
        self.is_digital = False


class WebAIBatchDialog(QDialog):
    """Step-by-step Batch Wizard dialog for processing multiple exams with Web AI one PDF at a time."""

    def __init__(
        self,
        parent: QWidget | None,
        workspaces: list[Workspace],
        config: Config,
        dark_mode: bool = False,
    ):
        super().__init__(parent)
        self.workspaces = workspaces
        self.config = config
        self.dark_mode = dark_mode
        self.items: list[BatchQueueItem] = [BatchQueueItem(ws) for ws in workspaces]
        self.current_index = 0
        self.watcher = QFileSystemWatcher(self)
        self.watcher.directoryChanged.connect(self._on_dir_changed)
        self.watcher.fileChanged.connect(self._on_file_changed)

        self.setWindowTitle("🌐 Web AI Batch Assistant — 1 PDF at a Time")
        self.setMinimumSize(960, 680)
        self.resize(1080, 750)
        self.setAcceptDrops(True)

        self._build_ui()
        self._init_queue_data()
        self._select_item(0)

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 14, 16, 14)
        root_layout.setSpacing(12)

        # Header bar with progress
        header_bar = QFrame()
        header_bar.setObjectName("topBar")
        h_layout = QHBoxLayout(header_bar)
        h_layout.setContentsMargins(14, 10, 14, 10)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        dlg_title = QLabel("🌐 Web AI Batch Assistant")
        dlg_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #2563eb;" if not self.dark_mode else "font-size: 16px; font-weight: 700; color: #60a5fa;")
        dlg_subtitle = QLabel("Process multiple exams with Web AI — 1 PDF at a time with 1-click prompt copying & instant answer merging.")
        dlg_subtitle.setStyleSheet("color: #64748b; font-size: 12px;")
        title_col.addWidget(dlg_title)
        title_col.addWidget(dlg_subtitle)
        h_layout.addLayout(title_col, 1)

        progress_col = QVBoxLayout()
        progress_col.setSpacing(4)
        progress_col.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.progress_label = QLabel(f"Exam 1 of {len(self.items)}")
        self.progress_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, len(self.items))
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedWidth(180)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setTextVisible(False)
        progress_col.addWidget(self.progress_label)
        progress_col.addWidget(self.progress_bar)
        h_layout.addLayout(progress_col)
        root_layout.addWidget(header_bar)

        # Main splitter (Queue list on left, current exam workspace on right)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Left: Queue Navigation
        queue_group = QGroupBox("Batch Queue")
        q_layout = QVBoxLayout(queue_group)
        q_layout.setSpacing(8)

        self.queue_list = QListWidget()
        self.queue_list.currentRowChanged.connect(self._on_queue_row_changed)
        q_layout.addWidget(self.queue_list, 1)

        queue_btn_row = QHBoxLayout()
        self.prev_btn = QPushButton("◀ Previous")
        self.prev_btn.setToolTip("Go back to previous exam")
        self.prev_btn.clicked.connect(self.prev_exam)
        self.skip_btn = QPushButton("⏭️ Skip")
        self.skip_btn.setToolTip("Skip this exam and move to next")
        self.skip_btn.clicked.connect(self.skip_current)
        queue_btn_row.addWidget(self.prev_btn)
        queue_btn_row.addWidget(self.skip_btn)
        q_layout.addLayout(queue_btn_row)

        splitter.addWidget(queue_group)

        # Right: Current Exam Workspace
        right_container = QWidget()
        r_layout = QVBoxLayout(right_container)
        r_layout.setContentsMargins(0, 0, 0, 0)
        r_layout.setSpacing(10)

        # 1. Exam overview banner
        self.exam_title_banner = QLabel("Active Exam: -")
        self.exam_title_banner.setStyleSheet("font-size: 15px; font-weight: 700;")
        self.exam_path_label = QLabel("")
        self.exam_path_label.setStyleSheet("color: #64748b; font-size: 11px;")
        r_layout.addWidget(self.exam_title_banner)
        r_layout.addWidget(self.exam_path_label)

        # 2. Step 1: Upload Single PDF
        step1_group = QGroupBox("Step 1 — Upload 1 PDF (Drag or Copy)")
        s1_layout = QVBoxLayout(step1_group)
        s1_layout.setSpacing(8)

        self.draggable_pdf = DraggablePdfWidget()
        s1_layout.addWidget(self.draggable_pdf)

        pdf_actions = QHBoxLayout()
        pdf_actions.setSpacing(8)
        self.reveal_pdf_btn = QPushButton("📁 Reveal in Folder")
        self.reveal_pdf_btn.setToolTip("Open folder with PDF file highlighted for dragging into browser")
        self.reveal_pdf_btn.clicked.connect(self._reveal_current_pdf)

        self.copy_pdf_file_btn = QPushButton("📋 Copy PDF File")
        self.copy_pdf_file_btn.setToolTip("Copy the actual PDF file to clipboard")
        self.copy_pdf_file_btn.clicked.connect(self._copy_current_pdf_file)

        self.copy_pdf_path_btn = QPushButton("📋 Copy Path")
        self.copy_pdf_path_btn.setToolTip("Copy absolute path to clipboard")
        self.copy_pdf_path_btn.clicked.connect(self._copy_current_pdf_path)

        self.clean_pdf_btn = QPushButton("🧹 Clean PDF")
        self.clean_pdf_btn.setToolTip("Create a cleaned PDF (discarding cover/even/odd pages)")
        self.clean_pdf_btn.clicked.connect(self._clean_current_pdf)

        pdf_actions.addWidget(self.reveal_pdf_btn)
        pdf_actions.addWidget(self.copy_pdf_file_btn)
        pdf_actions.addWidget(self.copy_pdf_path_btn)
        pdf_actions.addWidget(self.clean_pdf_btn)
        pdf_actions.addStretch()
        s1_layout.addLayout(pdf_actions)
        r_layout.addWidget(step1_group)

        # 3. Step 2: AI Prompt & Web Chat
        step2_group = QGroupBox("Step 2 — Prompt & Web AI")
        s2_layout = QVBoxLayout(step2_group)
        s2_layout.setSpacing(8)

        provider_row = QHBoxLayout()
        provider_row.addWidget(QLabel("Web AI Provider:"))
        self.provider_combo = QComboBox()
        for prov in WEB_PROVIDERS:
            self.provider_combo.addItem(f"🌐 {prov.label}", prov)
        provider_row.addWidget(self.provider_combo, 1)

        self.open_web_btn = QPushButton("🌐 Open / Focus Web AI")
        self.open_web_btn.setStyleSheet("font-weight: 700;")
        self.open_web_btn.setToolTip("Open the chosen Web AI chat in your browser")
        self.open_web_btn.clicked.connect(self._open_web_chat)
        provider_row.addWidget(self.open_web_btn)

        self.recopy_prompt_btn = QPushButton("📋 Re-copy Prompt")
        self.recopy_prompt_btn.setToolTip("Copy the prompt for this exam to clipboard again")
        self.recopy_prompt_btn.clicked.connect(self._copy_prompt_to_clipboard)
        provider_row.addWidget(self.recopy_prompt_btn)
        s2_layout.addLayout(provider_row)

        prompt_opts_row = QHBoxLayout()
        self.enhanced_prompt_check = QCheckBox("Enhanced prompt (image-option safe mode)")
        self.enhanced_prompt_check.setToolTip("Include explicit instructions for questions with image-only choices.")
        self.enhanced_prompt_check.toggled.connect(lambda _: self._prepare_and_copy_prompt(show_badge=True))
        prompt_opts_row.addWidget(self.enhanced_prompt_check)

        self.prompt_status_badge = QLabel("✅ Prompt copied to clipboard!")
        self.prompt_status_badge.setStyleSheet("color: #16a34a; font-weight: 600; font-size: 12px;")
        prompt_opts_row.addWidget(self.prompt_status_badge)
        prompt_opts_row.addStretch()
        s2_layout.addLayout(prompt_opts_row)

        r_layout.addWidget(step2_group)

        # 4. Step 3: Response Intake & Auto-Merge
        step3_group = QGroupBox("Step 3 — Paste Response or Drop questions.md")
        s3_layout = QVBoxLayout(step3_group)
        s3_layout.setSpacing(8)

        intake_info_row = QHBoxLayout()
        intake_info_row.addWidget(QLabel("Paste Web AI markdown output below (or drop a .md file):"))
        self.watcher_status_label = QLabel("👀 Watching exam folder for questions.md")
        self.watcher_status_label.setStyleSheet("color: #64748b; font-size: 11px;")
        intake_info_row.addStretch()
        intake_info_row.addWidget(self.watcher_status_label)
        s3_layout.addLayout(intake_info_row)

        self.response_edit = QPlainTextEdit()
        self.response_edit.setPlaceholderText(
            "Paste Markdown response from ChatGPT / Claude / Gemini here, or drag & drop questions.md file...\n\n"
            "Tip: Click 'Paste & Save (Ctrl+Enter)' below to automatically paste from clipboard, merge answer keys, and advance to next exam!"
        )
        self.response_edit.setMinimumHeight(140)
        s3_layout.addWidget(self.response_edit, 1)

        action_bar = QHBoxLayout()
        self.paste_save_btn = QPushButton("📋 Paste & Save (Ctrl+Enter)")
        self.paste_save_btn.setObjectName("primary")
        self.paste_save_btn.setStyleSheet("font-weight: 700; padding: 8px 18px;")
        self.paste_save_btn.setToolTip("Paste markdown from clipboard, strip code fences, merge answer key, save questions.md and advance!")
        self.paste_save_btn.clicked.connect(self.paste_and_save)

        self.save_next_btn = QPushButton("💾 Save & Next Exam ▶")
        self.save_next_btn.setToolTip("Save the current editor text as questions.md and advance to the next exam")
        self.save_next_btn.clicked.connect(self.save_and_next)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.response_edit.clear)

        action_bar.addWidget(self.paste_save_btn)
        action_bar.addWidget(self.save_next_btn)
        action_bar.addWidget(self.clear_btn)
        action_bar.addStretch()
        s3_layout.addLayout(action_bar)

        r_layout.addWidget(step3_group, 1)

        splitter.addWidget(right_container)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 7)
        root_layout.addWidget(splitter, 1)

        # Dialog footer
        footer_layout = QHBoxLayout()
        self.status_msg_label = QLabel("Ready.")
        self.status_msg_label.setStyleSheet("font-weight: 500;")
        footer_layout.addWidget(self.status_msg_label, 1)

        self.finish_btn = QPushButton("Done / Finish Batch")
        self.finish_btn.clicked.connect(self.finish_batch)
        self.cancel_btn = QPushButton("Close")
        self.cancel_btn.clicked.connect(self.reject)

        footer_layout.addWidget(self.finish_btn)
        footer_layout.addWidget(self.cancel_btn)
        root_layout.addLayout(footer_layout)

        # Keyboard shortcuts
        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(self.paste_and_save)
        QShortcut(QKeySequence("Ctrl+Enter"), self).activated.connect(self.paste_and_save)

    def _init_queue_data(self) -> None:
        self.queue_list.clear()
        for idx, item in enumerate(self.items):
            # Discover PDF and answer key for item
            sources = discover_sources(item.workspace)
            pdf = preferred_pdf(item.workspace.source_pdf or sources.pdf, item.workspace.path)
            item.pdf_path = pdf
            item.answer_key_path = sources.answer_keys[0] if sources.answer_keys else None
            item.is_digital = classify_pdf(pdf, workspace=item.workspace.path) if (pdf and pdf.is_file()) else False

            # Check if questions.md already exists
            q_file = item.workspace.path / "questions.md"
            if q_file.exists():
                try:
                    qs = load_questions(q_file)
                    item.questions_count = len(qs)
                    item.status = "saved"
                except Exception:
                    pass

            list_item = QListWidgetItem()
            self._update_list_item_display(list_item, item, idx)
            self.queue_list.addItem(list_item)

    def _update_list_item_display(self, list_item: QListWidgetItem, item: BatchQueueItem, idx: int) -> None:
        status_icons = {
            "pending": "⏳",
            "in_progress": "🟡",
            "saved": "✅",
            "skipped": "⏭️",
        }
        icon = status_icons.get(item.status, "⏳")
        count_str = f" ({item.questions_count} q's)" if item.status == "saved" and item.questions_count > 0 else ""
        list_item.setText(f"{icon} {idx + 1}. {item.workspace.name}{count_str}")
        list_item.setData(Qt.ItemDataRole.UserRole, idx)

    def _update_progress(self) -> None:
        completed = sum(1 for it in self.items if it.status in {"saved", "skipped"})
        saved_count = sum(1 for it in self.items if it.status == "saved")
        self.progress_bar.setValue(completed)
        self.progress_label.setText(f"Exam {self.current_index + 1} of {len(self.items)} ({saved_count} saved)")

    def _on_queue_row_changed(self, row: int) -> None:
        if 0 <= row < len(self.items) and row != self.current_index:
            self._select_item(row)

    def _select_item(self, index: int) -> None:
        if index < 0 or index >= len(self.items):
            return

        self.current_index = index
        item = self.items[index]
        if item.status == "pending":
            item.status = "in_progress"

        # Update queue list row without recursive signals
        self.queue_list.blockSignals(True)
        self.queue_list.setCurrentRow(index)
        for i, itm in enumerate(self.items):
            list_item = self.queue_list.item(i)
            if list_item:
                self._update_list_item_display(list_item, itm, i)
        self.queue_list.blockSignals(False)

        # Update watcher path
        self._update_watcher_path(item.workspace.path)

        # Update workspace header
        type_str = "📄 Digital PDF" if item.is_digital else "📷 Scanned PDF"
        ans_str = f" • Answer Key: {item.answer_key_path.name}" if item.answer_key_path else " • No Answer Key"
        self.exam_title_banner.setText(f"Active Exam: {item.workspace.name} ({type_str}{ans_str})")
        self.exam_path_label.setText(str(item.workspace.path))

        # Update single PDF widget
        self.draggable_pdf.set_pdf(item.pdf_path)

        # Check existing questions.md content to pre-fill or clear
        q_file = item.workspace.path / "questions.md"
        if q_file.is_file() and q_file.stat().st_size > 0:
            try:
                self.response_edit.setPlainText(q_file.read_text(encoding="utf-8"))
            except Exception:
                self.response_edit.clear()
        else:
            self.response_edit.clear()

        # Generate and auto-copy prompt
        self._prepare_and_copy_prompt(show_badge=True)
        self._update_progress()
        self.status_msg_label.setText(f"Ready for exam {index + 1}: {item.workspace.name}")

    def _update_watcher_path(self, target_dir: Path) -> None:
        paths = self.watcher.directories() + self.watcher.files()
        if paths:
            self.watcher.removePaths(paths)
        if target_dir.is_dir():
            self.watcher.addPath(str(target_dir))
            q_file = target_dir / "questions.md"
            if q_file.exists():
                self.watcher.addPath(str(q_file))

    def _on_dir_changed(self, path_str: str) -> None:
        target_dir = Path(path_str)
        q_file = target_dir / "questions.md"
        if q_file.is_file() and str(q_file) not in self.watcher.files():
            self.watcher.addPath(str(q_file))
            self._load_from_detected_file(q_file)

    def _on_file_changed(self, path_str: str) -> None:
        q_file = Path(path_str)
        if q_file.name.lower() == "questions.md" and q_file.is_file():
            self._load_from_detected_file(q_file)

    def _load_from_detected_file(self, q_file: Path) -> None:
        try:
            content = q_file.read_text(encoding="utf-8")
            if content.strip() and content.strip() != self.response_edit.toPlainText().strip():
                self.response_edit.setPlainText(content)
                self.status_msg_label.setText(f"📁 Detected updated questions.md in {q_file.parent.name}!")
                self.prompt_status_badge.setText("📁 Loaded questions.md from folder")
        except Exception as exc:
            LOGGER.warning("Could not auto-read questions.md: %s", exc)

    def _prepare_and_copy_prompt(self, show_badge: bool = True) -> None:
        item = self.items[self.current_index]
        try:
            # Generate the prompt file for web AI
            prompt_file = generate_workspace_prompt(
                self.config,
                item.workspace.path,
                kind="web",
            )
            # If enhanced prompt is selected and enhanced file exists, use it
            enhanced_file = item.workspace.path / "prompt_web_ai_enhanced.txt"
            target_file = enhanced_file if (self.enhanced_prompt_check.isChecked() and enhanced_file.is_file()) else prompt_file

            prompt_text = target_file.read_text(encoding="utf-8")
            QApplication.clipboard().setText(prompt_text)
            if show_badge:
                self.prompt_status_badge.setText("✅ Prompt copied to clipboard!")
                self.prompt_status_badge.setStyleSheet("color: #16a34a; font-weight: 600; font-size: 12px;")
        except Exception as exc:
            LOGGER.warning("Could not generate/copy prompt: %s", exc)
            self.prompt_status_badge.setText(f"⚠️ Prompt generation error: {exc}")
            self.prompt_status_badge.setStyleSheet("color: #dc2626; font-weight: 500; font-size: 11px;")

    def _copy_prompt_to_clipboard(self) -> None:
        self._prepare_and_copy_prompt(show_badge=True)
        self.status_msg_label.setText("Prompt re-copied to clipboard.")

    def _open_web_chat(self) -> None:
        prov = self.provider_combo.currentData()
        if prov and prov.url:
            self._prepare_and_copy_prompt(show_badge=True)
            webbrowser.open(prov.url)
            self.status_msg_label.setText(f"Opened {prov.label} in browser. Paste the prompt (Ctrl+V) and upload 1 PDF.")

    def _reveal_current_pdf(self) -> None:
        item = self.items[self.current_index]
        if item.pdf_path and item.pdf_path.is_file():
            reveal_in_file_manager(item.pdf_path)
            self.status_msg_label.setText(f"Revealed {item.pdf_path.name} in file manager.")
        else:
            reveal_in_file_manager(item.workspace.path)

    def _copy_current_pdf_file(self) -> None:
        item = self.items[self.current_index]
        if item.pdf_path and item.pdf_path.is_file():
            if copy_file_to_clipboard(item.pdf_path):
                self.status_msg_label.setText(f"Copied {item.pdf_path.name} file to clipboard.")
                QMessageBox.information(self, "PDF Copied", f"Copied '{item.pdf_path.name}' to clipboard!\nYou can paste it directly into file dialogs or chats.")
        else:
            QMessageBox.warning(self, "No PDF", "No PDF found in this exam folder.")

    def _copy_current_pdf_path(self) -> None:
        item = self.items[self.current_index]
        if item.pdf_path and item.pdf_path.is_file():
            QApplication.clipboard().setText(str(item.pdf_path.resolve()))
            self.status_msg_label.setText(f"Copied path: {item.pdf_path.name}")
        else:
            QMessageBox.warning(self, "No PDF", "No PDF found in this exam folder.")

    def _clean_current_pdf(self) -> None:
        item = self.items[self.current_index]
        if not item.pdf_path or not item.pdf_path.is_file():
            QMessageBox.warning(self, "No PDF", "No valid PDF file to clean.")
            return

        source_pdf = item.pdf_path
        clean_name = f"{source_pdf.stem}_clean.pdf" if not source_pdf.stem.endswith("_clean") else source_pdf.name
        clean_path = item.workspace.path / clean_name
        discard_spec = self.config.default_discard_pages or "std"

        try:
            total, kept = clean_pdf(source_pdf, clean_path, discard_spec)
            item.pdf_path = clean_path
            self.draggable_pdf.set_pdf(clean_path)
            self.status_msg_label.setText(f"Created clean PDF: kept {kept} of {total} pages.")
            QMessageBox.information(
                self,
                "Clean PDF Created",
                f"Successfully created clean PDF without cover/blank pages ({kept}/{total} pages kept):\n\n{clean_path.name}\n\nIt is now set as the active PDF for uploading.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Clean PDF Failed", f"Could not clean PDF: {exc}")

    # Drag and Drop support for files (.md / .txt) onto dialog
    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith((".md", ".txt", ".json")):
                    event.acceptProposedAction()
                    return
        super().dragEnterEvent(event)

    def dropEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = Path(url.toLocalFile())
                if file_path.is_file() and file_path.suffix.lower() in {".md", ".txt", ".json"}:
                    try:
                        content = file_path.read_text(encoding="utf-8")
                        self.response_edit.setPlainText(content)
                        self.status_msg_label.setText(f"Loaded content from dropped file: {file_path.name}")
                        event.acceptProposedAction()
                        return
                    except Exception as exc:
                        QMessageBox.warning(self, "Drop Error", f"Could not read dropped file: {exc}")
        super().dropEvent(event)

    def paste_and_save(self) -> None:
        """Paste from clipboard if editor is empty (or use existing editor text), then save and advance."""
        current_text = self.response_edit.toPlainText().strip()
        if not current_text:
            clipboard_text = QApplication.clipboard().text().strip()
            if clipboard_text:
                self.response_edit.setPlainText(clipboard_text)
                current_text = clipboard_text
            else:
                QMessageBox.warning(self, "No Response", "Please paste or enter the Web AI markdown response before saving.")
                return

        self._process_and_save_current_response(current_text)

    def save_and_next(self) -> None:
        current_text = self.response_edit.toPlainText().strip()
        if not current_text:
            QMessageBox.warning(self, "No Response", "Editor is empty. Paste the markdown response first.")
            return
        self._process_and_save_current_response(current_text)

    def _process_and_save_current_response(self, raw_text: str) -> None:
        item = self.items[self.current_index]
        cleaned_markdown = extract_markdown_from_response(raw_text)

        # Write to questions.md
        q_file = item.workspace.path / "questions.md"
        try:
            q_file.write_text(cleaned_markdown, encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Save Error", f"Could not write questions.md: {exc}")
            return

        # Auto-merge answer key if available
        runner = PipelineRunner(self.config.scripts_root)
        try:
            sources = discover_sources(item.workspace)
            selected_answer_key = sources.answer_keys[0] if sources.answer_keys else None
            if selected_answer_key:
                answers_json = item.workspace.path / "answers.json"
                runner.extract_answers(selected_answer_key, self.config.default_form, answers_json)
                runner.merge_answers(item.workspace.path)
            elif (item.workspace.path / "answers.json").is_file() or (item.workspace.path / "answers.md").is_file():
                runner.merge_answers(item.workspace.path)
        except Exception as exc:
            LOGGER.warning("Answer key merge notice for %s: %s", item.workspace.name, exc)

        # Validate questions
        try:
            questions = load_questions(q_file)
            item.questions_count = len(questions)
            item.status = "saved"
            item.error = None
        except Exception as exc:
            item.status = "saved"
            item.error = str(exc)
            # Count questions using basic parser if validation had minor warning
            try:
                item.questions_count = len(load_markdown_questions(q_file))
            except Exception:
                item.questions_count = 0

        # Update queue list display
        list_item = self.queue_list.item(self.current_index)
        if list_item:
            self._update_list_item_display(list_item, item, self.current_index)

        self._update_progress()
        self.status_msg_label.setText(f"✅ Saved {item.questions_count} question(s) in {item.workspace.name}.")

        # Auto-advance to next item
        next_idx = self._find_next_pending_index()
        if next_idx is not None:
            self._select_item(next_idx)
        else:
            self._show_all_done_dialog()

    def _find_next_pending_index(self) -> int | None:
        # First check indices after current
        for i in range(self.current_index + 1, len(self.items)):
            if self.items[i].status in {"pending", "in_progress"}:
                return i
        # Then check wrap-around
        for i in range(0, self.current_index):
            if self.items[i].status in {"pending", "in_progress"}:
                return i
        return None

    def skip_current(self) -> None:
        item = self.items[self.current_index]
        if item.status != "saved":
            item.status = "skipped"
        list_item = self.queue_list.item(self.current_index)
        if list_item:
            self._update_list_item_display(list_item, item, self.current_index)
        self._update_progress()

        next_idx = self._find_next_pending_index()
        if next_idx is not None:
            self._select_item(next_idx)
        elif self.current_index + 1 < len(self.items):
            self._select_item(self.current_index + 1)
        else:
            self._show_all_done_dialog()

    def prev_exam(self) -> None:
        if self.current_index > 0:
            self._select_item(self.current_index - 1)

    def _show_all_done_dialog(self) -> None:
        saved_items = [it for it in self.items if it.status == "saved"]
        skipped_items = [it for it in self.items if it.status == "skipped"]

        box = QMessageBox(self)
        box.setWindowTitle("Web AI Batch Complete")
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(
            f"<h3>Web AI Batch Finished!</h3>"
            f"<p><b>{len(saved_items)}</b> exam(s) saved, <b>{len(skipped_items)}</b> skipped out of <b>{len(self.items)}</b> total.</p>"
            f"<p>Would you like to build standalone HTML quizzes for the saved exams now?</p>"
        )
        build_btn = box.addButton("⚡ Build HTML Quizzes", QMessageBox.ButtonRole.AcceptRole)
        review_btn = box.addButton("Review Quizzes", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Close)
        box.exec()

        if box.clickedButton() == build_btn:
            self._build_html_quizzes(saved_items)
            self.accept()
        elif box.clickedButton() == review_btn:
            self.accept()

    def _build_html_quizzes(self, items: list[BatchQueueItem]) -> None:
        built = 0
        errors = []
        for it in items:
            try:
                build_standalone_quiz(it.workspace.path, self.config.scripts_root)
                built += 1
            except Exception as exc:
                errors.append(f"{it.workspace.name}: {exc}")

        if errors:
            QMessageBox.warning(self, "Quiz Build Warning", f"Built {built} quiz(zes), but encountered errors:\n" + "\n".join(errors))
        else:
            QMessageBox.information(self, "Quizzes Built", f"Successfully built {built} standalone HTML quiz(zes)!")

    def finish_batch(self) -> None:
        self.accept()

