#pragma once
#include <Arduino.h>

// 64x16 RGB framebuffer, row-major, 3 bytes per pixel.
constexpr int PANEL_W = 64;
constexpr int PANEL_H = 16;
constexpr size_t FB_BYTES = PANEL_W * PANEL_H * 3;

// Renders a text string centered on a 64x16 RGB framebuffer using a 5x7 bitmap font.
// `fg` and `bg` are 0xRRGGBB.
void rendererDrawText(uint8_t* fb, const char* text, uint32_t fg, uint32_t bg);

// Crossfade tween between two strings — call rendererTweenFrame in a loop with t in [0,1].
// Used when the follower count changes.
void rendererTweenFrame(uint8_t* fb, const char* from, const char* to,
                        uint32_t fg, uint32_t bg, float t);
