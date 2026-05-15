"""Instagram follower-count feature, PySide6.

Pulls live follower count from the Instagram Graph API in a worker thread.
Credentials persist in ``ipixel_secrets.json`` via ``ConfigManager``.

Needs a Facebook app + IG Business/Creator account linked to a Facebook
Page. See README for the one-time token-generation walkthrough.
"""

from __future__ import annotations

import math
import os
from typing import Any, Dict, Optional

from PIL import Image
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
)

from ...services.sprite_font import SpriteFontService
from ...services.instagram_service import (
    fetch_follower_count,
    format_instagram_display,
    refresh_long_lived_token,
)
from ...utils.image_utils import save_temp_image
from ...utils.paths import resolve_asset_path
from ..device_bridge import DeviceBridge
from ..fetcher import BackgroundFetcher
from ..sprite_sender import SpriteSender
from ..widgets import Card, ColorButton, SpriteFontPicker
from .base import Page


FORMATS = [
    ("Count (short, e.g. 1.4K)", "count_short"),
    ("Count (full)", "count_full"),
    ("@handle + count", "username_count"),
    ("Name + count", "name_count"),
    ("FOLLOWERS + count", "followers_label"),
]

LAYOUT_ICON = "icon"
LAYOUT_TEXT = "text"
LAYOUTS = [
    ("Instagram icon + count", LAYOUT_ICON),
    ("Text only", LAYOUT_TEXT),
]

INSTAGRAM_ICON_PATH = os.path.join("Gallery", "Sprites", "Instagram.png")


