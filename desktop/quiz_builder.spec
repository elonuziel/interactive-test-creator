# -*- mode: python ; coding: utf-8 -*-

import os

block_cipher = None

# Directory containing this spec file
spec_dir = SPECPATH

python_scripts_src = os.path.join(spec_dir, 'python_scripts')
web_dir_src = os.path.join(spec_dir, 'web')

datas = [
    (python_scripts_src, 'python_scripts'),
    (python_scripts_src, 'desktop/python_scripts'),
    (python_scripts_src, 'cli-legacy/python_scripts'),
]

if os.path.isdir(web_dir_src):
    datas.append((web_dir_src, 'desktop/web'))
    datas.append((web_dir_src, 'cli-legacy/web'))
    datas.append((web_dir_src, 'web'))
    datas.append((web_dir_src, '.'))

a = Analysis(
    [os.path.join(spec_dir, 'quiz_builder_cli.py')],
    pathex=[spec_dir],
    binaries=[],
    datas=datas,
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
        'runpy',
        'quiz_builder_gui',
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'queue',
        'threading',
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
