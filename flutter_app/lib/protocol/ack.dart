/// Classification of BLE NOTIFY frames from the panel.
///
/// Two facts drive this (see project CLAUDE.md "Protocol invariants" and the
/// blueprint ack spec):
///  * ANY non-empty notify frame signals that a pending command was
///    acknowledged — the handshake reply, power-on ack, per-window ack and the
///    final ack all count. The ESP32 firmware and pyref both signal the ack
///    semaphore on any frame rather than filtering on a leading `0x05`.
///  * The `send_image` FINAL ack (transfer complete) is specifically
///    `len >= 5 && data[0] == 0x05 && data[4] == 0x03`. The `>=` matters:
///    trailing bytes after byte 4 are possible.
///
/// pyref's `lib/transport/ack_manager.py` additionally treats `data[4] in (0,1)`
/// as a per-window ack; the blueprint only distinguishes "any ack" from the
/// send_image final ack, which is what this classifier exposes.
library;

import 'dart:typed_data';

/// Returns `true` if [data] is any acknowledgement frame, i.e. a non-empty
/// notify payload. Signals that a pending command has been answered.
bool isAck(Uint8List data) => data.isNotEmpty;

/// Returns `true` if [data] is the `send_image` final ("transfer complete")
/// acknowledgement: `len >= 5 && data[0] == 0x05 && data[4] == 0x03`.
bool isSendImageFinalAck(Uint8List data) {
  return data.length >= 5 && data[0] == 0x05 && data[4] == 0x03;
}
