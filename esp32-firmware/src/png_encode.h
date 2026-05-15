#pragma once
#include <Arduino.h>

// Encode a 64x16 RGB888 framebuffer as a minimal PNG (single uncompressed
// deflate block — no compression, but the panel firmware doesn't care about
// PNG compression, only that the bytes parse). Returns total bytes written
// into `out`, or 0 on overflow. Output size is fixed at ~3156 bytes for the
// 64x16 panel — pass an `outCap` of at least 3200.
size_t pngEncode64x16RGB(const uint8_t* fb, uint8_t* out, size_t outCap);

// Standard CRC32 (poly 0xEDB88320, init 0xFFFFFFFF, final XOR 0xFFFFFFFF).
// Exposed because the pypixelcolor send_image frame needs the same CRC over
// the full PNG, little-endian, alongside the size prefix.
uint32_t crc32Std(const uint8_t* data, size_t len);
