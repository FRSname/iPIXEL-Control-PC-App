#include "png_encode.h"
#include <string.h>

// miniz lives in ESP32 ROM, so we don't pay any flash cost for it. The header
// path moved between ESP-IDF 4.x and 5.x, so resolve whichever exists. As a
// last resort we forward-declare the symbol — it's a ROM function, so the
// linker finds it regardless of whether the header is on the include path.
#if __has_include(<rom/miniz.h>)
  #include <rom/miniz.h>
#elif __has_include(<esp_rom_miniz.h>)
  #include <esp_rom_miniz.h>
#else
  extern "C" int mz_compress(unsigned char* pDest, unsigned long* pDestLen,
                             const unsigned char* pSource, unsigned long sourceLen);
  #define MZ_OK 0
#endif

static uint32_t CRC_TABLE[256];
static bool CRC_INITED = false;

static void initCrcTable() {
    if (CRC_INITED) return;
    for (uint32_t n = 0; n < 256; ++n) {
        uint32_t c = n;
        for (int k = 0; k < 8; ++k) c = (c & 1) ? (0xEDB88320 ^ (c >> 1)) : (c >> 1);
        CRC_TABLE[n] = c;
    }
    CRC_INITED = true;
}

uint32_t crc32Std(const uint8_t* p, size_t n) {
    initCrcTable();
    uint32_t c = 0xFFFFFFFF;
    while (n--) c = CRC_TABLE[(c ^ *p++) & 0xFF] ^ (c >> 8);
    return c ^ 0xFFFFFFFF;
}

static inline void writeBE32(uint8_t* p, uint32_t v) {
    p[0] = (uint8_t)(v >> 24);
    p[1] = (uint8_t)(v >> 16);
    p[2] = (uint8_t)(v >> 8);
    p[3] = (uint8_t)(v);
}

static void writeChunk(uint8_t*& p, const char* type, const uint8_t* data, size_t len) {
    writeBE32(p, (uint32_t)len); p += 4;
    uint8_t* crcStart = p;
    memcpy(p, type, 4); p += 4;
    if (len) { memcpy(p, data, len); p += len; }
    uint32_t crc = crc32Std(crcStart, 4 + len);
    writeBE32(p, crc); p += 4;
}

size_t pngEncode64x16RGB(const uint8_t* fb, uint8_t* out, size_t outCap) {
    const int    W         = 64;
    const int    H         = 16;
    const size_t rowStride = (size_t)1 + W * 3;
    const size_t rawLen    = (size_t)H * rowStride;

    static uint8_t raw[3100];
    if (rawLen > sizeof(raw)) return 0;
    for (int y = 0; y < H; ++y) {
        raw[y * rowStride] = 0;
        memcpy(raw + y * rowStride + 1, fb + (size_t)y * W * 3, W * 3);
    }

    // Compress with miniz — produces a full zlib stream (CMF/FLG header,
    // deflate data with LZ77 + Huffman, and adler32 trailer).
    static uint8_t zlib[2048];
    unsigned long zlibLen = sizeof(zlib);
    int r = mz_compress(zlib, &zlibLen, raw, rawLen);
    if (r != MZ_OK) return 0;

    const size_t expected = 8 + 25 + (12 + zlibLen) + 12;
    if (outCap < expected) return 0;

    uint8_t* p = out;
    static const uint8_t SIG[8] = {0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A};
    memcpy(p, SIG, 8); p += 8;

    uint8_t ihdr[13];
    writeBE32(ihdr,     W);
    writeBE32(ihdr + 4, H);
    ihdr[8]  = 8;
    ihdr[9]  = 2;
    ihdr[10] = 0;
    ihdr[11] = 0;
    ihdr[12] = 0;
    writeChunk(p, "IHDR", ihdr, 13);

    writeChunk(p, "IDAT", zlib, zlibLen);
    writeChunk(p, "IEND", nullptr, 0);
    return (size_t)(p - out);
}
