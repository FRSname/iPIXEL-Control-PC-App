#!/usr/bin/env python3
"""One-shot Windows build script.

Installs PyInstaller if needed, runs the spec, then offers to create a
Start Menu shortcut pointing at the built exe so the app launches like
any other Windows program — no terminal.

Usage:
    python build_exe.py            # build + shortcut prompt
    python build_exe.py --no-shortcut
    python build_exe.py --clean    # wipe build/ and dist/ first
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SPEC = ROOT / "iPixelController.spec"
DIST = ROOT / "dist" / "iPixelController"
EXE = DIST / "iPixelController.exe"


def _ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller not found — installing...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pyinstaller"]
        )


def _ensure_pyside6() -> None:
    try:
        import PySide6  # noqa: F401
    except ImportError:
        print("PySide6 not found — installing dependencies from requirements.txt...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")]
        )


def _clean() -> None:
    for d in ("build", "dist"):
        p = ROOT / d
        if p.exists():
            print(f"Removing {p}")
            shutil.rmtree(p, ignore_errors=True)


def _build() -> None:
    print(f"Building from {SPEC.name}...")
    subprocess.check_call(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", str(SPEC)],
        cwd=str(ROOT),
    )


def _create_shortcut() -> None:
    """Create a Start Menu shortcut on Windows via PowerShell + WScript.Shell."""
    if os.name != "nt":
        print("Skipping shortcut: not on Windows.")
        return
    if not EXE.exists():
        print(f"Skipping shortcut: {EXE} not found.")
        return

    start_menu = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    if not start_menu.exists():
        print("Skipping shortcut: Start Menu Programs folder not found.")
        return

    link = start_menu / "iPixel Controller.lnk"
    target = str(EXE)
    workdir = str(EXE.parent)

    ps = (
        f"$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{link}'); "
        f"$s.TargetPath = '{target}'; "
        f"$s.WorkingDirectory = '{workdir}'; "
        f"$s.IconLocation = '{target},0'; "
        f"$s.Save();"
    )
    try:
        subprocess.check_call(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps]
        )
        print(f"Created Start Menu shortcut: {link}")
    except subprocess.CalledProcessError as e:
        print(f"Shortcut creation failed: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build iPixel Controller exe")
    parser.add_argument("--clean", action="store_true", help="Wipe build/ and dist/ first")
    parser.add_argument("--no-shortcut", action="store_true", help="Skip Start Menu shortcut")
    args = parser.parse_args()

    _ensure_pyside6()
    _ensure_pyinstaller()
    if args.clean:
        _clean()
    _build()

    if EXE.exists():
        print(f"\nBuild complete: {EXE}")
        if not args.no_shortcut:
            answer = input("Create Start Menu shortcut? [Y/n]: ").strip().lower()
            if answer in ("", "y", "yes"):
                _create_shortcut()
    else:
        print("Build finished but exe not found — check PyInstaller output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
