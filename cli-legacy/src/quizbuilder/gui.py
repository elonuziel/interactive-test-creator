from __future__ import annotations

import json
from pathlib import Path
import webbrowser

from .batch import discover_batch
from .commands import generate_workspace_prompt, process_workspace, process_workspaces
from .config import Config
from .exporter import build_run_standalone_quiz
from .providers import WEB_PROVIDERS, detect_providers, open_web_provider
from .prompts import send_to_provider
from .preview import render_pdf_page
from .runs import RunError, assemble_run, write_run_questions
from .validation import ValidationError, load_questions
from .workspace import discover_sources


def main() -> int:
    try:
        from PySide6.QtWidgets import (
            QApplication,
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
            QPushButton,
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

    # ── Center Area: 3-Column Layout ───────────────────────────────────────
    content = QHBoxLayout()
    content.setSpacing(10)

    # Column 1: Test Projects List & Batch Selection
    projects_group = QGroupBox("1. Projects & Selection")
    projects_layout = QVBoxLayout(projects_group)
    tests = QListWidget()
    projects_layout.addWidget(tests)
    mix = QCheckBox("Mix questions from checked tests")
    projects_layout.addWidget(mix)
    content.addWidget(projects_group, 2)

    # Column 2: Source PDF & Preview
    preview_group = QGroupBox("2. Source PDF & Preview")
    preview_layout = QVBoxLayout(preview_group)
    pdf_source_layout = QHBoxLayout()
    pdf_source_layout.addWidget(QLabel("PDF:"))
    pdf_source = QComboBox()
    pdf_source.addItem("No PDF selected", None)
    pdf_source_layout.addWidget(pdf_source, 1)
    preview_layout.addLayout(pdf_source_layout)

    preview = QLabel("No PDF preview loaded")
    preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
    preview.setMinimumSize(260, 300)
    preview.setFrameShape(QFrame.Shape.StyledPanel)
    preview.setStyleSheet("background-color: #f5f5f5; border: 1px solid #ddd;")
    preview_layout.addWidget(preview, 1)

    preview_button = QPushButton("🔍 Preview first page")
    preview_layout.addWidget(preview_button)
    content.addWidget(preview_group, 3)

    # Column 3: Question Editor
    editor_group = QGroupBox("3. Hebrew Question Editor (RTL)")
    editor_layout = QVBoxLayout(editor_group)
    question_list = QListWidget()
    editor_layout.addWidget(question_list, 1)

    question_text_label = QLabel("Question Text:")
    editor_layout.addWidget(question_text_label)
    question_text = QLineEdit()
    question_text.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    question_text.setPlaceholderText("טקסט השאלה...")
    editor_layout.addWidget(question_text)

    editor_layout.addWidget(QLabel("Answer Options:"))
    option_fields = [QLineEdit() for _ in range(4)]
    placeholders = ["אפשרות 1 (א)...", "אפשרות 2 (ב)...", "אפשרות 3 (ג)...", "אפשרות 4 (ד)..."]
    for field, placeholder in zip(option_fields, placeholders):
        field.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        field.setPlaceholderText(placeholder)
        editor_layout.addWidget(field)

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

    question_actions = QHBoxLayout()
    add_question = QPushButton("➕ Add question")
    remove_question = QPushButton("➖ Remove question")
    save_project = QPushButton("💾 Save test")
    question_actions.addWidget(add_question)
    question_actions.addWidget(remove_question)
    question_actions.addWidget(save_project)
    editor_layout.addLayout(question_actions)
    content.addWidget(editor_group, 4)

    main_layout.addLayout(content, 1)

    # ── Bottom Control Panels: Action Groups ───────────────────────────────
    bottom_panels = QHBoxLayout()
    bottom_panels.setSpacing(10)

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

    proc_btn_layout = QHBoxLayout()
    process_button = QPushButton("⚙️ Process selected test")
    process_batch_button = QPushButton("⚡ Process checked")
    proc_btn_layout.addWidget(process_button)
    proc_btn_layout.addWidget(process_batch_button)
    process_layout.addLayout(proc_btn_layout)
    bottom_panels.addWidget(process_group, 3)

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

    ai_btn_layout = QHBoxLayout()
    launch_provider = QPushButton("🚀 Launch provider")
    prompt_button = QPushButton("📄 Offline prompt")
    ai_btn_layout.addWidget(launch_provider)
    ai_btn_layout.addWidget(prompt_button)
    ai_layout.addLayout(ai_btn_layout)
    bottom_panels.addWidget(ai_group, 3)

    # Action Group 3: Standalone Quiz Run
    run_group = QGroupBox("Standalone Quiz Run")
    run_layout = QVBoxLayout(run_group)
    run_button = QPushButton("▶️ Prepare & Open Standalone Quiz")
    run_button.setStyleSheet("font-weight: bold; padding: 10px;")
    run_layout.addWidget(run_button)
    bottom_panels.addWidget(run_group, 2)

    main_layout.addLayout(bottom_panels)

    # ── Status Bar ─────────────────────────────────────────────────────────
    status_label = QLabel("Ready")
    status_label.setStyleSheet("color: #555; padding: 2px;")
    main_layout.addWidget(status_label)

    state = {"root": None, "workspace": None, "questions": [], "index": -1}

    def update_editor_fields(question: dict | None) -> None:
        if question is None:
            question_text.clear()
            for field in option_fields:
                field.clear()
            correct_index.setCurrentIndex(0)
            return
        question_text.setText(question.get("question", ""))
        options = question.get("options", [])
        for option_number, field in enumerate(option_fields):
            field.setText(options[option_number] if option_number < len(options) else "")
        answer = question.get("correctIndex", 0)
        correct_index.setCurrentIndex(answer if isinstance(answer, int) and 0 <= answer < 4 else 0)

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
        state["index"] = index
        if 0 <= index < len(state["questions"]):
            update_editor_fields(state["questions"][index])
        else:
            update_editor_fields(None)

    def load_workspace(workspace) -> None:
        if workspace is None:
            state["workspace"] = None
            state["questions"] = []
            state["index"] = -1
            question_list.clear()
            update_editor_fields(None)
            pdf_source.clear()
            pdf_source.addItem("No PDF selected", None)
            answer_key.clear()
            answer_key.addItem("No answer key", None)
            return

        pdf_source.clear()
        pdf_paths = [workspace.source_pdf] if workspace.source_pdf else (
            sorted(
                (item for item in workspace.path.iterdir() if item.is_file() and item.suffix.lower() == ".pdf"),
                key=lambda item: item.name.lower(),
            )
            if workspace.path.is_dir()
            else []
        )
        for path in pdf_paths:
            if path:
                pdf_source.addItem(path.name, path)
        if pdf_source.count() == 0:
            pdf_source.addItem("No PDF selected", None)

        answer_key.clear()
        answer_key.addItem("No answer key", None)
        for path in discover_sources(workspace).answer_keys:
            answer_key.addItem(path.name, path)

        state["workspace"] = workspace
        state["index"] = -1
        try:
            questions = load_questions(workspace.questions_path)
            state["questions"] = questions
            refresh_question_list_labels()
            if questions:
                question_list.setCurrentRow(0)
            else:
                update_editor_fields(None)
            status_label.setText(f"Loaded {workspace.name} ({len(questions)} questions)")
        except (ValidationError, OSError):
            state["questions"] = []
            question_list.clear()
            update_editor_fields(None)
            status_label.setText(f"Selected {workspace.name} (no questions.json yet)")

    def save_workspace() -> None:
        workspace = state["workspace"]
        if workspace is None:
            QMessageBox.warning(window, "No test selected", "Choose a test first.")
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

    def refresh() -> None:
        root = QFileDialog.getExistingDirectory(window, "Choose projects folder")
        if not root:
            return
        state["root"] = Path(root)
        populate_tests_list()

    def prepare() -> None:
        selected = [
            tests.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(tests.count())
            if tests.item(index).checkState() == Qt.CheckState.Checked
        ]
        if not selected and state["workspace"]:
            selected = [state["workspace"]]

        if not selected:
            QMessageBox.warning(window, "No tests selected", "Select or check at least one test first.")
            return

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

    def process_selected() -> None:
        workspace = state["workspace"]
        root = state["root"] or (workspace.path.parent if workspace else None)
        if workspace is None or root is None:
            QMessageBox.warning(window, "No test selected", "Choose a test first.")
            return
        process_button.setEnabled(False)
        process_batch_button.setEnabled(False)
        run_button.setEnabled(False)
        status_label.setText(f"Processing {workspace.name}...")

        selected_answer_key = answer_key.currentData()
        selected_pdf = pdf_source.currentData()
        worker = Worker(
            lambda: process_workspace(
                Config.defaults(root=root),
                workspace.path,
                selected_answer_key,
                form_number.text().strip() or "0",
                selected_pdf,
            )
        )
        worker.signals.finished.connect(
            lambda _result: (
                process_button.setEnabled(True),
                process_batch_button.setEnabled(True),
                run_button.setEnabled(True),
                status_label.setText(f"Processed {workspace.name}"),
                load_workspace(workspace),
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
        thread_pool.start(worker)

    def process_batch() -> None:
        root = state["root"]
        selected = [
            tests.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(tests.count())
            if tests.item(index).checkState() == Qt.CheckState.Checked
        ]
        if root is None or not selected:
            QMessageBox.warning(window, "No tests checked", "Check at least one test in the list first.")
            return
        process_batch_button.setEnabled(False)
        process_button.setEnabled(False)
        run_button.setEnabled(False)
        status_label.setText(f"Processing {len(selected)} test(s)...")

        def process_all():
            results = process_workspaces(
                Config.defaults(root=root), selected
            )
            return (
                [result.workspace.name for result in results if result.success],
                [f"{result.workspace.name}: {result.error}" for result in results if not result.success],
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
        thread_pool.start(worker)

    def launch_generation_provider() -> None:
        workspace = state["workspace"]
        root = state["root"] or (workspace.path.parent if workspace else None)
        if workspace is None or root is None:
            QMessageBox.warning(window, "No test selected", "Choose a test first.")
            return
        selected_provider, command = provider.currentData()
        try:
            if selected_provider.kind == "web":
                prompt_path = generate_workspace_prompt(
                    Config.defaults(root=root), workspace.path, "web"
                )
                open_web_provider(selected_provider)
            else:
                prompt_path = generate_workspace_prompt(
                    Config.defaults(root=root), workspace.path, "local"
                )
                send_to_provider(selected_provider, command, prompt_path)
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.critical(window, "Cannot launch provider", str(exc))
            return
        status_label.setText(f"Provider launched for {workspace.name}")
        QMessageBox.information(window, "Prompt ready", str(prompt_path))

    def on_add_question() -> None:
        save_question()
        new_q = {
            "question": "שאלה חדשה",
            "options": ["אפשרות 1", "אפשרות 2", "אפשרות 3", "אפשרות 4"],
            "correctIndex": 0,
        }
        state["questions"].append(new_q)
        refresh_question_list_labels()
        question_list.setCurrentRow(len(state["questions"]) - 1)

    def on_remove_question() -> None:
        idx = state["index"]
        if 0 <= idx < len(state["questions"]):
            state["questions"].pop(idx)
            state["index"] = -1
            refresh_question_list_labels()
            if state["questions"]:
                new_idx = min(idx, len(state["questions"]) - 1)
                question_list.setCurrentRow(new_idx)
            else:
                update_editor_fields(None)

    choose_root.clicked.connect(refresh)
    refresh_root.clicked.connect(populate_tests_list)
    tests.currentItemChanged.connect(
        lambda current, _previous: load_workspace(current.data(Qt.ItemDataRole.UserRole))
        if current else None
    )
    question_list.currentRowChanged.connect(
        lambda index: show_question(index) if index >= 0 else None
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

    window.show()
    return application.exec()