class InstagramPage(Page):
    title = "Instagram"
    subtitle = "Live follower count for an IG Business / Creator account."
    feature_id = "instagram"

    def __init__(self, device: DeviceBridge, config, fonts: SpriteFontService) -> None:
        super().__init__()
        self._device = device
        self._config = config
        self._fonts = fonts
        self._sender = SpriteSender(device, fonts, temp_basename="ipixel_instagram.png")
        self._current: Optional[Dict[str, Any]] = None

        self._fetcher = BackgroundFetcher(fetch_follower_count)
        self._fetcher.started.connect(lambda: self._set_status("Fetching…"))
        self._fetcher.succeeded.connect(self._on_data)
        self._fetcher.failed.connect(self._on_error)

        self._token_fetcher = BackgroundFetcher(refresh_long_lived_token)
        self._token_fetcher.started.connect(
            lambda: self._set_status("Refreshing token…")
        )
        self._token_fetcher.succeeded.connect(self._on_token_refreshed)
        self._token_fetcher.failed.connect(self._on_error)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._auto_refresh)

        # Animation state — frame queue + timer for transitioning the
        # displayed count from the previously-sent value to the new one.
        # Frames cascade left-to-right (each digit position locks one
        # frame after the previous one), with ease-in-out interval timing
        # — so the timer is single-shot and reschedules per frame.
        self._last_sent_count: Optional[int] = None
        self._anim_frames: list = []
        self._anim_intervals: list = []
        self._anim_index = 0
        self._anim_timer = QTimer(self)
        self._anim_timer.setSingleShot(True)
        self._anim_timer.timeout.connect(self._anim_tick)

        # ---- Credentials
        cred = Card(title="Credentials")
        form = QFormLayout()
        self.ig_user_edit = QLineEdit(self._config.get_secret("ig_user_id", ""))
        self.ig_user_edit.setPlaceholderText("17841... (IG Business Account ID)")
        form.addRow("IG user ID", self.ig_user_edit)

        self.token_edit = QLineEdit(self._config.get_secret("ig_access_token", ""))
        self.token_edit.setEchoMode(QLineEdit.Password)
        self.token_edit.setPlaceholderText("EAA... (long-lived or system user token)")
        form.addRow("Access token", self.token_edit)

        self.app_id_edit = QLineEdit(self._config.get_secret("ig_app_id", ""))
        self.app_id_edit.setPlaceholderText("Optional — only needed for token refresh")
        form.addRow("App ID", self.app_id_edit)

        self.app_secret_edit = QLineEdit(self._config.get_secret("ig_app_secret", ""))
        self.app_secret_edit.setEchoMode(QLineEdit.Password)
        self.app_secret_edit.setPlaceholderText("Optional — only needed for token refresh")
        form.addRow("App secret", self.app_secret_edit)
        cred.add_layout(form)

        cred_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save_credentials)
        cred_row.addWidget(save_btn)
        refresh_btn = QPushButton("Refresh token (60 days)")
        refresh_btn.clicked.connect(self._refresh_token)
        cred_row.addWidget(refresh_btn)
        cred_row.addStretch()
        cred.add_layout(cred_row)

        cred.add(QLabel(
            "Generate at developers.facebook.com → Graph API Explorer "
            "(instagram_basic + pages_show_list scopes). System User tokens "
            "from Business Settings don't expire."
        ))
        self.content_layout().addWidget(cred)

        # ---- Fetch
        fetch = Card(title="Status")
        fetch_row = QHBoxLayout()
        self.fetch_btn = QPushButton("Fetch follower count")
        self.fetch_btn.clicked.connect(self._fetch)
        fetch_row.addWidget(self.fetch_btn)
        fetch_row.addStretch()
        fetch.add_layout(fetch_row)
        self.status_label = QLabel("Save credentials, then Fetch.")
        self.status_label.setStyleSheet("color:#a6adc8;")
        fetch.add(self.status_label)
        self.content_layout().addWidget(fetch)

        # ---- Display
        disp = Card(title="Display")
        dform = QFormLayout()

        self.layout_combo = QComboBox()
        for label, _ in LAYOUTS:
            self.layout_combo.addItem(label)
        last_layout = self._config.get_setting("instagram_layout", LAYOUT_ICON)
        self.layout_combo.setCurrentIndex(
            0 if last_layout == LAYOUT_ICON else 1
        )
        self.layout_combo.currentIndexChanged.connect(self._on_layout_change)
        dform.addRow("Layout", self.layout_combo)

        self.format_combo = QComboBox()
        for label, _ in FORMATS:
            self.format_combo.addItem(label)
        dform.addRow("Text format", self.format_combo)

        col_row = QHBoxLayout()
        col_row.addWidget(QLabel("Text"))
        self.text_color = ColorButton("#FFFFFF")
        col_row.addWidget(self.text_color)
        col_row.addSpacing(16)
        col_row.addWidget(QLabel("Background"))
        # Instagram-ish purple default.
        self.bg_color = ColorButton("#833AB4")
        col_row.addWidget(self.bg_color)
        col_row.addStretch()
        dform.addRow("Colours", col_row)
        disp.add_layout(dform)
        self.content_layout().addWidget(disp)

        # ---- Sprite font
        font_card = Card(title="Sprite font")
        names = self._config.get_sprite_font_names()
        self.font_picker = SpriteFontPicker(
            font_names=names,
            use_sprite=bool(self._config.get_setting("instagram_use_sprite_font", True)),
            font_name=self._config.get_setting(
                "instagram_sprite_font_name", names[0] if names else ""
            ),
        )
        self.font_picker.changed.connect(self._on_font_change)
        font_card.add(self.font_picker)
        self.content_layout().addWidget(font_card)

        # ---- Auto-refresh
        ref = Card(title="Auto-refresh")
        self.refresh_check = QCheckBox("Refresh follower count automatically")
        ref.add(self.refresh_check)
        rform = QFormLayout()
        self.refresh_interval = QSpinBox()
        self.refresh_interval.setRange(60, 3600)
        self.refresh_interval.setSingleStep(60)
        self.refresh_interval.setValue(300)
        self.refresh_interval.setSuffix(" s")
        rform.addRow("Interval", self.refresh_interval)
        ref.add_layout(rform)
        self.animate_check = QCheckBox("Animate when the count changes")
        self.animate_check.setChecked(
            bool(self._config.get_setting("instagram_animate_changes", True))
        )
        self.animate_check.toggled.connect(
            lambda v: self._config.set_setting("instagram_animate_changes", bool(v))
        )
        ref.add(self.animate_check)
        self.content_layout().addWidget(ref)

        # ---- Actions
        row = QHBoxLayout()
        self.send_btn = QPushButton("Send to panel")
        self.send_btn.setObjectName("PrimaryButton")
        self.send_btn.clicked.connect(self._send)
        row.addWidget(self.send_btn)

        stop_btn = QPushButton("Stop refresh")
        stop_btn.clicked.connect(self._stop_refresh)
        row.addWidget(stop_btn)

        save_preset_btn = QPushButton("Save as preset")
        save_preset_btn.clicked.connect(self._save_preset)
        row.addWidget(save_preset_btn)
        row.addStretch()
        self.content_layout().addLayout(row)

        self.on_connection_changed(self._device.is_connected)

    # ---------------------------------------------------------------- helpers
    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _save_credentials(self) -> None:
        self._config.set_secret("ig_user_id", self.ig_user_edit.text().strip())
        self._config.set_secret("ig_access_token", self.token_edit.text().strip())
        self._config.set_secret("ig_app_id", self.app_id_edit.text().strip())
        self._config.set_secret("ig_app_secret", self.app_secret_edit.text().strip())
        QMessageBox.information(self, "Saved", "Instagram credentials saved.")

    def _format_key(self) -> str:
        return FORMATS[self.format_combo.currentIndex()][1]

    # ------------------------------------------------------------------ fetch
    def _fetch(self) -> None:
        ig_user_id = self.ig_user_edit.text().strip()
        token = self.token_edit.text().strip()
        if not ig_user_id or not token:
            QMessageBox.warning(
                self,
                "Missing credentials",
                "Enter both the IG user ID and an access token, then Save.",
            )
            return
        self.fetch_btn.setEnabled(False)
        self._fetcher.run(ig_user_id=ig_user_id, access_token=token)

    def _on_data(self, data: Dict[str, Any]) -> None:
        self.fetch_btn.setEnabled(True)
        self._current = data
        handle = data.get("username") or "?"
        self._set_status(
            f"@{handle}: {data.get('follower_count', 0):,} followers · "
            f"{data.get('media_count', 0):,} posts"
        )

    def _on_error(self, error: str) -> None:
        self.fetch_btn.setEnabled(True)
        self._set_status(f"Error: {error}")

    # ------------------------------------------------------------------ token
    def _refresh_token(self) -> None:
        token = self.token_edit.text().strip()
        app_id = self.app_id_edit.text().strip()
        app_secret = self.app_secret_edit.text().strip()
        if not (token and app_id and app_secret):
            QMessageBox.warning(
                self,
                "Need App ID + Secret",
                "Token refresh requires the Facebook App ID and App Secret. "
                "System User tokens don't need refresh.",
            )
            return
        self._token_fetcher.run(
            short_or_long_token=token, app_id=app_id, app_secret=app_secret
        )

    def _on_token_refreshed(self, data: Dict[str, Any]) -> None:
        new_token = data.get("access_token", "")
        days = data.get("expires_in", 0) // 86400
        self.token_edit.setText(new_token)
        self._config.set_secret("ig_access_token", new_token)
        self._set_status(f"Token refreshed (~{days} days).")

    # ------------------------------------------------------------------ send
    def _send(self) -> None:
        if not self._device.is_connected:
            QMessageBox.warning(self, "Not connected", "Connect to a device first.")
            return
        if not self._current:
            QMessageBox.warning(self, "No data", "Fetch the follower count first.")
            return

        self._sender.stop()
        self._anim_timer.stop()

        new_count = int(self._current.get("follower_count", 0))
        prev = self._last_sent_count

        if (
            self.animate_check.isChecked()
            and prev is not None
            and new_count != prev
        ):
            self._start_count_animation(prev, new_count)
        else:
            err = self._render_and_send(new_count)
            if err:
                QMessageBox.critical(self, "Send error", err)

        if self.refresh_check.isChecked():
            self._refresh_timer.start(self.refresh_interval.value() * 1000)

    # ----------------------------------------------------------- dispatch
    def _render_and_send(self, count: int) -> Optional[str]:
        """Render the panel image for ``count`` and dispatch it.

        Used by both the regular send path and the animation engine — the
        ``count`` argument lets us draw intermediate values without
        mutating ``self._current``.
        """
        self._last_sent_count = count
        data = dict(self._current or {})
        data["follower_count"] = count

        layout = LAYOUTS[self.layout_combo.currentIndex()][1]
        if layout == LAYOUT_ICON:
            return self._render_icon_for(data)

        text = format_instagram_display(data, self._format_key())
        if self.font_picker.use_sprite and self.font_picker.font_name:
            return self._sender.send_static(
                text, self.font_picker.font_name, self.bg_color.color
            )
        self._device.send_text(
            text,
            char_height=16,
            color=self.text_color.color,
            bg_color=self.bg_color.color,
            animation=0,
            speed=50,
        )
        return None

    # ---------------------------------------------------------- animation
    # Frame cadence is bounded below by BLE throughput: full 64×16 image
    # uploads at < ~320 ms intervals cause the bridge to disconnect after
    # consecutive timeouts. The ease-in-out profile keeps intervals
    # comfortably above that floor.
    ANIM_INTERVAL_MIN_MS = 340  # peak speed in the middle of the animation
    ANIM_INTERVAL_MAX_MS = 540  # slow ramp at the start and end
    # Each digit position locks one frame after the one to its left;
    # ANIM_PRE_LOCK_FRAMES is how many full rolls happen before the
    # leftmost digit settles. Higher = more rolling visible up front.
    ANIM_PRE_LOCK_FRAMES = 2

    def _start_count_animation(self, from_count: int, to_count: int) -> None:
        """Schedule a left-to-right digit cascade transitioning to ``to_count``.

        Each digit position locks one frame after its left neighbour, so
        the number is revealed gradually rather than every digit settling
        at once. Inter-frame intervals follow an ease-in-out (cosine)
        profile so the animation starts and ends gently.
        """
        if from_count == to_count:
            self._render_and_send(to_count)
            return

        self._anim_frames, self._anim_intervals = self._build_cascade_frames(
            to_count
        )
        self._anim_index = 0
        self._anim_tick()

    def _build_cascade_frames(self, target: int):
        """Return (frames, intervals).

        ``frames[i]`` is the integer to render on the i-th tick.
        ``intervals[i]`` is the delay (ms) between frames[i] and frames[i+1],
        so ``len(intervals) == len(frames) - 1``.

        Digit ``d`` (0 = leftmost) locks on frame ``ANIM_PRE_LOCK_FRAMES + d``;
        before that frame it shows ``(target_digit + lock_frame - current_frame) mod 10``,
        producing a smooth count-down to its final digit. Leading digit is
        clamped to 1 if a roll would otherwise produce a leading zero
        mid-animation (which would visually shrink the number).
        """
        target_str = str(abs(target))
        target_digits = [int(c) for c in target_str]
        num_digits = len(target_digits)
        sign = -1 if target < 0 else 1

        lock_frames = [self.ANIM_PRE_LOCK_FRAMES + d for d in range(num_digits)]
        n_frames = lock_frames[-1] + 1  # last digit locks on the final frame

        frames = []
        for f in range(n_frames):
            digits = []
            for d in range(num_digits):
                if f >= lock_frames[d]:
                    digits.append(target_digits[d])
                else:
                    offset = lock_frames[d] - f
                    digits.append((target_digits[d] + offset) % 10)
            if num_digits > 1 and digits[0] == 0:
                digits[0] = 1
            frames.append(sign * int("".join(str(d) for d in digits)))
        frames[-1] = target  # exact landing

        # Build ease-in-out interval profile. Inverse-sinusoid: large at
        # the edges (slow start/end), small in the middle (fast).
        n_intervals = n_frames - 1
        intervals = []
        for i in range(n_intervals):
            t = i / max(1, n_intervals - 1) if n_intervals > 1 else 0.5
            curve = 1.0 - math.sin(math.pi * t)  # 1 at edges, 0 in middle
            interval = int(
                self.ANIM_INTERVAL_MIN_MS
                + curve * (self.ANIM_INTERVAL_MAX_MS - self.ANIM_INTERVAL_MIN_MS)
            )
            intervals.append(interval)

        return frames, intervals

    def _anim_tick(self) -> None:
        if self._anim_index >= len(self._anim_frames):
            return
        value = self._anim_frames[self._anim_index]
        err = self._render_and_send(value)
        if err:
            # Stop animating, then re-send the final target so the panel
            # doesn't get stuck on an intermediate value.
            self._set_status(f"Animation aborted: {err}")
            if self._anim_frames:
                self._render_and_send(self._anim_frames[-1])
            return
        self._anim_index += 1
        if self._anim_index < len(self._anim_frames):
            # Schedule the next frame with the ease-in-out interval that
            # follows the frame we just sent.
            self._anim_timer.start(self._anim_intervals[self._anim_index - 1])

    # ------------------------------------------------------- icon composite
    def _render_icon_for(self, data: Dict[str, Any]) -> Optional[str]:
        """Render a 64×16 panel image with Instagram.png on the left and
        the follower count centred in the remaining ~48 columns. Mirrors
        the weather page's icon-composite path. Takes a data dict so the
        animation engine can render arbitrary intermediate counts.
        """
        # 46 columns of room next to the icon; assume ~7 px per char and
        # cap the format helper accordingly so it truncates rather than
        # overflowing into the icon zone.
        count_str = format_instagram_display(
            data, self._format_key(), max_chars=7
        )

        bg = self.bg_color.color
        canvas = Image.new("RGB", (64, 16), bg)

        # 1) Instagram icon, left edge (16×16).
        icon_path = resolve_asset_path(INSTAGRAM_ICON_PATH)
        if not os.path.isfile(icon_path):
            return (
                f"Instagram.png not found at {INSTAGRAM_ICON_PATH}. "
                "Drop a 16x16 PNG there or pick the Text-only layout."
            )
        try:
            with Image.open(icon_path) as icon:
                icon = icon.convert("RGBA")
                if icon.size != (16, 16):
                    icon = icon.resize((16, 16), Image.LANCZOS)
                canvas.paste(icon, (0, 0), icon)
        except Exception as e:  # noqa: BLE001
            return f"Failed to load Instagram icon: {e}"

        # 2) Count text centred in the right block (x=18..63 = 46 columns).
        right_start, right_end = 18, 64
        right_width = right_end - right_start

        text_img: Optional[Image.Image] = None
        if self.font_picker.use_sprite and self.font_picker.font_name:
            text_img, _err = self._fonts.render_text_line(
                count_str, self.font_picker.font_name, bg
            )
            if _err:
                text_img = None

        if text_img is not None:
            # If the rendered text is taller than the panel, scale down.
            if text_img.height > 16:
                scale = 16 / text_img.height
                text_img = text_img.resize(
                    (max(1, int(text_img.width * scale)), 16), Image.NEAREST
                )
            # If it's wider than the right block, crop from the left
            # (keeps the most significant digits visible).
            if text_img.width > right_width:
                text_img = text_img.crop((0, 0, right_width, text_img.height))
            tx = right_start + (right_width - text_img.width) // 2
            ty = (16 - text_img.height) // 2
            canvas.paste(
                text_img,
                (tx, ty),
                text_img if text_img.mode == "RGBA" else None,
            )
            path = save_temp_image(canvas, "ipixel_instagram.png")
            self._device.send_image(path, resize_method="crop", save_slot=0)
            return None

        # Fallback when no sprite font is selected: dispatch the icon
        # canvas as the static background, then overlay the count via the
        # firmware's send_text. send_text writes over the slot, so this
        # only works cleanly when the user picks a sprite font. Surface a
        # gentle error to make the requirement obvious.
        return (
            "Icon layout needs a sprite font selected (firmware send_text "
            "can't be composited over a background image). Enable a sprite "
            "font under the Sprite font card, or use the Text-only layout."
        )

    def _on_layout_change(self, _idx: int) -> None:
        layout = LAYOUTS[self.layout_combo.currentIndex()][1]
        self._config.set_setting("instagram_layout", layout)

    def _stop_refresh(self) -> None:
        self._refresh_timer.stop()
        self._anim_timer.stop()

    def _on_font_change(self) -> None:
        self._config.set_setting(
            "instagram_use_sprite_font", self.font_picker.use_sprite
        )
        self._config.set_setting(
            "instagram_sprite_font_name", self.font_picker.font_name
        )

    def refresh_font_list(self, names) -> None:
        self.font_picker.set_fonts(names)

    def _auto_refresh(self) -> None:
        def once(_data):
            self._send()
            try:
                self._fetcher.succeeded.disconnect(once)
            except Exception:
                pass

        self._fetcher.succeeded.connect(once)
        self._fetch()

    # ---------------------------------------------------------------- preset
    def _save_preset(self) -> None:
        if not self._current:
            QMessageBox.warning(self, "No data", "Fetch the follower count first.")
            return
        handle = self._current.get("username") or "Instagram"
        default = f"Instagram - @{handle[:15]}"
        name, ok = QInputDialog.getText(
            self, "Save preset", "Preset name:", text=default
        )
        if not ok or not name.strip():
            return
        preset = {
            "name": name.strip(),
            "type": self.feature_id,
            "layout": LAYOUTS[self.layout_combo.currentIndex()][1],
            "format": self._format_key(),
            "text_color": self.text_color.color,
            "bg_color": self.bg_color.color,
            "auto_refresh": self.refresh_check.isChecked(),
            "refresh_interval": self.refresh_interval.value(),
            "animate_changes": self.animate_check.isChecked(),
            "instagram_use_sprite_font": self.font_picker.use_sprite,
            "instagram_sprite_font_name": self.font_picker.font_name,
        }
        self._config.add_preset(preset)
        QMessageBox.information(self, "Saved", f"Preset '{name}' saved.")

    def execute_preset(self, preset: Dict[str, Any]) -> bool:
        layout = preset.get("layout", LAYOUT_ICON)
        for i, (_, key) in enumerate(LAYOUTS):
            if key == layout:
                self.layout_combo.setCurrentIndex(i)
                break
        fmt = preset.get("format", "count_short")
        for i, (_, key) in enumerate(FORMATS):
            if key == fmt:
                self.format_combo.setCurrentIndex(i)
                break
        self.text_color.set_color(preset.get("text_color", "#FFFFFF"))
        self.bg_color.set_color(preset.get("bg_color", "#833AB4"))
        self.refresh_check.setChecked(bool(preset.get("auto_refresh", False)))
        self.refresh_interval.setValue(int(preset.get("refresh_interval", 300)))
        if "animate_changes" in preset:
            self.animate_check.setChecked(bool(preset.get("animate_changes", True)))
        if "instagram_use_sprite_font" in preset:
            self.font_picker.set_use_sprite(
                bool(preset.get("instagram_use_sprite_font", True))
            )
        if "instagram_sprite_font_name" in preset:
            self.font_picker.set_font_name(
                preset.get("instagram_sprite_font_name", "")
            )

        def once(_data):
            self._send()
            try:
                self._fetcher.succeeded.disconnect(once)
            except Exception:
                pass

        self._fetcher.succeeded.connect(once)
        self._fetch()
        return True

    # ----------------------------------------------------------------- state
    def on_connection_changed(self, connected: bool) -> None:
        self.send_btn.setEnabled(connected)
        if not connected:
            self._refresh_timer.stop()
            self._anim_timer.stop()
            # Forget what was on the panel so the first send after
            # reconnect doesn't animate from a stale value.
            self._last_sent_count = None

    def on_hidden(self) -> None:
        self._refresh_timer.stop()
        self._anim_timer.stop()
        self._sender.stop()
