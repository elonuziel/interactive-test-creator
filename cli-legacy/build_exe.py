#!/usr/bin/env python3
"""
build_exe.py — Build quiz_builder.exe using PyInstaller
"""

import subprocess
import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    spec_file = os.path.join(base_dir, 'quiz_builder.spec')
    dist_dir = os.path.join(base_dir, 'dist')
    work_dir = os.path.join(base_dir, 'build')
    
    print(f"Building quiz_builder.exe from {spec_file}...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        f"--distpath={dist_dir}",
        f"--workpath={work_dir}",
        spec_file
    ]
    
    res = subprocess.run(cmd)
    if res.returncode == 0:
        dist_exe = os.path.join(dist_dir, 'quiz_builder.exe')
        print(f"\n[OK] Build successful! Executable generated at:\n  {dist_exe}")
    else:
        print(f"\n[X] Build failed with exit code {res.returncode}")
        sys.exit(res.returncode)

if __name__ == '__main__':
    main()
