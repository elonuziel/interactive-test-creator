#!/usr/bin/env python3
"""
10_build_hub_html.py — Build a standalone Centralized Master Quiz Hub HTML.

Finds all subdirectories containing questions.md (or specified paths),
embeds them into a single self-contained quiz_hub.html with an interactive
Exam Picker, Mixed Practice Launcher (default 30 questions or all), and
localStorage question mastery tracking.

Usage:
    python 10_build_hub_html.py tests/
    python 10_build_hub_html.py tests/ -o "tests/quiz_hub.html"
"""

import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/src")
from quizbuilder.hub import build_central_hub, build_all_standalone_quizzes
from quizbuilder.super_batch import build_plan
from quizbuilder.models import Workspace

def main():
    parser = argparse.ArgumentParser(description="Compile Centralized Quiz Hub HTML.")
    parser.add_argument("root", help="Root directory containing exam folders")
    parser.add_argument("-o", "--output", help="Output HTML file path", default=None)
    parser.add_argument("--build-per-exam", action="store_true", help="Also build standalone quiz.html in each exam folder")
    parser.add_argument("--title", default="מרכז המבחנים האינטראקטיבי", help="Title of the quiz hub")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    plan = build_plan(root)
    workspaces = [
        Workspace(
            name=item.overview.name,
            path=item.overview.workspace,
            source_pdf=item.overview.pdf,
        )
        for item in plan.items
        if (item.overview.workspace / "questions.md").is_file() or (item.overview.workspace / "questions.json").is_file()
    ]

    if not workspaces:
        print(f"No workspaces with questions.md or questions.json found in {root}")
        sys.exit(1)

    print(f"Found {len(workspaces)} exam workspaces with questions.")

    if args.build_per_exam:
        print("Building standalone quiz.html for each exam folder...")
        standalone_list = build_all_standalone_quizzes(workspaces)
        print(f"Generated {len(standalone_list)} standalone quiz.html files.")

    out_path = Path(args.output) if args.output else None
    hub_file = build_central_hub(root, workspaces, output=out_path, title=args.title)
    print(f"Successfully generated Centralized Quiz Hub at: {hub_file} ({hub_file.stat().st_size} bytes)")

if __name__ == "__main__":
    main()
