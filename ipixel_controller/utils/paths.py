"""
Path resolution utilities.

Handles resolving relative paths to absolute paths, finding the app directory,
and other path-related operations.
"""

import os
import sys
from typing import Optional


def get_app_dir() -> str:
    """
    Get the application's base directory.

    Works correctly whether running as a script or as a frozen executable.

    Returns:
        Absolute path to the application directory
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return os.path.dirname(sys.executable)
    else:
        # Running as script - go up from utils/ to package root, then to app root
        package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # If we're in ipixel_controller/, go up one more level
        if os.path.basename(package_dir) == 'ipixel_controller':
            return os.path.dirname(package_dir)
        else:
            return package_dir


def resolve_asset_path(path_value: str, base_dir: Optional[str] = None) -> str:
    """
    Resolve a potentially relative path to an absolute path.

    Handles:
    - Absolute paths (returned as-is)
    - Relative paths (resolved relative to base_dir or app directory)
    - User home directory expansion (~)
    - Empty paths (returns empty string)

    Args:
        path_value: The path to resolve (can be relative or absolute)
        base_dir: Base directory for relative paths (defaults to app directory)

    Returns:
        Absolute path string
    """
    if not path_value:
        return ""

    # Expand user home directory
    path_value = os.path.expanduser(path_value)

    # If already absolute, return as-is
    if os.path.isabs(path_value):
        return os.path.normpath(path_value)

    # Resolve relative to base directory
    if base_dir is None:
        base_dir = get_app_dir()

    return os.path.normpath(os.path.join(base_dir, path_value))


def get_gallery_dir() -> str:
    """
    Get the path to the Gallery directory containing assets.

    Returns:
        Absolute path to the Gallery directory
    """
    return os.path.join(get_app_dir(), "Gallery")


def get_sprites_dir() -> str:
    """
    Get the path to the Sprites directory containing sprite sheets.

    Returns:
        Absolute path to the Gallery/Sprites directory
    """
    return os.path.join(get_gallery_dir(), "Sprites")


def get_weather_dir() -> str:
    """
    Get the path to the Weather assets directory.

    Returns:
        Absolute path to the Gallery/Weather directory
    """
    return os.path.join(get_gallery_dir(), "Weather")


def ensure_dir_exists(path: str) -> str:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path to create

    Returns:
        The same path (for chaining)
    """
    os.makedirs(path, exist_ok=True)
    return path


def get_temp_path(filename: str) -> str:
    """
    Get a path in the system temp directory.

    Args:
        filename: Name for the temp file

    Returns:
        Full path to the temp file
    """
    import tempfile
    return os.path.join(tempfile.gettempdir(), filename)


def is_valid_image_path(path: str) -> bool:
    """
    Check if a path points to a valid image file.

    Args:
        path: Path to check

    Returns:
        True if path exists and has an image extension
    """
    if not path or not os.path.isfile(path):
        return False

    valid_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp'}
    _, ext = os.path.splitext(path.lower())
    return ext in valid_extensions
