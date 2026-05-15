"""
Configuration manager for settings, presets, and secrets.

Provides centralized management of all configuration files with
automatic loading and saving.
"""

import json
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from .events import EventBus, Events
from ..utils.paths import get_app_dir, get_asset_dir


# Default file names
SETTINGS_FILE = "ipixel_settings.json"
PRESETS_FILE = "ipixel_presets.json"
SECRETS_FILE = "ipixel_secrets.json"


@dataclass
class ConfigPaths:
    """Configuration file paths.

    Each file has a primary, user-writable location under :func:`get_app_dir`
    (the exe folder in frozen builds, repo root in dev). In a PyInstaller
    bundle there's also a read-only seed copy under :func:`get_asset_dir`
    (the ``_internal`` directory). On first run we copy the seed across so
    bundled defaults (sprite fonts, factory presets) are available without
    forcing the user to ship two copies.
    """
    settings: str = ""
    presets: str = ""
    secrets: str = ""

    def __post_init__(self):
        app_dir = get_app_dir()
        if not self.settings:
            self.settings = os.path.join(app_dir, SETTINGS_FILE)
        if not self.presets:
            self.presets = os.path.join(app_dir, PRESETS_FILE)
        if not self.secrets:
            self.secrets = os.path.join(app_dir, SECRETS_FILE)

    def seed_from_bundle(self) -> None:
        """Copy bundled defaults into the user-writable location.

        No-op in dev (asset_dir == app_dir → same file). In a frozen
        bundle, settings and presets get seeded; secrets never do (they
        contain API keys that must stay user-supplied).
        """
        asset_dir = get_asset_dir()
        app_dir = get_app_dir()
        if os.path.normcase(asset_dir) == os.path.normcase(app_dir):
            return
        for primary, name in (
            (self.settings, SETTINGS_FILE),
            (self.presets, PRESETS_FILE),
        ):
            if os.path.isfile(primary):
                continue
            bundled = os.path.join(asset_dir, name)
            if os.path.isfile(bundled):
                try:
                    import shutil
                    shutil.copyfile(bundled, primary)
                except Exception as e:
                    print(f"Failed to seed {name} from bundle: {e}")


