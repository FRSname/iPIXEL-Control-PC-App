"""
Sprite font service for rendering text using sprite sheets.

Provides functionality to render text as images using sprite sheet fonts,
with support for both static and scrolling text.
"""

import math
import os
from typing import Dict, List, Optional, Tuple, Any
from PIL import Image

from ..utils.paths import resolve_asset_path


# Default display dimensions
DEFAULT_WIDTH = 64
DEFAULT_HEIGHT = 16

# Default glyph orders
TEXT_GLYPH_ORDER = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:!?.,+-/$% '
CLOCK_GLYPH_ORDER = '0123456789:'


class SpriteFont:
    """
    Represents a sprite font loaded from a sprite sheet.

    A sprite font is a single image containing all character glyphs
    arranged in a grid. Each glyph is cropped and cached for fast
    text rendering.
    """

    def __init__(
        self,
        name: str,
        path: str,
        order: str,
        cols: int
    ):
        """
        Initialize a sprite font.

        Args:
            name: Display name for this font
            path: Path to the sprite sheet image
            order: String of characters in order as they appear in the sprite
            cols: Number of columns in the sprite sheet grid
        """
        self.name = name
        self.path = path
        self.order = order
        self.cols = max(1, cols)
        self._sprite: Optional[Image.Image] = None
        self._glyphs: Dict[str, Image.Image] = {}
        self._tile_size: Tuple[int, int] = (0, 0)
        self._loaded = False
        self._error: Optional[str] = None

    def load(self) -> bool:
        """
        Load the sprite sheet and extract glyphs.

        Returns:
            True if loaded successfully, False otherwise
        """
        if self._loaded:
            return self._error is None

        resolved_path = resolve_asset_path(self.path)
        if not resolved_path or not os.path.isfile(resolved_path):
            self._error = "Sprite sheet not found"
            self._loaded = True
            return False

        order = (self.order or "").strip()
        if not order:
            self._error = "Glyph order is empty"
            self._loaded = True
            return False

        try:
            self._sprite = Image.open(resolved_path).convert("RGBA")
        except Exception as e:
            self._error = f"Sprite load failed: {e}"
            self._loaded = True
            return False

        # Calculate tile dimensions
        rows = max(1, math.ceil(len(order) / self.cols))
        tile_w = max(1, self._sprite.width // self.cols)
        tile_h = max(1, self._sprite.height // rows)
        self._tile_size = (tile_w, tile_h)

        # Extract glyphs
        for idx, ch in enumerate(order):
            row = idx // self.cols
            col = idx % self.cols
            left = col * tile_w
            upper = row * tile_h
            right = left + tile_w
            lower = upper + tile_h
            if right <= self._sprite.width and lower <= self._sprite.height:
                self._glyphs[ch] = self._sprite.crop((left, upper, right, lower))

        if not self._glyphs:
            self._error = "No glyphs found in sprite sheet"
            self._loaded = True
            return False

        self._loaded = True
        return True

    def get_glyph(self, char: str) -> Optional[Image.Image]:
        """
        Get the glyph image for a character.

        Falls back to uppercase if lowercase not found.

        Args:
            char: Character to get glyph for

        Returns:
            Glyph image or None if not found
        """
        if not self._loaded:
            self.load()

        glyph = self._glyphs.get(char)
        if glyph is None:
            glyph = self._glyphs.get(char.upper())
        return glyph

    @property
    def tile_width(self) -> int:
        """Get the width of each glyph tile."""
        if not self._loaded:
            self.load()
        return self._tile_size[0]

    @property
    def tile_height(self) -> int:
        """Get the height of each glyph tile."""
        if not self._loaded:
            self.load()
        return self._tile_size[1]

    @property
    def error(self) -> Optional[str]:
        """Get any error that occurred during loading."""
        return self._error

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'name': self.name,
            'path': self.path,
            'order': self.order,
            'cols': self.cols
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SpriteFont':
        """Create from dictionary."""
        return cls(
            name=data.get('name', ''),
            path=data.get('path', ''),
            order=data.get('order', TEXT_GLYPH_ORDER),
            cols=data.get('cols', 1)
        )


class SpriteFontService:
    """
    Service for managing sprite fonts and rendering text.

    Provides centralized font management and text rendering functionality
    extracted from the original monolithic controller.
    """

    def __init__(self):
        """Initialize the sprite font service."""
        self._fonts: Dict[str, SpriteFont] = {}

    def register_font(self, font: SpriteFont) -> None:
        """
        Register a sprite font.

        Args:
            font: SpriteFont instance to register
        """
        self._fonts[font.name] = font

    def register_fonts_from_settings(self, font_list: List[Dict[str, Any]]) -> None:
        """
        Register fonts from settings dictionary list.

        Args:
            font_list: List of font dictionaries from settings
        """
        for font_data in font_list:
            font = SpriteFont.from_dict(font_data)
            self.register_font(font)

    def get_font(self, name: str) -> Optional[SpriteFont]:
        """
        Get a font by name.

        Args:
            name: Font name to look up

        Returns:
            SpriteFont or None if not found
        """
        return self._fonts.get(name)

    def get_font_names(self) -> List[str]:
        """Get list of all registered font names."""
        return list(self._fonts.keys())

    def render_text_line(
        self,
        text: str,
        font_name: str,
        bg_color: str = "#000000"
    ) -> Tuple[Optional[Image.Image], Optional[str]]:
        """
        Render text as a single line image (variable width).

        Used for scrolling text where the full text width is needed.

        Args:
            text: Text to render
            font_name: Name of the sprite font to use
            bg_color: Background color (hex string)

        Returns:
            Tuple of (PIL Image, error message or None)
        """
        font = self.get_font(font_name)
        if not font:
            return None, f"Font '{font_name}' not found"

        if not font.load():
            return None, font.error

        chars = list(text)
        total_w = font.tile_width * len(chars)

        if total_w == 0:
            return None, "No characters to render"

        base = Image.new("RGBA", (total_w, font.tile_height), bg_color)

        x = 0
        for ch in chars:
            glyph = font.get_glyph(ch)
            if glyph is None:
                # Skip unknown characters but advance position
                x += font.tile_width
                continue
            base.paste(glyph, (x, 0), glyph)
            x += font.tile_width

        return base.convert("RGB"), None

    def render_text_fixed(
        self,
        text: str,
        font_name: str,
        bg_color: str = "#000000",
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT
    ) -> Tuple[Optional[Image.Image], Optional[str]]:
        """
        Render text to a fixed-size image (default 64x16).

        Text is scaled to fit and centered on the canvas.

        Args:
            text: Text to render
            font_name: Name of the sprite font to use
            bg_color: Background color (hex string)
            width: Target width
            height: Target height

        Returns:
            Tuple of (PIL Image, error message or None)
        """
        # First render as line
        line_img, error = self.render_text_line(text, font_name, bg_color)
        if error:
            return None, error

        # Scale to fit
        if line_img.size != (width, height):
            scale = min(width / line_img.width, height / line_img.height)
            new_w = max(1, int(line_img.width * scale))
            new_h = max(1, int(line_img.height * scale))
            resized = line_img.resize((new_w, new_h), Image.NEAREST)

            # Center on canvas
            canvas = Image.new("RGBA", (width, height), bg_color)
            offset_x = (width - new_w) // 2
            offset_y = (height - new_h) // 2
            canvas.paste(resized, (offset_x, offset_y))
            line_img = canvas

        return line_img.convert("RGB"), None

    def render_text(
        self,
        text: str,
        sprite_path: str,
        order: str,
        cols: int,
        bg_color: str,
        fixed_size: bool = True
    ) -> Tuple[Optional[Image.Image], Optional[str]]:
        """
        Render text using raw sprite parameters (legacy compatibility).

        Args:
            text: Text to render
            sprite_path: Path to sprite sheet
            order: Glyph order string
            cols: Number of columns
            bg_color: Background color
            fixed_size: If True, return 64x16 image; otherwise variable width

        Returns:
            Tuple of (PIL Image, error message or None)
        """
        # Create temporary font
        temp_font = SpriteFont(
            name="_temp",
            path=sprite_path,
            order=order,
            cols=cols
        )
        self._fonts["_temp"] = temp_font

        try:
            if fixed_size:
                return self.render_text_fixed(text, "_temp", bg_color)
            else:
                return self.render_text_line(text, "_temp", bg_color)
        finally:
            # Clean up temp font
            del self._fonts["_temp"]


def speed_to_interval_ms(speed: int) -> int:
    """
    Convert speed value (1-100) to scroll interval in milliseconds.

    Higher speed values result in shorter intervals (faster scrolling).

    Args:
        speed: Speed value from 1 (slowest) to 100 (fastest)

    Returns:
        Interval in milliseconds
    """
    # Clamp speed to valid range
    speed = max(1, min(100, speed))
    # Speed 1 = 220ms, Speed 100 = 20ms
    return max(20, 220 - speed * 2)
