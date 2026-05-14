#!/usr/bin/env python3
"""Launcher for the new PySide6 UI.

Use this during development; the PyInstaller build calls into the same
``ipixel_controller.qt.app.main`` entry point.
"""

import os
import sys

# Ensure the repo root is on sys.path when invoked from elsewhere.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from ipixel_controller.qt.app import main

if __name__ == "__main__":
    main()