class ConfigManager:
    """
    Centralized configuration management.

    Handles loading, saving, and accessing settings, presets, and secrets.
    Publishes events when configuration changes.

    Features:
    - Lazy loading of configuration files
    - Automatic default value merging
    - Type-safe access methods
    - Event publishing on changes
    """

    # Default settings
    DEFAULT_SETTINGS = {
        'auto_connect': True,
        'restore_last_state': True,
        'last_device': None,
        'last_preset': None,

        # Sprite font settings
        'text_use_sprite_font': False,
        'text_sprite_font_name': 'Text Default',
        'clock_use_time_sprite': False,
        'clock_time_sprite_font_name': 'Clock Default',
        'countdown_use_sprite_font': False,
        'countdown_sprite_font_name': 'Text Default',
        'stock_use_sprite_font': True,
        'stock_sprite_font_name': 'Text Default',
        'youtube_use_sprite_font': True,
        'youtube_sprite_font_name': 'Text Default',
        'instagram_use_sprite_font': True,
        'instagram_sprite_font_name': 'Text Default',
        'instagram_layout': 'icon',
        'instagram_animate_changes': True,

        # Display delays
        'text_static_delay_seconds': 2,
        'countdown_static_delay_seconds': 2,
        'stock_static_delay_seconds': 2,
        'youtube_logo_delay_seconds': 2,

        # YouTube settings
        'youtube_show_logo': True,
        'youtube_logo_path': 'Gallery/Sprites/YT-btn.png',

        # Weather settings
        'weather_use_temp_images': False,
        'weather_temp_image_dir': 'Gallery/Weather',

        # Sprite fonts list
        'sprite_fonts': [],
    }

    # Default secrets
    DEFAULT_SECRETS = {
        'youtube_api_key': '',
        'weather_api_key': '',
        'ig_user_id': '',
        'ig_access_token': '',
        'ig_app_id': '',
        'ig_app_secret': '',
    }

    def __init__(
        self,
        events: Optional[EventBus] = None,
        paths: Optional[ConfigPaths] = None
    ):
        """
        Initialize the configuration manager.

        Args:
            events: Optional event bus for publishing changes
            paths: Optional custom configuration paths
        """
        self._events = events
        self._paths = paths or ConfigPaths()
        # Copy bundled defaults to the user-writable location on first run
        # of a frozen build. No-op in dev.
        self._paths.seed_from_bundle()

        self._settings: Dict[str, Any] = {}
        self._presets: List[Dict[str, Any]] = []
        self._secrets: Dict[str, Any] = {}

        self._settings_loaded = False
        self._presets_loaded = False
        self._secrets_loaded = False

    # Settings Management

    def load_settings(self) -> Dict[str, Any]:
        """
        Load settings from file.

        Returns:
            Settings dictionary
        """
        if self._settings_loaded:
            return self._settings

        self._settings = self._load_json(
            self._paths.settings,
            self.DEFAULT_SETTINGS.copy()
        )
        self._settings_loaded = True

        # Ensure all default keys exist
        for key, value in self.DEFAULT_SETTINGS.items():
            self._settings.setdefault(key, value)

        return self._settings

    def save_settings(self) -> bool:
        """
        Save settings to file.

        Returns:
            True if successful
        """
        result = self._save_json(self._paths.settings, self._settings)
        if result and self._events:
            self._events.publish(Events.SETTINGS_CHANGED, self._settings)
        return result

    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value.

        Args:
            key: Setting key
            default: Default value if not found

        Returns:
            Setting value
        """
        self.load_settings()
        return self._settings.get(key, default)

    def set_setting(self, key: str, value: Any, save: bool = True) -> None:
        """
        Set a setting value.

        Args:
            key: Setting key
            value: New value
            save: Whether to save immediately
        """
        self.load_settings()
        self._settings[key] = value
        if save:
            self.save_settings()

    @property
    def settings(self) -> Dict[str, Any]:
        """Get all settings."""
        return self.load_settings()

    # Presets Management

    def load_presets(self) -> List[Dict[str, Any]]:
        """
        Load presets from file.

        Returns:
            List of preset dictionaries
        """
        if self._presets_loaded:
            return self._presets

        data = self._load_json(self._paths.presets, [])
        self._presets = data if isinstance(data, list) else []
        self._presets_loaded = True
        return self._presets

    def save_presets(self) -> bool:
        """
        Save presets to file.

        Returns:
            True if successful
        """
        result = self._save_json(self._paths.presets, self._presets)
        if result and self._events:
            self._events.publish(Events.PRESETS_CHANGED, self._presets)
        return result

    def add_preset(self, preset: Dict[str, Any]) -> None:
        """
        Add a new preset.

        Args:
            preset: Preset dictionary
        """
        self.load_presets()
        self._presets.append(preset)
        self.save_presets()
        if self._events:
            self._events.publish(Events.PRESET_SAVED, preset)

    def delete_preset(self, index: int) -> bool:
        """
        Delete a preset by index.

        Args:
            index: Preset index

        Returns:
            True if deleted successfully
        """
        self.load_presets()
        if 0 <= index < len(self._presets):
            deleted = self._presets.pop(index)
            self.save_presets()
            if self._events:
                self._events.publish(Events.PRESET_DELETED, deleted)
            return True
        return False

    def get_preset_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a preset by name.

        Args:
            name: Preset name

        Returns:
            Preset dictionary or None
        """
        self.load_presets()
        for preset in self._presets:
            if preset.get('name') == name:
                return preset
        return None

    @property
    def presets(self) -> List[Dict[str, Any]]:
        """Get all presets."""
        return self.load_presets()

    def get_presets(self) -> List[Dict[str, Any]]:
        """
        Get all presets (method form).

        Returns:
            List of preset dictionaries
        """
        return self.load_presets()

    def update_preset(self, index: int, preset: Dict[str, Any]) -> bool:
        """
        Update a preset by index.

        Args:
            index: Preset index
            preset: New preset data

        Returns:
            True if updated successfully
        """
        self.load_presets()
        if 0 <= index < len(self._presets):
            self._presets[index] = preset
            self.save_presets()
            return True
        return False

    def remove_preset(self, index: int) -> bool:
        """
        Remove a preset by index (alias for delete_preset).

        Args:
            index: Preset index

        Returns:
            True if removed successfully
        """
        return self.delete_preset(index)

    # Secrets Management

    def load_secrets(self) -> Dict[str, Any]:
        """
        Load secrets from file.

        Returns:
            Secrets dictionary
        """
        if self._secrets_loaded:
            return self._secrets

        self._secrets = self._load_json(
            self._paths.secrets,
            self.DEFAULT_SECRETS.copy()
        )
        self._secrets_loaded = True
        return self._secrets

    def save_secrets(self) -> bool:
        """
        Save secrets to file.

        Returns:
            True if successful
        """
        return self._save_json(self._paths.secrets, self._secrets)

    def get_secret(self, key: str, default: str = "") -> str:
        """
        Get a secret value.

        Args:
            key: Secret key
            default: Default value if not found

        Returns:
            Secret value
        """
        self.load_secrets()
        return self._secrets.get(key, default)

    def set_secret(self, key: str, value: str, save: bool = True) -> None:
        """
        Set a secret value.

        Args:
            key: Secret key
            value: New value
            save: Whether to save immediately
        """
        self.load_secrets()
        self._secrets[key] = value
        if save:
            self.save_secrets()

    @property
    def secrets(self) -> Dict[str, Any]:
        """Get all secrets."""
        return self.load_secrets()

    # Sprite Fonts Management

    def get_sprite_fonts(self) -> List[Dict[str, Any]]:
        """
        Get list of sprite fonts.

        Returns:
            List of sprite font dictionaries
        """
        return self.get_setting('sprite_fonts', [])

    def set_sprite_fonts(self, fonts: List[Dict[str, Any]]) -> None:
        """
        Set sprite fonts list.

        Args:
            fonts: List of sprite font dictionaries
        """
        self.set_setting('sprite_fonts', fonts)
        if self._events:
            self._events.publish(Events.SPRITE_FONTS_CHANGED, fonts)

    def get_sprite_font_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a sprite font by name.

        Args:
            name: Font name

        Returns:
            Font dictionary or None
        """
        for font in self.get_sprite_fonts():
            if font.get('name') == name:
                return font
        return None

    def get_sprite_font_names(self) -> List[str]:
        """
        Get list of sprite font names.

        Returns:
            List of font names
        """
        return [f.get('name', '') for f in self.get_sprite_fonts()]

    def add_sprite_font(self, font: Dict[str, Any]) -> None:
        """
        Add a new sprite font.

        Args:
            font: Font dictionary with name, path, order, cols
        """
        fonts = self.get_sprite_fonts()
        fonts.append(font)
        self.set_sprite_fonts(fonts)

    def update_sprite_font(self, index: int, font: Dict[str, Any]) -> bool:
        """
        Update a sprite font by index.

        Args:
            index: Font index
            font: New font data

        Returns:
            True if updated successfully
        """
        fonts = self.get_sprite_fonts()
        if 0 <= index < len(fonts):
            fonts[index] = font
            self.set_sprite_fonts(fonts)
            return True
        return False

    def remove_sprite_font(self, index: int) -> bool:
        """
        Remove a sprite font by index.

        Args:
            index: Font index

        Returns:
            True if removed successfully
        """
        fonts = self.get_sprite_fonts()
        if 0 <= index < len(fonts):
            fonts.pop(index)
            self.set_sprite_fonts(fonts)
            return True
        return False

    # Helper Methods

    def _load_json(self, path: str, default: Any) -> Any:
        """Load JSON file with default fallback."""
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Failed to load {path}: {e}")
        return default

    def _save_json(self, path: str, data: Any) -> bool:
        """Save data to JSON file."""
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Failed to save {path}: {e}")
            return False

    def reload_all(self) -> None:
        """Force reload of all configuration files."""
        self._settings_loaded = False
        self._presets_loaded = False
        self._secrets_loaded = False
        self.load_settings()
        self.load_presets()
        self.load_secrets()
