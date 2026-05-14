"""PySide6 (Qt) UI for iPixel Controller.

This package replaces the legacy Tkinter UI under ``ipixel_controller.ui``.
The Tkinter UI and the monolithic ``ipixel_controller.py`` remain in the
repository during the migration window; they will be removed once every
feature has been ported to the Qt UI.
"""

from .app import main, run

__all__ = ["main", "run"]
