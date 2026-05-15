#include "renderer.h"
#include "assets_icon.h"
#include "assets_font.h"
#include <string.h>
#include <pgmspace.h>

static inline void putPixel(uint8_t* fb, int x, int y, uint32_t rgb) {
    if (x < 0 || x >= PANEL_W || y < 0 || y >= PANEL_H) return;
    uint8_t* p = fb + (y * PANEL_W + x) * 3;
    p[0] = (rgb >> 16) & 0xFF;
    p[1] = (rgb >>  8) & 0xFF;
    p[2] = (rgb      ) & 0xFF;
}

void rendererFillBg(uint8_t* fb, uint32_t bg) {
    uint8_t r = (bg >> 16) & 0xFF, g = (bg >> 8) & 0xFF, b = bg & 0xFF;
    for (size_t i = 0; i < FB_BYTES; i += 3) { fb[i] = r; fb[i+1] = g; fb[i+2] = b; }
}

void rendererDrawInstagramIcon(uint8_t* fb) {
    for (int y = 0; y < IG_ICON_H; ++y) {
        for (int x = 0; x < IG_ICON_W; ++x) {
            size_t i = (size_t)y * IG_ICON_W + x;
            uint8_t maskByte = pgm_read_byte(&IG_ICON_MASK[i >> 3]);
            if (!(maskByte & (1u << (i & 7)))) continue;   // transparent — leave bg
            size_t off = i * 3;
            uint8_t r = pgm_read_byte(&IG_ICON_RGB[off + 0]);
            uint8_t g = pgm_read_byte(&IG_ICON_RGB[off + 1]);
            uint8_t b = pgm_read_byte(&IG_ICON_RGB[off + 2]);
            putPixel(fb, x, y, ((uint32_t)r << 16) | ((uint32_t)g << 8) | b);
        }
    }
}

// Linear search through FONT_GLYPH_ORDER. 73 entries, no need for a LUT.
static int glyphIndex(char c) {
    for (int i = 0; i < FONT_GLYPH_COUNT; ++i) {
        if (FONT_GLYPH_ORDER[i] == c) return i;
    }
    // Fall back to uppercase for letters (the order has both cases, but be safe).
    if (c >= 'a' && c <= 'z') return glyphIndex((char)(c - 32));
    return -1; // unknown -> blank
}

int rendererSpriteTextWidth(const char* text) {
    int n = 0; while (text[n]) n++;
    return n <= 0 ? 0 : n * FONT_GLYPH_W;
}

static void drawGlyphAt(uint8_t* fb, char c, int x, int y, uint32_t fg) {
    int gi = glyphIndex(c);
    if (gi < 0) return;
    for (int row = 0; row < FONT_GLYPH_H; ++row) {
        uint8_t bits = pgm_read_byte(&FONT_GLYPH_BITS[gi][row]);
        if (!bits) continue;
        for (int col = 0; col < FONT_GLYPH_W; ++col) {
            if (bits & (1 << (7 - col))) {
                putPixel(fb, x + col, y + row, fg);
            }
        }
    }
}

void rendererDrawSpriteText(uint8_t* fb, const char* text,
                            int x, int y, uint32_t fg) {
    while (*text) {
        drawGlyphAt(fb, *text++, x, y, fg);
        x += FONT_GLYPH_W;
    }
}

// Repaint only the text area (x >= TEXT_AREA_X) with bg, leaving the icon column intact.
static void clearTextArea(uint8_t* fb, uint32_t bg) {
    uint8_t r = (bg >> 16) & 0xFF, g = (bg >> 8) & 0xFF, b = bg & 0xFF;
    for (int y = 0; y < PANEL_H; ++y) {
        for (int x = TEXT_AREA_X; x < PANEL_W; ++x) {
            uint8_t* p = fb + (y * PANEL_W + x) * 3;
            p[0] = r; p[1] = g; p[2] = b;
        }
    }
}

static int centeredX(const char* text) {
    int w = rendererSpriteTextWidth(text);
    int x = TEXT_AREA_X + (TEXT_AREA_W - w) / 2;
    if (x < TEXT_AREA_X) x = TEXT_AREA_X;
    return x;
}

void rendererStaticFrame(uint8_t* fb, const char* text,
                         uint32_t fg, uint32_t bg) {
    rendererFillBg(fb, bg);
    rendererDrawInstagramIcon(fb);
    rendererDrawSpriteText(fb, text, centeredX(text), 0, fg);
}

void rendererTweenFrame(uint8_t* fb, const char* from, const char* to,
                        uint32_t fg, uint32_t bg, float t) {
    if (t < 0) t = 0; if (t > 1) t = 1;
    // Repaint only the text area each frame; the icon column doesn't move.
    rendererDrawInstagramIcon(fb);
    clearTextArea(fb, bg);
    int yFrom = 0 - (int)(PANEL_H * t);
    int yTo   = 0 + (int)(PANEL_H * (1.0f - t));
    rendererDrawSpriteText(fb, from, centeredX(from), yFrom, fg);
    rendererDrawSpriteText(fb, to,   centeredX(to),   yTo,   fg);
}
