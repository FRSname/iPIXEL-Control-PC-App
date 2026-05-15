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

// =============================================================================
// Fixed-Huffman deflate (RFC 1951 §3.2.6). We never emit LZ77 matches — every
// input byte becomes a literal — but the bytes still go through the standard
// fixed-Huffman code table, which produces a valid (if uncompressed-on-average)
// deflate stream that all standard PNG decoders accept.
//
// Bit packing per §3.1.1:
//   - Non-Huffman fields (BFINAL, BTYPE) are packed LSB-first.
//   - Huffman codes are emitted MSB-first.
// In both cases bits accumulate LSB-first within each output byte.
// =============================================================================

struct BitWr {
    uint8_t* out;
    size_t   pos;
    uint8_t  acc;
    int      nbits;
};

static inline void bwBit(BitWr& w, int bit) {
    if (bit) w.acc |= (uint8_t)(1 << w.nbits);
    if (++w.nbits == 8) { w.out[w.pos++] = w.acc; w.acc = 0; w.nbits = 0; }
}

static void bwPutLSB(BitWr& w, uint32_t val, int count) {
    for (int i = 0; i < count; ++i) bwBit(w, (val >> i) & 1);
}

static void bwPutHuff(BitWr& w, uint32_t code, int count) {
    for (int i = count - 1; i >= 0; --i) bwBit(w, (code >> i) & 1);
}

static void bwFlush(BitWr& w) {
    if (w.nbits > 0) { w.out[w.pos++] = w.acc; w.acc = 0; w.nbits = 0; }
}

static size_t deflateFixedHuffman(const uint8_t* data, size_t dataLen, uint8_t* out) {
    BitWr w = { out, 0, 0, 0 };
    bwPutLSB(w, 1, 1);    // BFINAL = 1 (last block)
    bwPutLSB(w, 1, 2);    // BTYPE  = 01 (fixed Huffman)

    for (size_t i = 0; i < dataLen; ++i) {
        uint8_t b = data[i];
        if (b < 144) bwPutHuff(w, 0x30u  + b,           8);   // literals 0–143
        else         bwPutHuff(w, 0x190u + (b - 144),   9);   // literals 144–255
    }
    bwPutHuff(w, 0, 7);   // end-of-block symbol (literal 256, 7-bit code 0)
    bwFlush(w);
    return w.pos;
}

size_t pngEncode64x16RGB(const uint8_t* fb, uint8_t* out, size_t outCap) {
    const int    W         = 64;
    const int    H         = 16;
    const size_t rowStride = (size_t)1 + W * 3;        // 1 filter byte + RGB row
    const size_t rawLen    = (size_t)H * rowStride;    // 3088

    static uint8_t raw[3100];
    if (rawLen > sizeof(raw)) return 0;
    for (int y = 0; y < H; ++y) {
        raw[y * rowStride] = 0; // filter = None
        memcpy(raw + y * rowStride + 1, fb + (size_t)y * W * 3, W * 3);
    }

    // Worst case fixed-Huffman output for `rawLen` literal bytes is
    // (9 * rawLen + 7 + 3 + 7) / 8 ≈ rawLen * 9/8 + 3. Round up generously.
    static uint8_t deflated[3520];
    size_t defLen = deflateFixedHuffman(raw, rawLen, deflated);
    if (defLen == 0 || defLen > sizeof(deflated)) return 0;

    // 8 (sig) + 25 (IHDR) + 4+4+2+defLen+4+4 (IDAT) + 12 (IEND).
    const size_t expected = 8 + 25 + (12 + 2 + defLen + 4) + 12;
    if (outCap < expected) return 0;

    uint8_t* p = out;
    static const uint8_t SIG[8] = {0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A};
    memcpy(p, SIG, 8); p += 8;

    uint8_t ihdr[13];
    writeBE32(ihdr,     W);
    writeBE32(ihdr + 4, H);
    ihdr[8]  = 8;   // bit depth
    ihdr[9]  = 2;   // colour type = truecolour RGB
    ihdr[10] = 0;   // compression method = deflate
    ihdr[11] = 0;   // filter method = adaptive
    ihdr[12] = 0;   // not interlaced
    writeChunk(p, "IHDR", ihdr, 13);

    uint8_t* idatLenPos = p;
    writeBE32(p, 0); p += 4;
    uint8_t* idatTypeAndData = p;
    memcpy(p, "IDAT", 4); p += 4;

    uint8_t* zlibStart = p;
    *p++ = 0x78;    // CMF: deflate, 32 KB window
    *p++ = 0x9C;    // FLG: default compression level, FCHECK satisfies (CMF*256+FLG) % 31 == 0
    memcpy(p, deflated, defLen); p += defLen;
    writeBE32(p, adler32(raw, rawLen)); p += 4;

    size_t zlibLen = (size_t)(p - zlibStart);
    writeBE32(idatLenPos, (uint32_t)zlibLen);
    uint32_t idatCrc = crc32Std(idatTypeAndData, 4 + zlibLen);
    writeBE32(p, idatCrc); p += 4;

    writeChunk(p, "IEND", nullptr, 0);
    return (size_t)(p - out);
}
