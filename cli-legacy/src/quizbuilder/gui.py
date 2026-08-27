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
            QFileDialog,
            QLabel,
            QListWidget,
            QListWidgetItem,
            QMessageBox,
            QPushButton,
            QCheckBox,
            QComboBox,
            QHBoxLayout,
            QLineEdit,
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
    window.resize(980, 680)
    layout = QVBoxLayout(window)

    root_label = QLabel("Choose a folder containing test projects")
    layout.addWidget(root_label)
    choose_root = QPushButton("Choose projects folder")
    layout.addWidget(choose_root)
    content = QHBoxLayout()
    tests = QListWidget()
    content.addWidget(tests, 1)
    preview = QLabel("PDF preview")
    preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
    preview.setMinimumSize(260, 260)
    content.addWidget(preview, 2)

    editor = QWidget()
    editor_layout = QVBoxLayout(editor)
    question_list = QListWidget()
    editor_layout.addWidget(question_list)
    question_text = QLineEdit()
    question_text.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    editor_layout.addWidget(question_text)
    option_fields = [QLineEdit() for _ in range(4)]
    for field in option_fields:
        field.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        editor_layout.addWidget(field)
    correct_index = QComboBox()
    correct_index.addItems(["1", "2", "3", "4"])
    editor_layout.addWidget(correct_index)
    question_actions = QHBoxLayout()
    add_question = QPushButton("Add question")
    remove_question = QPushButton("Remove question")
    save_project = QPushButton("Save test")
    question_actions.addWidget(add_question)
    question_actions.addWidget(remove_question)
    question_actions.addWidget(save_project)
    editor_layout.addLayout(question_actions)
    content.addWidget(editor, 3)
    layout.addLayout(content)
    mix = QCheckBox("Mix questions from all selected tests")
    layout.addWidget(mix)
    process_button = QPushButton("Process selected PDF")
    layout.addWidget(process_button)
    pdf_source = QComboBox()
    pdf_source.addItem("No PDF selected")
    layout.addWidget(pdf_source)
    process_batch_button = QPushButton("Process all checked tests")
    layout.addWidget(process_batch_button)
    answer_key = QComboBox()
    answer_key.addItem("No answer key")
    layout.addWidget(answer_key)
    form_number = QLineEdit("0")
    form_number.setPlaceholderText("Answer-key form number")
    layout.addWidget(form_number)
    prompt_button = QPushButton("Create offline generation prompt")
    layout.addWidget(prompt_button)
    provider = QComboBox()
    for web_provider in WEB_PROVIDERS:
        provider.addItem(web_provider.label, (web_provider, None))
    for local_provider, command in detect_providers():
        provider.addItem(f"{local_provider.label} ({command})", (local_provider, command))
    layout.addWidget(provider)
    launch_provider = QPushButton("Create prompt and launch provider")
    layout.addWidget(launch_provider)
    run_button = QPushButton("Prepare and open selected run")
    layout.addWidget(run_button)
    status_label = QLabel("Ready")
    layout.addWidget(status_label)

    state = {"root": None, "workspace": None, "questions": [], "index": -1}

    def save_question() -> None:
        index = state["index"]
        if index < 0 or index >= len(state["questions"]):
            return
        question = state["questions"][index]
        question["question"] = question_text.text()
        question["options"] = [field.text() for field in option_fields if field.text()]
        question["correctIndex"] = correct_index.currentIndex()

    def show_question(index: int) -> None:
        save_question()
        state["index"] = index
        question = state["questions"][index]
        question_text.setText(question.get("question", ""))
        options = question.get("options", [])
        for option_number, field in enumerate(option_fields):
            field.setText(options[option_number] if option_number < len(options) else "")
        answer = question.get("correctIndex", 0)
        correct_index.setCurrentIndex(answer if isinstance(answer, int) and 0 <= answer < 4 else 0)

    def load_workspace(workspace) -> None:
        pdf_source.clear()
        pdf_source.addItem("No PDF selected")
        pdf_paths = [workspace.source_pdf] if workspace.source_pdf else sorted(
            (item for item in workspace.path.iterdir() if item.is_file() and item.suffix.lower() == ".pdf"),
            key=lambda item: item.name.lower(),
        )
        for path in pdf_paths:
            if path is None:
                continue
            pdf_source.addItem(path.name, path)
        answer_key.clear()
        answer_key.addItem("No answer key")
        for path in discover_sources(workspace).answer_keys:
            answer_key.addItem(path.name, path)
        try:
            questions = load_questions(workspace.questions_path)
        except ValidationError as exc:
            state["workspace"] = workspace
            state["questions"] = []
            question_list.clear()
            QMessageBox.warning(window, "Cannot edit test", str(exc))
            return
        state["workspace"] = workspace
        state["questions"] = questions
        state["index"] = -1
        question_list.clear()
        for number, question in enumerate(questions, 1):
            question_list.addItem(f"{number}. {question['question'][:80]}")
        if questions:
            question_list.setCurrentRow(0)

    def save_workspace() -> None:
        workspace = state["workspace"]
        if workspace is None:
            return
        save_question()
        workspace.questions_path.write_text(
            json.dumps(state["questions"], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        QMessageBox.information(window, "Saved", str(workspace.questions_path))

    def refresh() -> None:
        root = QFileDialog.getExistingDirectory(window, "Choose projects folder")
        if not root:
            return
        state["root"] = Path(root)
        tests.clear()
        for candidate in discover_batch(state["root"]):
            label = candidate.workspace.name
            if candidate.issues:
                label += f"  ({'; '.join(candidate.issues)})"
            item = QListWidgetItem(label, tests)
            item.setData(Qt.ItemDataRole.UserRole, candidate.workspace)
            item.setCheckState(Qt.CheckState.Unchecked)
        root_label.setText(f"Projects: {root}")

    def prepare() -> None:
        selected = [
            tests.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(tests.count())
            if tests.item(index).checkState()
        ]
        try:
            save_question()
            run = assemble_run(selected, mix=mix.isChecked())
            root = state["root"]
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
        QMessageBox.information(
            window,
            "Run prepared",
            f"{len(run.questions)} question(s) from {len(run.sources)} test(s)\n{html_output}",
        )

    def process_selected() -> None:
        workspace = state["workspace"]
        root = state["root"]
        if workspace is None or root is None:
            QMessageBox.warning(window, "No test selected", "Choose a test first.")
            return
        process_button.setEnabled(False)
        run_button.setEnabled(False)
        status_label.setText(f"Processing {workspace.name}...")

        selected_answer_key = answer_key.currentData()
        worker = Worker(
            lambda: process_workspace(
                Config.defaults(root=root),
                workspace.path,
                selected_answer_key,
                form_number.text().strip() or "0",
                pdf_source.currentData(),
            )
        )
        worker.signals.finished.connect(
            lambda _result: (
                process_button.setEnabled(True),
                run_button.setEnabled(True),
                status_label.setText(f"Processed {workspace.name}"),
                load_workspace(workspace),
            )
        )
        worker.signals.failed.connect(
            lambda message: (
                process_button.setEnabled(True),
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
            if tests.item(index).checkState()
        ]
        if root is None or not selected:
            QMessageBox.warning(window, "No tests selected", "Check at least one test first.")
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
        root = state["root"]
        if workspace is None or root is None:
            QMessageBox.warning(window, "No test selected", "Choose a test first.")
            return
        try:
            prompt_path = generate_workspace_prompt(Config.defaults(root=root), workspace.path)
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.critical(window, "Cannot create prompt", str(exc))
            return
        QMessageBox.information(window, "Prompt created", str(prompt_path))

    def preview_selected() -> None:
        workspace = state["workspace"]
        if workspace is None:
            QMessageBox.warning(window, "No test selected", "Choose a test first.")
            return
        source = discover_sources(workspace).pdf
        if source is None:
            QMessageBox.warning(window, "No PDF found", "This test has no PDF source.")
            return
        preview.setText("Rendering preview...")
        worker = Worker(lambda: render_pdf_page(source))
        worker.signals.finished.connect(
            lambda image: preview.setPixmap(QPixmap.fromImage(QImage.fromData(image)))
        )
        worker.signals.failed.connect(lambda message: preview.setText(message))
        thread_pool.start(worker)

    def launch_generation_provider() -> None:
        workspace = state["workspace"]
        root = state["root"]
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
        QMessageBox.information(window, "Prompt ready", str(prompt_path))

    choose_root.clicked.connect(refresh)
    tests.currentItemChanged.connect(
        lambda current, _previous: load_workspace(current.data(Qt.ItemDataRole.UserRole))
        if current else None
    )
    question_list.currentRowChanged.connect(
        lambda index: show_question(index) if index >= 0 else None
    )
    add_question.clicked.connect(
        lambda: (
            save_question(),
            state["questions"].append({"question": "", "options": ["", ""], "correctIndex": 0}),
            question_list.addItem(f"{len(state['questions'])}. New question"),
            question_list.setCurrentRow(len(state["questions"]) - 1),
        )
    )
    remove_question.clicked.connect(
        lambda: (
            state["questions"].pop(state["index"]),
            question_list.takeItem(state["index"]),
            state.update(index=-1),
        ) if 0 <= state["index"] < len(state["questions"]) else None
    )
    save_project.clicked.connect(save_workspace)
    process_button.clicked.connect(process_selected)
    process_batch_button.clicked.connect(process_batch)
    preview_button = QPushButton("Preview first PDF page")
    layout.addWidget(preview_button)
    preview_button.clicked.connect(preview_selected)
    prompt_button.clicked.connect(create_prompt)
    launch_provider.clicked.connect(launch_generation_provider)
    run_button.clicked.connect(prepare)
    window.show()
    return application.exec()
