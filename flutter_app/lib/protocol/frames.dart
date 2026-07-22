/// Pure builders for the iPixel BLE wire protocol.
///
/// Every byte layout here is ported directly from the vendored pypixelcolor
/// Python sources (`tool/pyref/.venv/.../site-packages/pypixelcolor/`). Source
/// file + line citations accompany each builder. No BLE or Flutter code lives
/// here — only `dart:typed_data`.
library;

import 'dart:typed_data';

import 'crc32.dart';

/// Default GATT write chunk size used by pypixelcolor
/// (`lib/transport/send_plan.py::SendPlan.chunk_size = 244`, matching an MTU of
/// 247 minus the 3-byte ATT header).
const int _kDefaultChunkSize = 244;

/// Fixed header + framing overhead added around the PNG payload in a single
/// `send_image` window. Derived from pyref `commands/send_image.py`:
///   prefix(2) + [0x02,0x00,option](3) + pngLen(4) + crc32(4) + [0x00,slot](2).
const int _kSendImageOverhead = 15;

/// Maximum PNG payload carried by a single window.
///
/// pyref splits payloads larger than `window_size = 12 * 1024` (12288 bytes)
/// across multiple windows (pyref `commands/send_image.py` line 335, and the
/// `SendPlan.window_size` default in `lib/transport/send_plan.py` line 19).
/// This builder is single-window only, so it enforces that documented bound.
/// It is also comfortably inside the u16 prefix ceiling (0xFFFF - 15 = 65520),
/// which guarantees the little-endian prefix at offset 0 never truncates.
const int _kMaxSingleWindowPng = 12 * 1024;

/// Builds the `get_device_info` / time-sync handshake payload.
///
/// Layout: `[8, 0, 1, 0x80, hour, minute, second, 0]`.
/// Source: pyref `lib/internal_commands.py::build_get_device_info_command`
/// (lines 26-35); identical to `commands/set_time.py::set_time` (lines 39-48).
/// The panel accepts and ACKs `send_image` frames before this handshake but
/// will not render their content, so it must be sent right after subscribing.
Uint8List buildHandshake(DateTime now) {
  return Uint8List.fromList(<int>[
    8, // Command length
    0, // Reserved
    1, // Sub-command
    0x80, // Command type id (-128 signed)
    now.hour,
    now.minute,
    now.second,
    0, // Language / reserved
  ]);
}

/// Builds the power on/off payload.
///
/// Layout: `[5, 0, 7, 1, on ? 1 : 0]`.
/// Source: pyref `commands/set_power.py::set_power` (lines 14-20).
Uint8List buildPower(bool on) {
  return Uint8List.fromList(<int>[
    5, // Command length
    0, // Reserved
    7, // Command id
    1, // Command type id
    on ? 1 : 0, // Power state
  ]);
}

/// Builds the brightness payload.
///
/// Layout: `[5, 0, 4, 0x80, level]` where `level` is 0-100.
/// Source: pyref `commands/set_brightness.py::set_brightness` (lines 12-18).
/// The type-id byte here is `0x80`, NOT `1` as in `set_power`; this was read
/// from the source rather than guessed.
///
/// Throws [ArgumentError] if [level] is outside 0-100 (mirrors the Python
/// `ValueError` guard on line 10-11).
Uint8List buildBrightness(int level) {
  if (level < 0 || level > 100) {
    throw ArgumentError.value(
      level,
      'level',
      'Brightness level must be between 0 and 100',
    );
  }
  return Uint8List.fromList(<int>[
    5, // Command length
    0, // Reserved
    4, // Command id
    0x80, // Command type id
    level, // Brightness value
  ]);
}

/// Builds the fully-framed `send_image` payload for a single window and splits
/// it into GATT write chunks of at most [chunkSize] bytes.
///
/// Frame layout (ported from pyref `commands/send_image.py::_build_send_plan`,
/// lines 322-359, for the non-GIF / first-window case):
///
/// ```
/// [u16 LE prefix = 15 + pngLen]   // _len_prefix_for: 2 + len(frame)
/// [0x02, 0x00, 0x00]              // [0x02, 0x00, option]; option = 0 for window 0
/// [u32 LE pngLen]                 // _frame_size_bytes(len, 8)
/// [u32 LE crc32(png)]             // _crc32_le: binascii.crc32, little-endian
/// [0x00, slot]                    // cur_tail = [0x00, save_slot]
/// [png bytes]
/// ```
///
/// The panel concatenates chunks, so boundaries are arbitrary — pyref chunks
/// the complete message (prefix included) in `send_plan.py::_chunk_bytes`.
///
/// Note on slot byte position: the slot occupies the SECOND byte of the tail
/// (`[0x00, slot]`), matching the blueprint's `[0x00, 0x00]` for slot 0. This
/// was confirmed against a pyref plan built with `save_slot=3`, which produced
/// a tail of `00 03`. No discrepancy with the blueprint framing spec.
///
/// This builder targets single-window transfers only (payloads under
/// pyref's 12 KB `window_size`). A real 64x16 PNG is a few hundred bytes, well
/// within that limit. Throws [ArgumentError] if [chunkSize] < 1, [slot] is
/// negative or > 255, [png] is empty, or [png] exceeds the single-window limit
/// of [_kMaxSingleWindowPng] bytes.
List<Uint8List> buildSendImageFrames(
  Uint8List png, {
  int slot = 0,
  int chunkSize = _kDefaultChunkSize,
}) {
  if (png.isEmpty) {
    throw ArgumentError.value(png, 'png', 'PNG payload must not be empty');
  }
  if (png.length > _kMaxSingleWindowPng) {
    throw ArgumentError.value(
      png.length,
      'png.length',
      'exceeds single-window limit of $_kMaxSingleWindowPng bytes',
    );
  }
  if (chunkSize < 1) {
    throw ArgumentError.value(chunkSize, 'chunkSize', 'must be >= 1');
  }
  if (slot < 0 || slot > 0xFF) {
    throw ArgumentError.value(slot, 'slot', 'must be 0-255');
  }

  final pngLen = png.length;
  final crc = crc32(png);
  final message = Uint8List(_kSendImageOverhead + pngLen);
  final data = ByteData.sublistView(message);

  // Prefix = 2 + len(frame after prefix) = 15 + pngLen. Equal to total length.
  data.setUint16(0, _kSendImageOverhead + pngLen, Endian.little);
  message[2] = 0x02;
  message[3] = 0x00;
  message[4] = 0x00; // option = 0 for the first (only) window
  data.setUint32(5, pngLen, Endian.little);
  data.setUint32(9, crc, Endian.little);
  message[13] = 0x00;
  message[14] = slot;
  message.setRange(_kSendImageOverhead, message.length, png);

  return _chunk(message, chunkSize);
}

/// Splits [buffer] into consecutive slices of at most [size] bytes.
List<Uint8List> _chunk(Uint8List buffer, int size) {
  final chunks = <Uint8List>[];
  for (var pos = 0; pos < buffer.length; pos += size) {
    final end = pos + size < buffer.length ? pos + size : buffer.length;
    chunks.add(Uint8List.sublistView(buffer, pos, end));
  }
  return List.unmodifiable(chunks);
}
