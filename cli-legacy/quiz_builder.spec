# -*- mode: python ; coding: utf-8 -*-

import os

block_cipher = None

# Directory containing this spec file
spec_dir = SPECPATH
repo_root = os.path.dirname(spec_dir)

python_scripts_src = os.path.join(spec_dir, 'python_scripts')
if not os.path.isdir(python_scripts_src):
    python_scripts_src = os.path.join(repo_root, 'python_scripts')

datas = [
    (python_scripts_src, 'python_scripts'),
    (python_scripts_src, 'cli-legacy/python_scripts'),
]

# Include web app assets in bundle
web_dir_src = os.path.join(spec_dir, 'web')
if os.path.isdir(web_dir_src):
    datas.append((web_dir_src, 'cli-legacy/web'))
    datas.append((web_dir_src, 'web'))
    datas.append((web_dir_src, '.'))

for web_asset in ['index.html', 'style.css', 'app.js', 'generator.js', 'quiz_generator.html', 'favicon.svg']:
    asset_path = os.path.join(repo_root, web_asset)
    if os.path.isfile(asset_path):
        datas.append((asset_path, '.'))
        datas.append((asset_path, 'web'))
        datas.append((asset_path, 'cli-legacy'))

a = Analysis(
    [os.path.join(spec_dir, 'quiz_builder_cli.py')],
    pathex=[repo_root, spec_dir],
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
