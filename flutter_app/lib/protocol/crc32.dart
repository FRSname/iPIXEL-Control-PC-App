/// IEEE CRC-32 (reflected input/output, polynomial 0xEDB88320).
///
/// This matches Python's `binascii.crc32`, which is what pypixelcolor uses to
/// compute the checksum embedded in a `send_image` frame
/// (see pyref `commands/send_image.py::_crc32_le`, which does
/// `binascii.crc32(data) & 0xFFFFFFFF`).
///
/// Verified against the canonical test vector: `crc32("123456789")`
/// == `0xCBF43926`.
library;

import 'dart:typed_data';

/// Reflected polynomial for the IEEE 802.3 / zlib CRC-32.
const int _kPolynomial = 0xEDB88320;

/// 32-bit mask used to keep intermediate results inside an unsigned 32-bit
/// range on platforms where `int` is 64-bit.
const int _kMask32 = 0xFFFFFFFF;

/// Lazily-built 256-entry lookup table.
final Uint32List _table = _buildTable();

Uint32List _buildTable() {
  final table = Uint32List(256);
  for (var i = 0; i < 256; i++) {
    var crc = i;
    for (var bit = 0; bit < 8; bit++) {
      if ((crc & 1) != 0) {
        crc = (crc >> 1) ^ _kPolynomial;
      } else {
        crc >>= 1;
      }
    }
    table[i] = crc;
  }
  return table;
}

/// Computes the IEEE CRC-32 of [data] and returns it as an unsigned 32-bit int.
int crc32(Uint8List data) {
  var crc = _kMask32;
  for (final byte in data) {
    crc = (crc >> 8) ^ _table[(crc ^ byte) & 0xFF];
  }
  return (crc ^ _kMask32) & _kMask32;
}
