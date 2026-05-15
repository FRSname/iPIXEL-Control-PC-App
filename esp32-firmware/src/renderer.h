#pragma once
#include <Arduino.h>

constexpr int    PANEL_W  = 64;
constexpr int    PANEL_H  = 16;
constexpr size_t FB_BYTES = PANEL_W * PANEL_H * 3;

// Layout: 16x16 IG icon on the left + 48px area for the follower text.
constexpr int    TEXT_AREA_X = PANEL_W - 48;     // 16
constexpr int    TEXT_AREA_W = 48;

// Fill the entire framebuffer with `bg` (0xRRGGBB).
void rendererFillBg(uint8_t* fb, uint32_t bg);

// Stamp the baked Instagram icon at the upper-left corner. Icon pixels
// overwrite the framebuffer (no alpha blending — it was pre-flattened onto
// black during conversion).
void rendererDrawInstagramIcon(uint8_t* fb);

// Pixel width of `text` rendered in the baked sprite font.
int rendererSpriteTextWidth(const char* text);

// Draw `text` in the sprite font at (x, y_top) using `fg` (0xRRGGBB) for
// "on" pixels. Off pixels stay untouched, so the framebuffer's existing
// background (and the icon) shows through gaps.
void rendererDrawSpriteText(uint8_t* fb, const char* text,
                            int x, int y, uint32_t fg);

// One frame of a slide-up tween between `from` and `to`, both rendered
// centered inside the text area. `t` in [0, 1]. Icon stays static — only
// pixels inside the text area are touched.
void rendererTweenFrame(uint8_t* fb, const char* from, const char* to,
                        uint32_t fg, uint32_t bg, float t);

// Render a static frame: bg fill + icon + centered text.
void rendererStaticFrame(uint8_t* fb, const char* text,
                         uint32_t fg, uint32_t bg);
