"""Interactive Quiz Builder — Main GUI Application Window."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import sys
from typing import Any

from PySide6.QtCore import QPoint, QSettings, QThreadPool, Qt, QTimer
from PySide6.QtGui import QAction, QCursor, QGuiApplication, QIcon, QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..batch import discover_batch
from ..config import Config
from ..models import Workspace
from ..validation import ValidationError, load_questions
from ..workspace import discover_sources
from .dialogs import WelcomeDialog
from .styles import DARK_STYLESHEET, LITE_STYLESHEET
from .tabs import ExportTabWidget, ExtractTabWidget, ReviewTabWidget
from .workers import Worker

LOGGER = logging.getLogger(__name__)


class MainWindow(QWidget):
    """Main window coordinating exam extraction, review, and export tabs."""

    def __init__(self, config: Config | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.config = config or Config.load()
        self.settings = QSettings("InteractiveQuizBuilder", "QuizBuilder")
        self.thread_pool = QThreadPool.globalInstance()
        self._active_workers: set[Worker] = set()
        self.state: dict[str, Any] = {
            "root": None,
            "workspace": None,
            "questions": [],
            "index": -1,
            "dirty": False,
            "loading": False,
        }
        self.setWindowTitle("Interactive Quiz Builder")
        self.setMinimumSize(780, 520)
        self.resize(1120, 780)
        self._setup_window_icon()
        self.dark_mode = self.settings.value("dark_mode", False, type=bool)
        self.setStyleSheet(DARK_STYLESHEET if self.dark_mode else LITE_STYLESHEET)
        self._build_ui()
        self._show_welcome_if_needed()
        self._connect_signals()
        self._restore_session()

    def _setup_window_icon(self) -> None:
        """Configure desktop taskbar and window icons."""
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("elonuziel.interactivequizbuilder.gui")
            except Exception:
                pass

        icon_paths = [
            Path(__file__).resolve().parents[3] / "assets" / "app_icon.png",
            Path(__file__).resolve().parents[1] / "assets" / "app_icon.png",
            Path(__file__).resolve().parent / "assets" / "app_icon.png",
            Path(__file__).resolve().parents[3] / "favicon.svg",
            Path(getattr(sys, "_MEIPASS", "")) / "assets" / "app_icon.png" if hasattr(sys, "_MEIPASS") else None,
        ]
        for p in icon_paths:
            if p and p.is_file():
                icon = QIcon(str(p))
                self.setWindowIcon(icon)
                app = QApplication.instance()
                if app:
                    app.setWindowIcon(icon)
                break

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 12, 14, 12)
        root_layout.setSpacing(10)

        # Top Bar
        top_bar = QFrame()
        top_bar.setObjectName("topBar")
        top_layout = QHBoxLayout(top_bar)
        self.root_label = QLabel("Exam folder: (not selected)")
        self.root_label.setToolTip("Choose the parent folder containing your exam folders.")
        self.choose_root_btn = QPushButton("Choose exam folder…")
        self.choose_root_btn.setToolTip("Select the parent folder that contains your exam projects.")
        self.recent_btn = QPushButton("▼ Recent")
        self.recent_btn.setToolTip("Open a recently used exam folder.")
        self.recent_btn.setMaximumWidth(82)
        self.refresh_root_btn = QPushButton("⟳ Reload")
        self.refresh_root_btn.setToolTip("Scan the selected folder again for exam projects.")
        self.theme_button = QPushButton("☀️ Light" if self.dark_mode else "🌙 Dark")
        self.theme_button.setToolTip("Toggle between dark and light theme.")
        self.theme_button.setMaximumWidth(88)
        top_layout.addWidget(self.root_label, 1)
        top_layout.addWidget(self.choose_root_btn)
        top_layout.addWidget(self.recent_btn)
        top_layout.addWidget(self.refresh_root_btn)
        top_layout.addWidget(self.theme_button)
        root_layout.addWidget(top_bar)

        # Tabs
        self.tabs = QTabWidget()
        self.extract_tab = ExtractTabWidget(self)
        self.review_tab = ReviewTabWidget(self)
        self.export_tab = ExportTabWidget(self)
        self.tabs.addTab(self.extract_tab, "Choose & extract")
        self.tabs.addTab(self.review_tab, "Review questions")
        self.tabs.addTab(self.export_tab, "Play or export")
        root_layout.addWidget(self.tabs, 1)

        # Status Bar
        status_bar = QFrame()
        status_bar.setObjectName("statusBar")
        status_layout = QHBoxLayout(status_bar)
        self.status_label = QLabel("Welcome! Choose an exam folder to begin. Each exam folder should contain a PDF and questions.md.")
        self.status_label.setWordWrap(True)
        self.status_progress = QProgressBar()
        self.status_progress.setRange(0, 0)
        self.status_progress.setMaximumWidth(130)
        self.status_progress.setMaximumHeight(14)
        self.status_progress.setTextVisible(False)
        self.status_progress.setVisible(False)
        status_layout.addWidget(self.status_label, 1)
        status_layout.addWidget(self.status_progress)
        root_layout.addWidget(status_bar)

    def _connect_signals(self) -> None:
        self.choose_root_btn.clicked.connect(self.choose_folder)
        self.refresh_root_btn.clicked.connect(self.reload_folder)
        self.recent_btn.clicked.connect(self._show_recent_menu)
        self.theme_button.clicked.connect(self.toggle_theme)
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(lambda: (self.exam_search.setFocus(), self.exam_search.selectAll()))

    # ==================== Delegated Tab Attributes ====================
    # Tab 1: Extract Tab Properties
    @property
    def exam_group(self): return self.extract_tab.exam_group
    @property
    def exam_search(self): return self.extract_tab.exam_search
    @property
    def exam_list(self): return self.extract_tab.exam_list
    @property
    def exam_select_all_btn(self): return self.extract_tab.exam_select_all_btn
    @property
    def exam_deselect_all_btn(self): return self.extract_tab.exam_deselect_all_btn
    @property
    def batch_button(self): return self.extract_tab.batch_button
    @property
    def super_batch_button(self): return self.extract_tab.super_batch_button
    @property
    def super_batch_info_btn(self): return self.extract_tab.super_batch_info_btn
    @property
    def web_batch_button(self): return self.extract_tab.web_batch_button
    @property
    def extract_group(self): return self.extract_tab.extract_group
    @property
    def current_exam_title(self): return self.extract_tab.current_exam_title
    @property
    def pdf_combo(self): return self.extract_tab.pdf_combo
    @property
    def browse_pdf_button(self): return self.extract_tab.browse_pdf_button
    @property
    def detection_title(self): return self.extract_tab.detection_title
    @property
    def detection_description(self): return self.extract_tab.detection_description
    @property
    def extract_button(self): return self.extract_tab.extract_button
    @property
    def ai_hint(self): return self.extract_tab.ai_hint
    @property
    def ai_provider_combo(self): return self.extract_tab.ai_provider_combo
    @property
    def launch_ai_button(self): return self.extract_tab.launch_ai_button
    @property
    def ai_info_btn(self): return self.extract_tab.ai_info_btn
    @property
    def answer_combo(self): return self.extract_tab.answer_combo
    @property
    def browse_answer_button(self): return self.extract_tab.browse_answer_button
    @property
    def form_edit(self): return self.extract_tab.form_edit
    @property
    def clean_group(self): return self.extract_tab.clean_group
    @property
    def clean_hint(self): return self.extract_tab.clean_hint
    @property
    def preset_std_button(self): return self.extract_tab.preset_std_button
    @property
    def preset_even_button(self): return self.extract_tab.preset_even_button
    @property
    def preset_odd_button(self): return self.extract_tab.preset_odd_button
    @property
    def preset_clear_button(self): return self.extract_tab.preset_clear_button
    @property
    def discard_range_edit(self): return self.extract_tab.discard_range_edit
    @property
    def clean_pdf_button(self): return self.extract_tab.clean_pdf_button
    @property
    def clean_summary_label(self): return self.extract_tab.clean_summary_label
    @property
    def preview(self): return self.extract_tab.preview
    @property
    def preview_button(self): return self.extract_tab.preview_button
    @property
    def next_review_button(self): return self.extract_tab.next_review_button

    # Tab 2: Review Tab Properties
    @property
    def question_status(self): return self.review_tab.question_status
    @property
    def question_filter_edit(self): return self.review_tab.question_filter_edit
    @property
    def filter_incomplete_checkbox(self): return self.review_tab.filter_incomplete_checkbox
    @property
    def question_list(self): return self.review_tab.question_list
    @property
    def move_up_button(self): return self.review_tab.move_up_button
    @property
    def move_down_button(self): return self.review_tab.move_down_button
    @property
    def duplicate_button(self): return self.review_tab.duplicate_button
    @property
    def add_question_button(self): return self.review_tab.add_question_button
    @property
    def delete_question_button(self): return self.review_tab.delete_question_button
    @property
    def matrix_button(self): return self.review_tab.matrix_button
    @property
    def open_questions_button(self): return self.review_tab.open_questions_button
    @property
    def question_editor(self): return self.review_tab.question_editor
    @property
    def save_button(self): return self.review_tab.save_button
    @property
    def save_as_button(self): return self.review_tab.save_as_button
    @property
    def help_button(self): return self.review_tab.help_button
    @property
    def next_export_button(self): return self.review_tab.next_export_button

    # Tab 3: Export Tab Properties
    @property
    def play_list(self): return self.export_tab.play_list
    @property
    def select_all_button(self): return self.export_tab.select_all_button
    @property
    def clear_all_button(self): return self.export_tab.clear_all_button
    @property
    def mix_checkbox(self): return self.export_tab.mix_checkbox
    @property
    def summary(self): return self.export_tab.summary
    @property
    def play_button(self): return self.export_tab.play_button
    @property
    def export_button(self): return self.export_tab.export_button
    @property
    def open_runs_button(self): return self.export_tab.open_runs_button

    # ==================== Delegated Tab Methods ====================
    def select_all_extract_exams(self) -> None: self.extract_tab.select_all_extract_exams()
    def deselect_all_extract_exams(self) -> None: self.extract_tab.deselect_all_extract_exams()
    def invert_extract_exams_selection(self) -> None: self.extract_tab.invert_extract_exams_selection()
    def filter_exams(self, query: str) -> None: self.extract_tab.filter_exams(query)
    def choose_custom_exam_file(self) -> None: self.extract_tab.choose_custom_exam_file()
    def choose_custom_answer_key(self) -> None: self.extract_tab.choose_custom_answer_key()
    def preview_first_page(self) -> None: self.extract_tab.preview_first_page()
    def set_discard_preset(self, rule: str) -> None: self.extract_tab.set_discard_preset(rule)
    def update_clean_summary(self) -> None: self.extract_tab.update_clean_summary()
    def run_clean_pdf(self) -> None: self.extract_tab.run_clean_pdf()
    def reload_ai_providers(self) -> None: self.extract_tab.reload_ai_providers()
    def show_cli_agent_guide(self) -> None: self.extract_tab.show_cli_agent_guide()
    def process_selected_exam(self) -> None: self.extract_tab.process_selected_exam()
    def process_batch_checked(self) -> None: self.extract_tab.process_batch_checked()
    def launch_ai(self) -> None: self.extract_tab.launch_ai()
    def open_super_batch(self) -> None: self.extract_tab.open_super_batch()
    def open_web_batch_wizard(self) -> None: self.extract_tab.open_web_batch_wizard()

    def refresh_question_list(self) -> None: self.review_tab.refresh_question_list()
    def show_question(self, row: int) -> None: self.review_tab.show_question(row)
    def save_active_question(self) -> None: self.review_tab.save_active_question()
    def mark_dirty(self) -> None: self.review_tab.mark_dirty()
    def add_question(self) -> None: self.review_tab.add_question()
    def duplicate_question(self) -> None: self.review_tab.duplicate_question()
    def delete_question(self) -> None: self.review_tab.delete_question()
    def move_question_up(self) -> None: self.review_tab.move_question_up()
    def move_question_down(self) -> None: self.review_tab.move_question_down()
    def open_answer_matrix(self) -> None: self.review_tab.open_answer_matrix()
    def import_custom_questions_file(self) -> None: self.review_tab.import_custom_questions_file()
    def save_questions_as(self) -> None: self.review_tab.save_questions_as()
    def save_test(self) -> None: self.review_tab.save_test()
    def show_markdown_help(self) -> None: self.review_tab.show_markdown_help()

    def select_all_play_exams(self) -> None: self.export_tab.select_all_play_exams()
    def clear_all_play_exams(self) -> None: self.export_tab.clear_all_play_exams()
    def invert_play_exams_selection(self) -> None: self.export_tab.invert_play_exams_selection()
    def select_all_exams(self) -> None: self.export_tab.select_all_exams()
    def clear_all_exams(self) -> None: self.export_tab.clear_all_exams()
    def checked_play_workspaces(self) -> list: return self.export_tab.checked_play_workspaces()
    def update_summary(self) -> None: self.export_tab.update_summary()
    def prepare_and_play_quiz(self) -> None: self.export_tab.prepare_and_play_quiz()
    def export_quiz(self) -> None: self.export_tab.export_quiz()
    def open_image_cropper(self) -> None: self.export_tab.open_image_cropper()
    def open_runs_folder(self) -> None: self.export_tab.open_runs_folder()

    # ==================== MainWindow Core Functions ====================
    def start_worker(self, worker: Worker) -> None:
        self._active_workers.add(worker)
        self._set_worker_busy(True)

        def _remove(result_or_err=None) -> None:
            self._active_workers.discard(worker)
            self._set_worker_busy(bool(self._active_workers))

        worker.signals.finished.connect(_remove)
        worker.signals.failed.connect(_remove)
        self.thread_pool.start(worker)

    def toggle_theme(self) -> None:
        self.dark_mode = not self.dark_mode
        self.settings.setValue("dark_mode", self.dark_mode)
        self.setStyleSheet(DARK_STYLESHEET if self.dark_mode else LITE_STYLESHEET)
        self.theme_button.setText("☀️ Light" if self.dark_mode else "🌙 Dark")

    def _set_status(self, message: str, status_type: str = "info") -> None:
        self.status_label.setText(message)
        if status_type == "error":
            self.status_label.setStyleSheet("color: var(--danger-color);")
        elif status_type == "success":
            self.status_label.setStyleSheet("color: var(--success-color);")
        elif status_type == "busy":
            self.status_label.setStyleSheet("color: var(--accent-color);")
        else:
            self.status_label.setStyleSheet("")

    def _set_worker_busy(self, busy: bool) -> None:
        self.status_progress.setVisible(busy)
        cursor = Qt.CursorShape.WaitCursor if busy else Qt.CursorShape.ArrowCursor
        QGuiApplication.setOverrideCursor(cursor) if busy else QGuiApplication.restoreOverrideCursor()

    def _update_tab_labels(self) -> None:
        dirty_badge = " *" if self.state["dirty"] else ""
        self.tabs.setTabText(1, f"Review questions{dirty_badge}")
        selected_count = len(self.export_tab.checked_play_workspaces())
        self.tabs.setTabText(2, f"Play or export ({selected_count})")

    def _recent_folders(self) -> list[str]:
        raw = self.settings.value("recent_folders", [])
        if isinstance(raw, str):
            return [raw] if raw else []
        return list(raw) if raw else []

    def _add_recent_folder(self, folder_path: str) -> None:
        recents = [f for f in self._recent_folders() if f != folder_path]
        recents.insert(0, folder_path)
        self.settings.setValue("recent_folders", recents[:8])

    def _show_recent_menu(self) -> None:
        menu = QMenu(self)
        recents = self._recent_folders()
        if not recents:
            empty_action = menu.addAction("No recent folders")
            empty_action.setEnabled(False)
        else:
            for path_str in recents:
                action = menu.addAction(path_str)
                action.triggered.connect(lambda checked=False, p=path_str: self._open_recent(p))
            menu.addSeparator()
            clear_action = menu.addAction("Clear recent folders")
            clear_action.triggered.connect(lambda: self.settings.setValue("recent_folders", []))
        menu.exec(self.recent_btn.mapToGlobal(QPoint(0, self.recent_btn.height())))

    def _open_recent(self, path_str: str) -> None:
        target = Path(path_str)
        if not target.is_dir():
            QMessageBox.warning(self, "Folder not found", f"The folder no longer exists:\n{path_str}")
            recents = [f for f in self._recent_folders() if f != path_str]
            self.settings.setValue("recent_folders", recents)
            return
        if not self.confirm_discard_changes():
            return
        self.state["root"] = target
        self.settings.setValue("last_root", str(target))
        self._add_recent_folder(str(target))
        self.root_label.setText(f"Exam folder: {target}")
        self.populate_tests()
        self._set_status(f"Loaded exam folder: {target}", "success")

    def populate_tests(self) -> None:
        if not self.state["root"]:
            return
        try:
            candidates = discover_batch(self.state["root"])
        except (FileNotFoundError, OSError) as exc:
            self.status_label.setText(str(exc))
            return
        self.state["batch_candidates"] = candidates
        self.exam_list.clear()
        self.play_list.clear()
        for candidate in candidates:
            label = candidate.workspace.name
            if candidate.issues:
                label += f" ({'; '.join(candidate.issues)})"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, candidate.workspace)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.exam_list.addItem(item)

            play_item = QListWidgetItem(label)
            play_item.setData(Qt.ItemDataRole.UserRole, candidate.workspace)
            play_item.setFlags(play_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            play_item.setCheckState(Qt.CheckState.Checked if candidate.ready_to_run else Qt.CheckState.Unchecked)
            self.play_list.addItem(play_item)

        self.root_label.setText(f"Exam folder: {self.state['root']}")
        if self.exam_list.count() > 0:
            self.exam_list.setCurrentRow(0)
        self.update_summary()

    def reload_folder(self) -> None:
        if not self.state["root"]:
            QMessageBox.warning(self, "No exam folder", "Choose an exam folder first.")
            return
        if not self.confirm_discard_changes():
            return
        self.populate_tests()
        self._set_status(f"Reloaded exam folder: {self.state['root']}", "success")

    def choose_folder(self) -> None:
        if not self.confirm_discard_changes():
            return
        folder = QFileDialog.getExistingDirectory(
            self,
            "Choose Exam Folder (parent directory of exam subfolders)",
            str(self.state["root"]) if self.state["root"] else str(Path.home()),
        )
        if folder:
            self.state["root"] = Path(folder)
            self.settings.setValue("last_root", folder)
            self._add_recent_folder(folder)
            self.root_label.setText(f"Exam folder: {self.state['root']}")
            self.populate_tests()
            self._set_status(f"Selected exam folder: {self.state['root']}", "success")

    def select_exam(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        if not current:
            return
        workspace = current.data(Qt.ItemDataRole.UserRole)
        if workspace:
            if not self.confirm_discard_changes():
                if previous:
                    self.exam_list.blockSignals(True)
                    self.exam_list.setCurrentItem(previous)
                    self.exam_list.blockSignals(False)
                return
            self.load_workspace(workspace)

    def load_workspace(self, workspace: Workspace) -> None:
        if workspace != self.state["workspace"] and not self.confirm_discard_changes():
            return
        self.state["workspace"] = workspace
        self.state["questions"] = []
        self.state["index"] = -1
        self.state["loading"] = True
        self.settings.setValue("last_workspace", workspace.name)
        self.current_exam_title.setText(f"Exam: {workspace.name}")

        self.pdf_combo.blockSignals(True)
        self.pdf_combo.clear()
        sources = discover_sources(workspace)
        if getattr(workspace, "source_pdf", None):
            self.pdf_combo.addItem(workspace.source_pdf.name, workspace.source_pdf)
        elif sources.pdf:
            self.pdf_combo.addItem(sources.pdf.name, sources.pdf)
        for doc in sorted(list(workspace.path.glob("*.pdf")) + list(workspace.path.glob("*.docx")), key=lambda item: item.name.casefold()):
            if self.pdf_combo.findData(doc) < 0:
                self.pdf_combo.addItem(doc.name, doc)
        if not self.pdf_combo.count():
            self.pdf_combo.addItem("No exam file selected", None)
        self.pdf_combo.blockSignals(False)

        self.answer_combo.clear()
        self.answer_combo.addItem("No answer key", None)
        for answer in sources.answer_keys:
            self.answer_combo.addItem(answer.name, answer)
        for ans in sorted(list(workspace.path.glob("*.csv")) + list(workspace.path.glob("*.xlsx")) + list(workspace.path.glob("*.xls")), key=lambda item: item.name.casefold()):
            if self.answer_combo.findData(ans) < 0:
                self.answer_combo.addItem(ans.name, ans)

        self.preview.setText("No exam preview loaded.")

        self.state["loading"] = False
        try:
            self.state["questions"] = load_questions(workspace.questions_path)
            self.state["dirty"] = False
            self._set_status(f"Loaded {len(self.state['questions'])} question(s) from {workspace.name}/questions.md", "success")
        except (OSError, ValidationError):
            self.state["questions"] = []
            self.state["dirty"] = False
            self._set_status(f"{workspace.name}: No questions.md yet. Extract questions or write them in the review tab.", "info")

        self.state["index"] = 0 if self.state["questions"] else -1
        self.refresh_question_list()
        self._update_tab_labels()
        self.update_summary()
        self.extract_tab._on_pdf_selection_changed()

    def confirm_discard_changes(self) -> bool:
        if not self.state["dirty"]:
            return True
        self.save_active_question()
        choice = QMessageBox.question(
            self,
            "Unsaved changes",
            "You have unsaved changes in questions.md. Save them before continuing?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if choice == QMessageBox.StandardButton.Save:
            self.save_test()
            return True
        if choice == QMessageBox.StandardButton.Discard:
            self.state["dirty"] = False
            self._update_tab_labels()
            return True
        return False

    def _show_welcome_if_needed(self) -> None:
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen" or "pytest" in sys.modules:
            return
        if not self.settings.value("welcome_seen", False, type=bool):
            dialog = WelcomeDialog(self)
            dialog.exec()
            self.settings.setValue("welcome_seen", True)

    def _restore_session(self) -> None:
        saved = self.settings.value("last_exam_folder", "") or self.settings.value("last_root", "")
        configured = self.config.workspace_root
        self.state["root"] = configured if configured.is_dir() else Path(saved) if (saved and Path(saved).is_dir()) else configured
        if self.state["root"] and self.state["root"].is_dir():
            self.root_label.setText(f"Exam folder: {self.state['root']}")
            self.populate_tests()
            last_workspace = self.settings.value("last_workspace")
            if last_workspace:
                for index in range(self.exam_list.count()):
                    item = self.exam_list.item(index)
                    workspace = item.data(Qt.ItemDataRole.UserRole)
                    if workspace and workspace.name == last_workspace:
                        self.exam_list.setCurrentItem(item)
                        break

    def closeEvent(self, event) -> None:
        if self.confirm_discard_changes():
            event.accept()
        else:
            event.ignore()


def main() -> int:
    application = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    return application.exec()


QuizBuilderWindow = MainWindow
