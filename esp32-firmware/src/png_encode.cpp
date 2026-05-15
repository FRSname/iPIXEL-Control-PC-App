#include "png_encode.h"
#include <string.h>

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

static uint32_t adler32(const uint8_t* p, size_t n) {
    uint32_t a = 1, b = 0;
    while (n--) {
        a = (a + *p++) % 65521;
        b = (b + a) % 65521;
    }
    return (b << 16) | a;
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
    const int W = 64, H = 16;
    const size_t rowStride = (size_t)1 + W * 3;       // 1 filter byte + RGB row
    const size_t rawLen    = (size_t)H * rowStride;   // 16 * 193 = 3088
    // Computed PNG size: 8 (sig) + 25 (IHDR) + 4+4+2+5+rawLen+4+4 (IDAT) + 12 (IEND)
    const size_t expected = 8 + 25 + (12 + 2 + 5 + rawLen + 4) + 12;
    if (outCap < expected) return 0;

    uint8_t* p = out;

    static const uint8_t SIG[8] = {0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A};
    memcpy(p, SIG, 8); p += 8;

    uint8_t ihdr[13];
    writeBE32(ihdr,     W);
    writeBE32(ihdr + 4, H);
    ihdr[8]  = 8;   // bit depth
    ihdr[9]  = 2;   // colour type = truecolour RGB
    ihdr[10] = 0;   // compression = deflate
    ihdr[11] = 0;   // filter
    ihdr[12] = 0;   // no interlace
    writeChunk(p, "IHDR", ihdr, 13);

    // IDAT chunk — patch length once payload is assembled
    uint8_t* idatLenPos = p;
    writeBE32(p, 0); p += 4;
    uint8_t* idatTypeAndData = p;
    memcpy(p, "IDAT", 4); p += 4;

    uint8_t* zlibStart = p;
    *p++ = 0x78; // CMF: deflate, 32K window
    *p++ = 0x01; // FLG: fastest, no preset dict (FCHECK adjusted so (CMF*256+FLG)%31==0)

    // One stored (uncompressed) deflate block holding the whole image.
    *p++ = 0x01; // BFINAL=1, BTYPE=00, pad bits = 0
    uint16_t blockLen = (uint16_t)rawLen;
    *p++ = (uint8_t)(blockLen & 0xFF);
    *p++ = (uint8_t)((blockLen >> 8) & 0xFF);
    uint16_t nblockLen = (uint16_t)~blockLen;
    *p++ = (uint8_t)(nblockLen & 0xFF);
    *p++ = (uint8_t)((nblockLen >> 8) & 0xFF);

    uint8_t* rawStart = p;
    for (int y = 0; y < H; ++y) {
        *p++ = 0; // filter = None
        memcpy(p, fb + (size_t)y * W * 3, W * 3);
        p += W * 3;
    }

    uint32_t adl = adler32(rawStart, rawLen);
    writeBE32(p, adl); p += 4;

    size_t zlibLen = (size_t)(p - zlibStart);
    writeBE32(idatLenPos, (uint32_t)zlibLen);
    uint32_t idatCrc = crc32Std(idatTypeAndData, 4 + zlibLen);
    writeBE32(p, idatCrc); p += 4;

    writeChunk(p, "IEND", nullptr, 0);
    return (size_t)(p - out);
}
