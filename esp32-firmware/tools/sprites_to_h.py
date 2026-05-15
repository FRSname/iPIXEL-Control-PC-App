"""Convert iPixel sprite assets to PROGMEM C headers for the ESP32 firmware.

Outputs:
  src/assets_icon.h  -- the Instagram icon (16x16 RGB888)
  src/assets_font.h  -- one sprite font (73 glyphs x 7x16 RGBA8888)

Run once after editing this script's CHOICES or after replacing source PNGs.
The desktop app uses the same glyph order, so the on-device font renders
identical text to what you'd see in the Qt UI.
"""

from __future__ import annotations
from pathlib import Path
from PIL import Image


# What to bake in. Change FONT_PNG to use a different sheet
# (TextSpriteYellow.png, Text-thin-White-Sprite.png, etc.) - the columns/order
# stay the same because every TextSprite*.png shares the 512x16 / 73-glyph layout.
GALLERY        = Path(__file__).resolve().parents[2] / "Gallery" / "Sprites"
ICON_PNG       = GALLERY / "Instagram.png"
FONT_PNG       = GALLERY / "TextSprite.png"

# 73-char order matching ipixel_controller/services/sprite_font.py TEXT_GLYPH_ORDER
GLYPH_ORDER    = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:!?.,+-/$% "
GLYPH_COLS     = 73
GLYPH_W        = 7
GLYPH_H        = 16

OUT_ICON       = Path(__file__).resolve().parent.parent / "src" / "assets_icon.h"
OUT_FONT       = Path(__file__).resolve().parent.parent / "src" / "assets_font.h"


def emit_icon():
    img = Image.open(ICON_PNG).convert("RGBA")
    if img.size != (16, 16):
        img = img.resize((16, 16), Image.NEAREST)
    w, h = img.size

    # RGB array — alpha-composited onto black so the colour values are stable
    # even though we won't draw the transparent pixels at runtime.
    bg = Image.new("RGB", (w, h), (0, 0, 0))
    bg.paste(img, mask=img.split()[3])
    px = list(bg.getdata())

    # 1-bit alpha mask, packed LSB-first per byte, row-major. The renderer
    # uses it to skip transparent pixels so the user's background colour
    # shows through (instead of a black square behind the icon).
    alpha = list(img.split()[3].getdata())
    n_bits  = w * h
    n_bytes = (n_bits + 7) // 8
    mask = bytearray(n_bytes)
    for i, a in enumerate(alpha):
        if a > 128:
            mask[i >> 3] |= 1 << (i & 7)

    lines = []
    lines.append("// Auto-generated from Gallery/Sprites/Instagram.png by tools/sprites_to_h.py")
    lines.append("#pragma once")
    lines.append("#include <Arduino.h>")
    lines.append("")
    lines.append(f"static constexpr int IG_ICON_W = {w};")
    lines.append(f"static constexpr int IG_ICON_H = {h};")
    lines.append("")
    lines.append(f"static const uint8_t IG_ICON_RGB[{w*h*3}] PROGMEM = {{")
    chunks = []
    for r, g, b in px:
        chunks.append(f"0x{r:02X},0x{g:02X},0x{b:02X}")
    for i in range(0, len(chunks), 8):
        lines.append("    " + ",".join(chunks[i:i+8]) + ",")
    lines.append("};")
    lines.append("")
    lines.append(f"// 1-bit alpha mask: bit set = draw pixel, bit clear = leave bg alone.")
    lines.append(f"static const uint8_t IG_ICON_MASK[{n_bytes}] PROGMEM = {{")
    mask_chunks = [f"0x{b:02X}" for b in mask]
    for i in range(0, len(mask_chunks), 8):
        lines.append("    " + ",".join(mask_chunks[i:i+8]) + ",")
    lines.append("};")
    OUT_ICON.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT_ICON.relative_to(OUT_ICON.parents[2])}  ({len(px)*3} bytes RGB + {n_bytes} bytes mask)")


def emit_font():
    sheet = Image.open(FONT_PNG).convert("RGBA")
    tile_w = sheet.width // GLYPH_COLS
    tile_h = sheet.height
    assert tile_w == GLYPH_W and tile_h == GLYPH_H, (
        f"Expected {GLYPH_W}x{GLYPH_H} glyphs from a {GLYPH_COLS}-col sheet, "
        f"got {tile_w}x{tile_h} from {sheet.size}"
    )
    assert len(GLYPH_ORDER) == GLYPH_COLS, (
        f"GLYPH_ORDER has {len(GLYPH_ORDER)} chars, expected {GLYPH_COLS}"
    )

    # For each glyph, store a 1-bit mask: pixel "on" iff alpha > 128.
    # Color comes from the user's textColor at draw time (so the same font
    # works as white, yellow, red... without needing multiple PNGs).
    # 7x16 = 112 bits = 14 bytes per glyph, row-major, MSB-first per row.
    masks = []
    for col in range(GLYPH_COLS):
        glyph = sheet.crop((col * GLYPH_W, 0, (col + 1) * GLYPH_W, GLYPH_H))
        alpha = glyph.split()[3]
        bits = bytearray(GLYPH_H * 1)  # row stride = 1 byte (7 bits used, top-aligned)
        for y in range(GLYPH_H):
            row = 0
            for x in range(GLYPH_W):
                if alpha.getpixel((x, y)) > 128:
                    row |= (1 << (7 - x))  # MSB-first, bit 7 = leftmost
            bits[y] = row
        masks.append(bytes(bits))

    lines = []
    lines.append(f"// Auto-generated from Gallery/Sprites/{FONT_PNG.name} by tools/sprites_to_h.py")
    lines.append("#pragma once")
    lines.append("#include <Arduino.h>")
    lines.append("")
    lines.append(f"static constexpr int  FONT_GLYPH_W = {GLYPH_W};")
    lines.append(f"static constexpr int  FONT_GLYPH_H = {GLYPH_H};")
    lines.append(f"static constexpr int  FONT_GLYPH_COUNT = {GLYPH_COLS};")
    safe_order = GLYPH_ORDER.replace("\\", "\\\\").replace('"', '\\"')
    lines.append(f'static const char     FONT_GLYPH_ORDER[] = "{safe_order}";')
    lines.append("")
    lines.append(f"// One row per byte (MSB = leftmost pixel). {GLYPH_H} rows per glyph.")
    lines.append(f"static const uint8_t  FONT_GLYPH_BITS[{GLYPH_COLS}][{GLYPH_H}] PROGMEM = {{")
    for ch, m in zip(GLYPH_ORDER, masks):
        row_bytes = ",".join(f"0x{b:02X}" for b in m)
        disp = ch.replace("\\", "\\\\").replace("'", "\\'")
        lines.append(f"    {{ {row_bytes} }}, // '{disp}'")
    lines.append("};")
    OUT_FONT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT_FONT.relative_to(OUT_FONT.parents[2])}  ({GLYPH_COLS*GLYPH_H} bytes data)")


if __name__ == "__main__":
    emit_icon()
    emit_font()
