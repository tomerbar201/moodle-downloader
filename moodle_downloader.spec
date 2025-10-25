# -*- mode: python ; coding: utf-8 -*-
import os, sys
from PyInstaller.utils.hooks import collect_data_files

# __file__ is not guaranteed inside exec() when PyInstaller loads the spec.
# Use working directory (where the spec resides when invoked) as base.
current_dir = os.path.abspath('.')
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

block_cipher = None

# Ensure Playwright's bundled driver (node + CLI) ships inside the executable.
datas = collect_data_files('playwright', includes=['driver/**'])

hiddenimports = [
    'playwright', 'playwright.sync_api',
    'playwright._impl._browser_type', 'playwright._impl._connection', 'playwright._impl._page',
    'playwright._impl._browser_context', 'playwright._impl._driver', 'playwright._impl._api_structures',
    'playwright._impl._errors', 'playwright._impl._helper', 'playwright._impl._api_types',
    'PyQt5', 'PyQt5.QtWidgets', 'PyQt5.QtCore', 'PyQt5.QtGui',
    'bs4', 'lxml', 'keyring', 'keyring.backends', 'keyring.backends.Windows',
]

a = Analysis(
    ['run_gui.py'],
    pathex=[current_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[current_dir],
    hooksconfig={},
    runtime_hooks=['src/playwright_runtime_hook.py'],
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
    name='MoodleDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='MoodleIcon.ico',
)