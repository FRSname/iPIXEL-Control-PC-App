"""Core infrastructure modules.

Only framework-agnostic modules are re-exported here. ``TimerManager``
(in ``timers``) and ``DeviceManager`` (in ``device``) are Tkinter-bound
and must be imported directly — re-exporting them through the package
makes the Qt UI pull in the Tk runtime as a side effect of importing
``core.config`` or ``core.events``, which breaks PyInstaller builds
that exclude Tk.
"""

from .state import AppState, ConnectionStatus, DeviceInfo
from .events import EventBus, Events
from .config import ConfigManager, ConfigPaths

__all__ = [
    'AppState',
    'ConnectionStatus',
    'DeviceInfo',
    'EventBus',
    'Events',
    'ConfigManager',
    'ConfigPaths',
]
