#include "png_encode.h"
#include <string.h>

// ============================================================================
// LZ77 + fixed-Huffman deflate encoder. Just big enough to compress a 64x16
// RGB framebuffer down to a few hundred bytes — comparable to what PIL emits
// on the desktop side. The iPixel panel firmware apparently has a small
// in-RAM PNG buffer; an uncompressed-literal-only stream (~3 KB) is ACKed at
// the protocol layer but silently discarded by the decoder, whereas a real
// LZ77-compressed PNG renders correctly.
//
// Tables and bit-layout are straight from RFC 1951 §3.2.5/§3.2.6.
// Memory: ~24 KB for hash + previous-position chain. Fits comfortably given
// ESP32's free RAM (typically 200 KB+ for our app).
// ============================================================================

static uint32_t CRC_TABLE[256];
static bool     CRC_INITED = false;

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

// Bit accumulator for the deflate stream. Bits within a byte pack LSB-first;
// non-Huffman fields go LSB-first, Huffman codes go MSB-first (RFC 1951 §3.1.1).
struct BitWr {
    uint8_t* out;
    size_t   pos;
    uint32_t acc;
    int      nbits;
};

static inline void bwBit(BitWr& w, int b) {
    if (b) w.acc |= ((uint32_t)1 << w.nbits);
    if (++w.nbits >= 8) {
        w.out[w.pos++] = (uint8_t)(w.acc & 0xFF);
        w.acc >>= 8;
        w.nbits -= 8;
    }
}

static void bwLSB(BitWr& w, uint32_t v, int n) {
    for (int i = 0; i < n; ++i) bwBit(w, (v >> i) & 1);
}

static void bwHuff(BitWr& w, uint32_t code, int n) {
    for (int i = n - 1; i >= 0; --i) bwBit(w, (code >> i) & 1);
}

static void bwFlush(BitWr& w) {
    if (w.nbits > 0) { w.out[w.pos++] = (uint8_t)(w.acc & 0xFF); w.acc = 0; w.nbits = 0; }
}

// Length code table — 29 entries indexed by length-symbol (0..28).
// Length symbol N corresponds to deflate symbol 257+N.
static const uint16_t LEN_BASE [29] = {
    3,4,5,6,7,8,9,10, 11,13,15,17, 19,23,27,31,
    35,43,51,59, 67,83,99,115, 131,163,195,227, 258
};
static const uint8_t  LEN_EXTRA[29] = {
    0,0,0,0,0,0,0,0, 1,1,1,1, 2,2,2,2,
    3,3,3,3, 4,4,4,4, 5,5,5,5, 0
};

// Distance code table — 30 entries.
static const uint16_t DIST_BASE [30] = {
    1,2,3,4, 5,7, 9,13, 17,25, 33,49, 65,97, 129,193,
    257,385, 513,769, 1025,1537, 2049,3073, 4097,6145,
    8193,12289, 16385,24577
};
static const uint8_t  DIST_EXTRA[30] = {
    0,0,0,0, 1,1, 2,2, 3,3, 4,4, 5,5, 6,6,
    7,7, 8,8, 9,9, 10,10, 11,11, 12,12, 13,13
};

static int findLenSym(int len) {
    int i = 28;
    while (i > 0 && LEN_BASE[i] > (uint16_t)len) --i;
    return i;
}

static int findDistSym(int dist) {
    int i = 29;
    while (i > 0 && DIST_BASE[i] > (uint16_t)dist) --i;
    return i;
}

static void emitLit(BitWr& w, uint8_t b) {
    // Fixed-Huffman literals: 0..143 → 8-bit codes 0x30..0xBF
    //                         144..255 → 9-bit codes 0x190..0x1FF
    if (b < 144) bwHuff(w, 0x30u  + b,         8);
    else         bwHuff(w, 0x190u + (b - 144), 9);
}

static void emitLen(BitWr& w, int len) {
    int s = findLenSym(len);
    int sym = 257 + s;
    // RFC 1951 §3.2.6 fixed Huffman table: symbols 256..279 map to 7-bit
    // codes 0..23 — so code 0 is EOB (symbol 256), code 1 is length-symbol
    // 257 (length 3), and a length-N symbol uses code (sym - 256). Older
    // versions of this file used `sym - 257`, which collided length-3 with
    // EOB and caused decoders to terminate mid-stream.
    if (sym <= 279) bwHuff(w, (uint32_t)(sym - 256),       7);
    else            bwHuff(w, (uint32_t)(192 + sym - 280), 8);
    if (LEN_EXTRA[s]) bwLSB(w, (uint32_t)(len - LEN_BASE[s]), LEN_EXTRA[s]);
}

static void emitDist(BitWr& w, int dist) {
    int s = findDistSym(dist);
    bwHuff(w, (uint32_t)s, 5);   // distance codes are 5 bits in fixed Huffman
    if (DIST_EXTRA[s]) bwLSB(w, (uint32_t)(dist - DIST_BASE[s]), DIST_EXTRA[s]);
}

