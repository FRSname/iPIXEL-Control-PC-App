# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Qt iPixel Controller.

Build:
    python build_exe.py

or directly:
    pyinstaller --noconfirm iPixelController.spec
"""

import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# ---------------------------------------------------------------- assets
# Ship the runtime assets next to the exe.
datas = []
for d in ("Gallery", "playlists"):
    if os.path.isdir(d):
        datas.append((d, d))

# Ship default config so first launch has something to work with.
for f in ("ipixel_settings.json", "ipixel_presets.json"):
    if os.path.isfile(f):
        datas.append((f, "."))

# Pull in pypixelcolor / bleak / google client data files automatically.
for pkg in ("pypixelcolor", "bleak"):
    try:
        datas += collect_data_files(pkg)
    except Exception:
        pass

# -------------------------------------------------------- hidden imports
hiddenimports = []
for mod in (
    "pypixelcolor",
    "bleak",
    "bleak.backends",
    "bleak.backends.winrt",
    "PIL",
    "PIL._imagingtk",
    "googleapiclient",
    "googleapiclient.discovery",
    "yfinance",
    "numpy",
    "requests",
):
    try:
        hiddenimports += collect_submodules(mod)
    except Exception:
        hiddenimports.append(mod)

hiddenimports += [
    "ipixel_controller.qt",
    "ipixel_controller.qt.app",
    "ipixel_controller.qt.main_window",
    "ipixel_controller.core",
    "ipixel_controller.services",
]

# Optional embedded browser for the Draw tab. Pulled in best-effort so
# builds work even if the user skipped PySide6-Addons.
for pkg in ("PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineCore"):
    try:
        hiddenimports += collect_submodules(pkg)
    except Exception:
        pass

# --------------------------------------------------------------- analysis
a = Analysis(
    ["run_qt.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # The legacy Tkinter UI ships in the same package; the Qt build
        # doesn't need Tk runtime. Drop it to shrink the bundle.
        "tkinter",
        "_tkinter",
        "tkinter.ttk",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Optional icon — fall back gracefully if missing.
_icon_candidates = ["app.ico", "Gallery/app.ico"]
_icon = next((p for p in _icon_candidates if os.path.isfile(p)), None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="iPixelController",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,         # GUI app — no console window
    icon=_icon,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="iPixelController",
)
