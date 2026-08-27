from __future__ import annotations

from pathlib import Path

from .config import Config
from .documents import DocumentError, classify_pdf, convert_docx_with_soffice
from .commands import process_workspace as process_workspace_command
from .exporter import build_standalone_quiz
from .pipeline import PipelineRunner
from .platform import open_path
from .prompts import generate_prompt, send_to_provider
from .providers import detect_providers
from .workspace import create_workspace, discover_sources, list_workspaces


def choose_workspace(config: Config):
    workspaces = list_workspaces(config.workspace_root)
    print("\nWorkspaces:")
    for index, workspace in enumerate(workspaces, 1):
        status = "ready" if workspace.questions_path.exists() else "pending"
        print(f"  [{index}] {workspace.name} ({status})")
    print("  [N] New workspace")
    choice = input("Choose workspace: ").strip().lower()
    if choice == "n":
        return create_workspace(config.workspace_root, input("Workspace name: "))
    if choice.isdigit() and 1 <= int(choice) <= len(workspaces):
        return workspaces[int(choice) - 1]
    return None


def run_workspace(config: Config, workspace) -> None:
    sources = discover_sources(workspace)
    if sources.docx and not sources.pdf:
        try:
            converted = convert_docx_with_soffice(sources.docx[0], workspace.path)
            sources = discover_sources(workspace)
            print(f"Converted DOCX to {converted}")
        except DocumentError as err:
            print(f"DOCX conversion unavailable: {err}")
    if not sources.pdf:
        print(f"Place a PDF or DOCX in {workspace.path}")
        open_path(workspace.path)
        return

    print(f"PDF: {sources.pdf.name}")
    digital = classify_pdf(sources.pdf)
    runner = PipelineRunner(config.scripts_root)
    if digital:
        raw = workspace.path / "raw_text.md"
        images = workspace.path / "images"
        page_map = workspace.path / "page_map.json"
        runner.extract_text(sources.pdf, raw, images, page_map)
        runner.parse_questions(raw, workspace.questions_path, images, page_map)
    else:
        pages = workspace.path / "pages_output"
        runner.render_pages(sources.pdf, pages, config.default_discard_pages, workspace.path / f"{workspace.name}_clean.pdf")
        print(f"Scanned PDF rendered to {pages}; use a prompt provider to extract questions.")

    if workspace.questions_path.exists():
        runner.merge_answers(workspace.path)
        runner.validate(workspace.questions_path)
    else:
        providers = detect_providers(config.provider.freebuff_commands)
        for index, (provider, command) in enumerate(providers, 1):
            print(f"  [{index}] {provider.label}")
        print("  [S] Skip")
        choice = input("Prompt provider: ").strip().lower()
        if choice.isdigit() and 1 <= int(choice) <= len(providers):
            provider, command = providers[int(choice) - 1]
            prompt = generate_prompt(runner, workspace.path, workspace.name, config.default_form, bool(sources.answer_keys), "local")
            print(f"Generated {prompt}")
            process = send_to_provider(provider, command, prompt)
            input("Press Enter after the provider finishes...")
            if process.poll() is None:
                print("Provider is still running.")

    if workspace.questions_path.exists():
        runner.merge_answers(workspace.path)
        runner.validate(workspace.questions_path)
        if input("Build standalone HTML? (Y/n): ").strip().lower() != "n":
            output = build_standalone_quiz(workspace.path, runner.scripts_dir)
            print(f"Built {output}")


def run(config: Config) -> int:
    workspace = choose_workspace(config)
    if workspace:
        run_workspace(config, workspace)
    return 0