// LZ77 match-finding state. Cheap chained hash: HASH_SIZE buckets, prev[] is
// indexed by `pos & (CHAIN_MASK)` so it wraps with the active window.
static const int    HASH_BITS = 12;
static const int    HASH_SIZE = 1 << HASH_BITS;
static const int    CHAIN_LEN = 8192;          // power-of-two
static const int    CHAIN_MASK = CHAIN_LEN - 1;
static const int    MIN_MATCH = 3;
static const int    MAX_MATCH = 258;
static const int    MAX_CHAIN_WALK = 32;       // upper bound on hash-chain probes per position

static int16_t g_head[HASH_SIZE];
static int16_t g_prev[CHAIN_LEN];

static inline uint16_t hash3(const uint8_t* p) {
    uint32_t h = ((uint32_t)p[0] << 10) ^ ((uint32_t)p[1] << 5) ^ p[2];
    return (uint16_t)(h & (HASH_SIZE - 1));
}

static size_t deflateLZ77Fixed(const uint8_t* in, size_t inLen, uint8_t* out) {
    BitWr w = { out, 0, 0, 0 };

    bwLSB(w, 1, 1);   // BFINAL = 1
    bwLSB(w, 1, 2);   // BTYPE = 01 (fixed Huffman)

    for (int i = 0; i < HASH_SIZE; ++i) g_head[i] = -1;
    for (int i = 0; i < CHAIN_LEN; ++i) g_prev[i] = -1;

    int i = 0;
    while (i < (int)inLen) {
        int bestLen  = 0;
        int bestDist = 0;

        if (i + MIN_MATCH <= (int)inLen) {
            uint16_t h = hash3(in + i);
            int probe = g_head[h];
            int walks = 0;
            while (probe >= 0 && (i - probe) <= CHAIN_LEN && walks++ < MAX_CHAIN_WALK) {
                int maxL = (int)inLen - i;
                if (maxL > MAX_MATCH) maxL = MAX_MATCH;
                int len = 0;
                while (len < maxL && in[probe + len] == in[i + len]) ++len;
                if (len >= MIN_MATCH && len > bestLen) {
                    bestLen  = len;
                    bestDist = i - probe;
                    if (bestLen == MAX_MATCH) break;
                }
                probe = g_prev[probe & CHAIN_MASK];
            }
        }

        if (bestLen >= MIN_MATCH) {
            emitLen(w, bestLen);
            emitDist(w, bestDist);
            // Insert hash entries for every position covered by the match —
            // future matches benefit from seeing the full LZ77 dictionary.
            for (int k = 0; k < bestLen; ++k) {
                int p = i + k;
                if (p + MIN_MATCH <= (int)inLen) {
                    uint16_t hh = hash3(in + p);
                    g_prev[p & CHAIN_MASK] = g_head[hh];
                    g_head[hh] = (int16_t)p;
                }
            }
            i += bestLen;
        } else {
            emitLit(w, in[i]);
            if (i + MIN_MATCH <= (int)inLen) {
                uint16_t hh = hash3(in + i);
                g_prev[i & CHAIN_MASK] = g_head[hh];
                g_head[hh] = (int16_t)i;
            }
            ++i;
        }
    }

    bwHuff(w, 0, 7);   // end-of-block symbol (literal 256 → 7-bit code 0)
    bwFlush(w);
    return w.pos;
}

size_t pngEncode64x16RGB(const uint8_t* fb, uint8_t* out, size_t outCap) {
    const int    W         = 64;
    const int    H         = 16;
    const size_t rowStride = (size_t)1 + W * 3;
    const size_t rawLen    = (size_t)H * rowStride;   // 3088

    static uint8_t raw[3100];
    if (rawLen > sizeof(raw)) return 0;
    for (int y = 0; y < H; ++y) {
        raw[y * rowStride] = 0;
        memcpy(raw + y * rowStride + 1, fb + (size_t)y * W * 3, W * 3);
    }

    // Compressed output is typically <800 bytes; cap generously.
    static uint8_t deflated[2048];
    size_t defLen = deflateLZ77Fixed(raw, rawLen, deflated);
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
    ihdr[8]  = 8; ihdr[9] = 2; ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;
    writeChunk(p, "IHDR", ihdr, 13);

    uint8_t* idatLenPos = p;
    writeBE32(p, 0); p += 4;
    uint8_t* idatTypeAndData = p;
    memcpy(p, "IDAT", 4); p += 4;

    uint8_t* zlibStart = p;
    *p++ = 0x78;
    *p++ = 0x9C;
    memcpy(p, deflated, defLen); p += defLen;
    writeBE32(p, adler32(raw, rawLen)); p += 4;

    size_t zlibLen = (size_t)(p - zlibStart);
    writeBE32(idatLenPos, (uint32_t)zlibLen);
    uint32_t idatCrc = crc32Std(idatTypeAndData, 4 + zlibLen);
    writeBE32(p, idatCrc); p += 4;

    writeChunk(p, "IEND", nullptr, 0);
    return (size_t)(p - out);
}
