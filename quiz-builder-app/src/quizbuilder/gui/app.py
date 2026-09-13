"""Interactive Quiz Builder — Main GUI Application Window."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import sys
from typing import Any

from PySide6.QtCore import QPoint, QSettings, QThreadPool, Qt, QTimer
from PySide6.QtGui import QAction, QBrush, QColor, QCursor, QGuiApplication, QIcon, QImage, QKeySequence, QPixmap, QShortcut
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
        top_layout.setSpacing(6)

        # Folder icon + compact path label
        folder_icon = QLabel("📂")
        folder_icon.setFixedWidth(22)
        self.root_label = QLabel("No exam folder selected")
        self.root_label.setObjectName("pathLabel")
        self.root_label.setToolTip("Choose the parent folder containing your exam folders.")

        # Folder action buttons (clustered)
        self.choose_root_btn = QPushButton("Choose folder…")
        self.choose_root_btn.setToolTip("Select the parent folder that contains your exam projects.")
        self.recent_btn = QPushButton("▼ Recent")
        self.recent_btn.setToolTip("Open a recently used exam folder.")
        self.recent_btn.setObjectName("secondary")
        self.recent_btn.setMaximumWidth(80)
        self.refresh_root_btn = QPushButton("⟳")
        self.refresh_root_btn.setObjectName("secondary")
        self.refresh_root_btn.setToolTip("Reload: scan the selected folder again for exam projects.")
        self.refresh_root_btn.setMaximumWidth(34)
        self.refresh_root_btn.setMinimumWidth(34)

        # Visual separator before theme button
        v_sep = QFrame()
        v_sep.setFrameShape(QFrame.Shape.VLine)
        v_sep.setFixedWidth(1)

        self.theme_button = QPushButton("☀️ Light" if self.dark_mode else "🌙 Dark")
        self.theme_button.setObjectName("secondary")
        self.theme_button.setToolTip("Toggle between dark and light theme.")
        self.theme_button.setMaximumWidth(88)

        top_layout.addWidget(folder_icon)
        top_layout.addWidget(self.root_label, 1)
        top_layout.addWidget(self.choose_root_btn)
        top_layout.addWidget(self.recent_btn)
        top_layout.addWidget(self.refresh_root_btn)
        top_layout.addWidget(v_sep)
        top_layout.addWidget(self.theme_button)
        root_layout.addWidget(top_bar)

        # Tabs — step-numbered to reinforce the workflow
        self.tabs = QTabWidget()
        self.extract_tab = ExtractTabWidget(self)
        self.review_tab = ReviewTabWidget(self)
        self.export_tab = ExportTabWidget(self)
        self.tabs.addTab(self.extract_tab, "1 · Extract")
        self.tabs.addTab(self.review_tab, "2 · Review")
        self.tabs.addTab(self.export_tab, "3 · Play & Export")
        root_layout.addWidget(self.tabs, 1)

        # Status Bar — icon + message + spinner
        status_bar = QFrame()
        status_bar.setObjectName("statusBar")
        status_layout = QHBoxLayout(status_bar)
        status_layout.setSpacing(6)
        self.status_icon = QLabel("ℹ️")
        self.status_icon.setFixedWidth(20)
        self.status_label = QLabel("Welcome! Choose an exam folder to begin.")
        self.status_label.setObjectName("statusInfo")
        self.status_label.setWordWrap(True)
        self.status_progress = QProgressBar()
        self.status_progress.setRange(0, 0)
        self.status_progress.setMaximumWidth(120)
        self.status_progress.setMaximumHeight(12)
        self.status_progress.setTextVisible(False)
        self.status_progress.setVisible(False)
        status_layout.addWidget(self.status_icon)
        status_layout.addWidget(self.status_label, 1)
        status_layout.addWidget(self.status_progress)
        root_layout.addWidget(status_bar)

    def _connect_signals(self) -> None:
        self.choose_root_btn.clicked.connect(self.choose_folder)
        self.refresh_root_btn.clicked.connect(self.reload_folder)
        self.recent_btn.clicked.connect(self._show_recent_menu)
        self.theme_button.clicked.connect(self.toggle_theme)
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(lambda: (self.extract_tab.exam_search.setFocus(), self.extract_tab.exam_search.selectAll()))

    # ==================== Dynamic Tab Delegation ====================
    def __getattr__(self, name: str) -> Any:
        """Forward unmatched attribute/method lookups to child tabs for backward compatibility."""
        tabs = [
            self.__dict__.get("extract_tab"),
            self.__dict__.get("review_tab"),
            self.__dict__.get("export_tab"),
        ]
        for tab in tabs:
            if tab is not None and hasattr(tab, name):
                return getattr(tab, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def __dir__(self) -> list[str]:
        """Include child tab attributes in introspection and autocompletion."""
        attrs = set(super().__dir__())
        for tab in (
            self.__dict__.get("extract_tab"),
            self.__dict__.get("review_tab"),
            self.__dict__.get("export_tab"),
        ):
            if tab is not None:
                attrs.update(dir(tab))
        return sorted(attrs)

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
        _icons = {
            "error": "❌",
            "success": "✅",
            "busy": "⏳",
            "ready": "✅",
        }
        _names = {
            "error": "statusError",
            "success": "statusSuccess",
            "busy": "statusBusy",
            "ready": "statusSuccess",
        }
        icon = _icons.get(status_type, "ℹ️")
        name = _names.get(status_type, "statusInfo")
        self.status_icon.setText(icon)
        # Dynamically update the objectName so the stylesheet selector re-applies
        self.status_label.setObjectName(name)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _set_worker_busy(self, busy: bool) -> None:
        self.status_progress.setVisible(busy)
        cursor = Qt.CursorShape.WaitCursor if busy else Qt.CursorShape.ArrowCursor
        QGuiApplication.setOverrideCursor(cursor) if busy else QGuiApplication.restoreOverrideCursor()

    def _update_tab_labels(self) -> None:
        dirty_badge = " *" if self.state["dirty"] else ""
        self.tabs.setTabText(1, f"2 · Review{dirty_badge}")
        selected_count = len(self.export_tab.checked_play_workspaces())
        count_badge = f" ({selected_count})" if selected_count else ""
        self.tabs.setTabText(2, f"3 · Play & Export{count_badge}")

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

    def _set_root_label(self, path: Path) -> None:
        """Show folder name in label; full absolute path in tooltip."""
        self.root_label.setText(f"📁 {path.name}")
        self.root_label.setToolTip(str(path))

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
        self._set_root_label(target)
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
        self.extract_tab.exam_list.clear()
        self.export_tab.play_list.clear()

        # Colors for dark/light mode — picked to be readable on both backgrounds
        _CLR_READY   = QColor("#2ea043")   # green  — extracted, no issues
        _CLR_WARN    = QColor("#d29922")   # amber  — has issues
        _CLR_PENDING = QColor("#8b8b8b")   # grey   — not extracted yet (no issues)

        for candidate in candidates:
            has_issues = bool(candidate.issues)
            is_ready   = candidate.ready_to_run  # questions.md exists AND no issues
            is_pending = not is_ready and not has_issues  # no questions.md, but also no blocking issue

            label = candidate.workspace.name
            if has_issues:
                label += f" ({'; '.join(candidate.issues)})"

            if is_ready:
                color = _CLR_READY
                tooltip = "Ready — questions extracted and no issues."
            elif has_issues:
                color = _CLR_WARN
                tooltip = "Issues:\n• " + "\n• ".join(candidate.issues)
            else:
                color = _CLR_PENDING
                tooltip = "Not extracted yet. Select this exam and run extraction."

            brush = QBrush(color)

            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, candidate.workspace)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setForeground(brush)
            item.setToolTip(tooltip)
            self.extract_tab.exam_list.addItem(item)

            play_item = QListWidgetItem(label)
            play_item.setData(Qt.ItemDataRole.UserRole, candidate.workspace)
            play_item.setFlags(play_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            play_item.setCheckState(Qt.CheckState.Checked if is_ready else Qt.CheckState.Unchecked)
            play_item.setForeground(brush)
            play_item.setToolTip(tooltip)
            self.export_tab.play_list.addItem(play_item)

        self._set_root_label(self.state['root'])
        if self.extract_tab.exam_list.count() > 0:
            self.extract_tab.exam_list.setCurrentRow(0)
        self.export_tab.update_summary()

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
            self._set_root_label(self.state['root'])
            self.populate_tests()
            self._set_status(f"Selected exam folder: {self.state['root']}", "success")

    def select_exam(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        if not current:
            return
        workspace = current.data(Qt.ItemDataRole.UserRole)
        if workspace:
            if not self.confirm_discard_changes():
                if previous:
                    self.extract_tab.exam_list.blockSignals(True)
                    self.extract_tab.exam_list.setCurrentItem(previous)
                    self.extract_tab.exam_list.blockSignals(False)
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
        self.extract_tab.current_exam_title.setText(f"Exam: {workspace.name}")

        self.extract_tab.pdf_combo.blockSignals(True)
        self.extract_tab.pdf_combo.clear()
        sources = discover_sources(workspace)
        if getattr(workspace, "source_pdf", None):
            self.extract_tab.pdf_combo.addItem(workspace.source_pdf.name, workspace.source_pdf)
        elif sources.pdf:
            self.extract_tab.pdf_combo.addItem(sources.pdf.name, sources.pdf)
        _pdf_exts = {".pdf", ".docx"}
        for doc in sorted(
            (p for p in workspace.path.iterdir() if p.is_file() and p.suffix.lower() in _pdf_exts),
            key=lambda item: item.name.casefold(),
        ):
            if self.extract_tab.pdf_combo.findData(doc) < 0:
                self.extract_tab.pdf_combo.addItem(doc.name, doc)
        if not self.extract_tab.pdf_combo.count():
            self.extract_tab.pdf_combo.addItem("No exam file selected", None)
        self.extract_tab.pdf_combo.blockSignals(False)

        self.extract_tab.answer_combo.clear()
        self.extract_tab.answer_combo.addItem("No answer key", None)
        for answer in sources.answer_keys:
            self.extract_tab.answer_combo.addItem(answer.name, answer)
        _ans_exts = {".csv", ".xlsx", ".xls"}
        for ans in sorted(
            (p for p in workspace.path.iterdir() if p.is_file() and p.suffix.lower() in _ans_exts),
            key=lambda item: item.name.casefold(),
        ):
            if self.extract_tab.answer_combo.findData(ans) < 0:
                self.extract_tab.answer_combo.addItem(ans.name, ans)

        self.extract_tab.preview.setText("No exam preview loaded.")

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
        self.review_tab.refresh_question_list()
        self._update_tab_labels()
        self.export_tab.update_summary()
        self.extract_tab._on_pdf_selection_changed()

    def confirm_discard_changes(self) -> bool:
        if not self.state["dirty"]:
            return True
        self.review_tab.save_active_question()
        choice = QMessageBox.question(
            self,
            "Unsaved changes",
            "You have unsaved changes in questions.md. Save them before continuing?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if choice == QMessageBox.StandardButton.Save:
            self.review_tab.save_test()
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
        target_root = None
        if configured and configured.is_dir():
            target_root = configured
        elif saved and Path(saved).is_dir():
            target_root = Path(saved)
        self.state["root"] = target_root
        if target_root:
            self._set_root_label(target_root)
            self.populate_tests()
            last_workspace = self.settings.value("last_workspace")
            if last_workspace:
                for index in range(self.extract_tab.exam_list.count()):
                    item = self.extract_tab.exam_list.item(index)
                    workspace = item.data(Qt.ItemDataRole.UserRole)
                    if workspace and workspace.name == last_workspace:
                        self.extract_tab.exam_list.setCurrentItem(item)
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
