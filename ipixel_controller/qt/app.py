"""Qt application bootstrap.

Run with one of:

    python -m ipixel_controller.qt
    python run_qt.py

Once PyInstaller bundles the app, the spec uses :func:`main` as the
entry point.
"""

from __future__ import annotations

import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from ..core.config import ConfigManager
from ..core.events import EventBus
from .main_window import MainWindow
from .theme import STYLESHEET


def _ensure_cwd() -> None:
    """When launched from a frozen bundle the cwd may be elsewhere.

    The app reads relative assets (``Gallery/``, JSON config). Switch to
    the directory that contains those at startup.
    """
    if getattr(sys, "frozen", False):
        bundle_dir = os.path.dirname(sys.executable)
        if os.path.exists(os.path.join(bundle_dir, "ipixel_settings.json")) or \
           os.path.exists(os.path.join(bundle_dir, "Gallery")):
            os.chdir(bundle_dir)


def run() -> int:
    _ensure_cwd()

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("iPixel Controller")
    app.setOrganizationName("iPixel")
    app.setStyleSheet(STYLESHEET)

    events = EventBus()
    config = ConfigManager(events=events)
    config.load_settings()
    config.load_presets()
    config.load_secrets()

    window = MainWindow(config=config, events=events)
    window.show()

    return app.exec()


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
