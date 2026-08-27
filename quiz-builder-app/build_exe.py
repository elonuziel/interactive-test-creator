#!/usr/bin/env python3
"""
build_exe.py — Build quiz_builder_gui.exe using PyInstaller with automatic version bumping and Authenticode Code Signing

import subprocess
import sys
import os
import re
import argparse

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

VERSION_TEMPLATE = """# UTF-8
# Windows Version Info for quiz_builder.exe

VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, {build}),
    prodvers=({major}, {minor}, {patch}, {build}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '040904B0',
          [
            StringStruct('CompanyName', 'Elon Uziel'),
            StringStruct('FileDescription', 'Interactive Hebrew Quiz Builder Executable'),
            StringStruct('FileVersion', '{ver_str}'),
            StringStruct('InternalName', 'quiz_builder_gui'),
            StringStruct('LegalCopyright', 'Copyright © 2026 Elon Uziel. MIT License.'),
            StringStruct('ProductName', 'Interactive Hebrew Quiz Builder'),
            StringStruct('ProductVersion', '{ver_str}')
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""

def parse_version_tuple(ver_input):
    clean = re.sub(r'^[^\d]+', '', str(ver_input or '')).strip()
    parts = [int(p) for p in re.findall(r'\d+', clean)]
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts[:4])

def read_current_version(info_file):
    if not os.path.exists(info_file):
        return (1, 0, 0, 0)
    try:
        with open(info_file, 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.search(r'filevers=\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)', content)
        if match:
            return tuple(int(m) for m in match.groups())
    except Exception:
        pass
    return (1, 0, 0, 0)

def update_version_info_file(info_file, ver_tuple):
    major, minor, patch, build = ver_tuple
    ver_str = f"{major}.{minor}.{patch}.{build}"
    content = VERSION_TEMPLATE.format(
        major=major,
        minor=minor,
        patch=patch,
        build=build,
        ver_str=ver_str
    )
    with open(info_file, 'w', encoding='utf-8') as f:
        f.write(content)
    return ver_str

def sign_executable(exe_path):
    if sys.platform != 'win32':
        return
    print(f"Signing executable {os.path.basename(exe_path)} with Publisher 'Elon Uziel'...")
    ps_cmd = (
        f"$cert = Get-ChildItem Cert:\\CurrentUser\\My -CodeSigningCert | Where-Object {{ $_.Subject -match 'Elon Uziel' }} | Select-Object -First 1; "
        f"if (-not $cert) {{ $cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject 'CN=Elon Uziel, O=Elon Uziel' -CertStoreLocation 'Cert:\\CurrentUser\\My' }}; "
        f"Set-AuthenticodeSignature -FilePath '{exe_path}' -Certificate $cert -HashAlgorithm SHA256"
    )
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
        if res.returncode == 0:
            print(f"  [OK] Successfully signed {os.path.basename(exe_path)} (Publisher: Elon Uziel)")
        else:
            print(f"  [!] Notice: Code signing returned: {res.stderr.strip()}")
    except Exception as e:
        print(f"  [!] Notice: Code signing skipped: {e}")

def main():
    parser = argparse.ArgumentParser(description="Build quiz_builder.exe with automatic version bumping and code signing")
    parser.add_argument('-v', '--version', help="Specify version string (e.g. 1.0.1 or v1.0.1). If omitted, increments build number.")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    spec_file = os.path.join(base_dir, 'quiz_builder_gui.spec')
    info_file = os.path.join(base_dir, 'version_info.txt')
    dist_dir = os.path.join(base_dir, 'dist')
    work_dir = os.path.join(base_dir, 'build')

    if args.version:
        ver_tuple = parse_version_tuple(args.version)
    else:
        current_tuple = read_current_version(info_file)
        # Increment build number by 1
        ver_tuple = (current_tuple[0], current_tuple[1], current_tuple[2], current_tuple[3] + 1)

    ver_str = update_version_info_file(info_file, ver_tuple)
    print(f"Bumped version to: {ver_str}")

    print(f"Building quiz_builder.exe v{ver_str} from {spec_file}...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        f"--distpath={dist_dir}",
        f"--workpath={work_dir}",
        spec_file
    ]

    res = subprocess.run(cmd)
    if res.returncode == 0:
        dist_exe = os.path.join(dist_dir, 'quiz_builder_gui.exe')
        print(f"\n[OK] Build successful! Executable v{ver_str} generated at:\n  {dist_exe}")
        sign_executable(dist_exe)
    else:
        print(f"\n[X] Build failed with exit code {res.returncode}")
        sys.exit(res.returncode)

if __name__ == '__main__':
    main()
