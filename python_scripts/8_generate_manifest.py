"""
8_generate_manifest.py — Auto-generate manifest.json for the quiz web app.

Scans a tests directory for subdirectories containing `questions.json` and
writes a manifest.json that the web app uses to populate the test selection menu.

Usage:
    python 8_generate_manifest.py                          # default: scans ./tests/
    python 8_generate_manifest.py --tests-dir path/to/tests
"""

import argparse
import json
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def derive_display_name(folder_name):
    """Convert a folder name like '2019_moed_a' into ' 2019 Moed A'."""
    return folder_name.replace('_', ' ').replace('-', ' ').title()


def scan_tests(tests_dir):
    """Walk the tests directory and find all folders with questions.json."""
    manifest = []

    if not os.path.isdir(tests_dir):
        return manifest

    for entry in sorted(os.listdir(tests_dir)):
        entry_path = os.path.join(tests_dir, entry)
        if not os.path.isdir(entry_path):
            continue

        questions_file = os.path.join(entry_path, 'questions.json')
        if os.path.isfile(questions_file):
            # Path relative to repo root (what the web app expects)
            relative_path = os.path.join(tests_dir, entry).replace('\\', '/')
            manifest.append({
                'name': derive_display_name(entry),
                'path': relative_path,
            })

    return manifest


def main():
    parser = argparse.ArgumentParser(
        description="Auto-generate manifest.json for the quiz web app test selection menu."
    )
    parser.add_argument(
        '--tests-dir', default='tests',
        help="Path to the tests directory (default: tests/)"
    )
    parser.add_argument(
        '-o', '--output', default=None,
        help="Output manifest file path (default: <tests-dir>/manifest.json)"
    )

    args = parser.parse_args()
    tests_dir = args.tests_dir
    output_path = args.output or os.path.join(tests_dir, 'manifest.json')

    manifest = scan_tests(tests_dir)

    if not manifest:
        print(f"No test folders with questions.json found in '{tests_dir}'.")
        print(f"Writing empty manifest to {output_path}")

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"Generated manifest with {len(manifest)} test(s) -> {output_path}")
    for entry in manifest:
        print(f"  • {entry['name']} ({entry['path']})")

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
