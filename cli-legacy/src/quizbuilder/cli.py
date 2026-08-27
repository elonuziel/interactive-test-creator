from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .config import Config
from .dependencies import DependencyError, require_dependencies
from .paths import application_root, tests_root, web_root
from .platform import serve
from .providers import detect_providers



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quizbuilder", description="Interactive Hebrew Quiz Builder")
    parser.add_argument("--config", type=Path, help="Path to a TOML configuration file")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("wizard", help="Run the guided workflow")
    subparsers.add_parser("gui", help="Open the desktop GUI")
    process = subparsers.add_parser("process", help="Process a workspace")
    process.add_argument("workspace", type=Path)
    prompt = subparsers.add_parser("prompt", help="Generate a prompt for a workspace")
    prompt.add_argument("workspace", type=Path)
    prompt.add_argument("--kind", choices=("local", "web"), default="local")
    prompt.add_argument("--form", default=None)
    build = subparsers.add_parser("build", help="Build a standalone HTML quiz")
    build.add_argument("workspace", type=Path)
    build.add_argument("-o", "--output", type=Path)
    run = subparsers.add_parser("run", help="Prepare one test or a mixed quiz run")
    run.add_argument("workspaces", type=Path, nargs="+")
    run.add_argument("--mix", action="store_true", help="Mix questions from all selected tests")
    run.add_argument("--name", help="Name for the derived run")
    run.add_argument("-o", "--output", type=Path, help="Write the derived questions JSON")
    run.add_argument("--html", type=Path, help="Write a standalone HTML quiz for the run")
    init = subparsers.add_parser("init", help="Create a workspace")
    init.add_argument("name")
    detect = subparsers.add_parser("detect", help="Check dependencies and available AI providers")
    detect.add_argument("--no-dependencies", action="store_true", help="Only detect providers")
    serve = subparsers.add_parser("serve", help="Serve the web player")
    serve.add_argument("--port", type=int, default=8000)
    validate = subparsers.add_parser("validate", help="Validate a questions JSON file")
    validate.add_argument("questions", type=Path)
    clean = subparsers.add_parser("clean", help="Remove generated scratch files from a workspace")
    clean.add_argument("workspace", type=Path)
    subparsers.add_parser("version", help="Print the package version")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = Config.load(args.config, tests_root())

    try:
        if args.command == "version":
            from . import __version__
            print(__version__)
            return 0
        if args.command == "gui":
            from .gui import main as gui_main
            return gui_main()
        if args.command == "process":
            from .commands import process_workspace
            artifacts = process_workspace(config, args.workspace)
            print(f"Processed workspace; {len(artifacts)} artifact(s) produced.")
            return 0
        if args.command == "prompt":
            from .commands import generate_workspace_prompt
            print(generate_workspace_prompt(config, args.workspace, args.kind, args.form))
            return 0
        if args.command == "build":
            from .commands import build_workspace
            print(build_workspace(config, args.workspace, args.output))
            return 0
        if args.command == "run":
            from .models import Workspace
            from .exporter import build_run_standalone_quiz
            from .runs import assemble_run, write_run_questions

            workspaces = [Workspace(path.resolve().name, path.resolve()) for path in args.workspaces]
            quiz_run = assemble_run(workspaces, name=args.name, mix=args.mix)
            if args.output:
                print(write_run_questions(quiz_run, args.output.resolve()))
            if args.html:
                print(build_run_standalone_quiz(quiz_run, args.html.resolve(), config.scripts_root))
            if not args.output and not args.html:
                print(f"{quiz_run.name}: {len(quiz_run.questions)} question(s) from {len(quiz_run.sources)} test(s)")
            return 0
        if args.command == "init":
            from .workspace import create_workspace
            workspace = create_workspace(config.workspace_root, args.name)
            print(workspace.path)
            return 0
        if args.command == "clean":
            from .commands import clean_workspace
            print(f"Removed {clean_workspace(args.workspace)} scratch file(s).")
            return 0
        if args.command == "validate":
            from .commands import validate_questions
            print(f"Valid: {validate_questions(args.questions)} question(s).")
            return 0
        if args.command == "detect":
            if not args.no_dependencies:
                require_dependencies()
            providers = detect_providers(config.provider.freebuff_commands)
            for provider, command in providers:
                print(f"{provider.id}: {command}")
            return 0
        if args.command == "serve":
            from .web_assets import validate_assets
            missing = validate_assets(web_root())
            if missing:
                raise ValueError(f"Missing web assets: {', '.join(missing)}")
            serve(web_root(), args.port, config.provider.open_browser)
            return 0
        if args.command in (None, "wizard"):
            from .wizard import run
            return run(config)
        parser.error(f"Unknown command: {args.command}")
    except (DependencyError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
