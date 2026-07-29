# -*- mode: python ; coding: utf-8 -*-

import os

block_cipher = None

# Directory containing this spec file
spec_dir = SPECPATH
repo_root = os.path.dirname(spec_dir)

a = Analysis(
    [os.path.join(spec_dir, 'quiz_builder_cli.py')],
    pathex=[repo_root, spec_dir],
    binaries=[],
    datas=[],
    hiddenimports=[
        'fitz',
        'pandas',
        'openpyxl',
        'http.server',
        'socketserver',
        'webbrowser',
        'json',
        'mimetypes',
        'base64',
        're',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='quiz_builder',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
    version=os.path.join(spec_dir, 'version_info.txt')
)
