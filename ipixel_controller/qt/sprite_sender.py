"""Render text with a sprite font and send it to the panel.

Encapsulates the static-render and scroll-text paths that every
text-based feature needs (Text, Clock, Stock, YouTube, Weather). Each
caller gets a :class:`SpriteSender` configured with the device bridge
and font service; calling :meth:`send_static` or :meth:`start_scroll`
renders to a temp image and dispatches to the panel via
``device.send_image`` — which respects custom background colours (unlike
the built-in ``send_text`` firmware path).

A scroll session is owned by the SpriteSender instance: starting a new
one cancels the previous one, so feature pages don't have to coordinate
QTimer lifetimes themselves.
"""

from __future__ import annotations

from typing import Optional

from PIL import Image
from PySide6.QtCore import QObject, QTimer

from ..services.sprite_font import SpriteFontService
from ..utils.image_utils import save_temp_image
from .device_bridge import DeviceBridge


PANEL_W = 64
PANEL_H = 16


class SpriteSender(QObject):
    """Per-page sprite renderer with a single owned QTimer for scrolling."""

    def __init__(
        self,
        device: DeviceBridge,
        font_service: SpriteFontService,
        temp_basename: str = "ipixel_sprite.png",
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._device = device
        self._fonts = font_service
        self._temp_name = temp_basename

        self._scroll_timer = QTimer(self)
        self._scroll_timer.timeout.connect(self._scroll_tick)

        self._scroll_img: Optional[Image.Image] = None
        self._scroll_offset = 0
        self._scroll_step = 1
        self._scroll_max = 0
        self._scroll_bg = "#000000"

    # ------------------------------------------------------------- lifecycle
    def stop(self) -> None:
        """Cancel any in-progress scroll."""
        self._scroll_timer.stop()
        self._scroll_img = None

    # ---------------------------------------------------------------- static
    def send_static(self, text: str, font_name: str, bg_color: str) -> Optional[str]:
        """Render ``text`` centred on a 64×16 canvas and send it.

        Returns ``None`` on success, or an error string the caller can show.
        """
        self.stop()
        img, error = self._fonts.render_text_fixed(text, font_name, bg_color)
        if error or img is None:
            return error or "Sprite render failed"
        self._dispatch(img)
        return None

    # --------------------------------------------------------------- scroll
    def start_scroll(
        self,
        text: str,
        font_name: str,
        bg_color: str,
        speed: int = 50,
        reverse: bool = False,
    ) -> Optional[str]:
        """Scroll ``text`` continuously across the panel.

        ``speed`` is 1..100 (UI scale); converted to a per-frame delay.
        If the rendered text already fits in the panel, falls back to a
        single static send (no animation).
        """
        self.stop()
        line, error = self._fonts.render_text_line(text, font_name, bg_color)
        if error or line is None:
            return error or "Sprite render failed"

        # Pad with a few empty columns so the wrap doesn't look abrupt.
        padded = Image.new(line.mode, (line.width + 8, line.height), bg_color)
        padded.paste(line, (0, 0), line if line.mode == "RGBA" else None)

        if padded.height != PANEL_H:
            scale = PANEL_H / padded.height
            padded = padded.resize(
                (max(1, int(padded.width * scale)), PANEL_H), Image.NEAREST
            )

        if padded.width <= PANEL_W:
            # Fits — send once and stop.
            canvas = Image.new(padded.mode, (PANEL_W, PANEL_H), bg_color)
            offset_x = (PANEL_W - padded.width) // 2
            canvas.paste(padded, (offset_x, 0), padded if padded.mode == "RGBA" else None)
            self._dispatch(canvas)
            return None

        self._scroll_img = padded
        self._scroll_max = padded.width - PANEL_W
        self._scroll_bg = bg_color
        self._scroll_step = -1 if reverse else 1
        self._scroll_offset = self._scroll_max if reverse else 0
        # speed 1..100  →  ~220..20 ms / frame
        speed = max(1, min(100, speed))
        interval = max(20, 220 - speed * 2)
        self._scroll_tick()  # send first frame immediately
        self._scroll_timer.start(interval)
        return None

    def _scroll_tick(self) -> None:
        if self._scroll_img is None:
            self._scroll_timer.stop()
            return
        img = self._scroll_img
        crop = img.crop(
            (self._scroll_offset, 0, self._scroll_offset + PANEL_W, img.height)
        )
        self._dispatch(crop)
        self._scroll_offset += self._scroll_step
        if self._scroll_offset > self._scroll_max:
            self._scroll_offset = 0
        elif self._scroll_offset < 0:
            self._scroll_offset = self._scroll_max

    # --------------------------------------------------------------- helpers
    def _dispatch(self, img: Image.Image) -> None:
        if img.mode != "RGB":
            img = img.convert("RGB")
        path = save_temp_image(img, self._temp_name)
        self._device.send_image(path, resize_method="crop", save_slot=0)
