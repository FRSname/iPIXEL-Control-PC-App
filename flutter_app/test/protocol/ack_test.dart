import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:ipixel_controller/protocol/ack.dart';

Uint8List bytes(List<int> b) => Uint8List.fromList(b);

void main() {
  group('isAck', () {
    test('empty frame is not an ack', () {
      expect(isAck(Uint8List(0)), isFalse);
    });
    test('any non-empty frame is an ack', () {
      expect(isAck(bytes([0x00])), isTrue);
      expect(isAck(bytes([0x0b, 0x00, 0x01, 0x80])), isTrue); // handshake reply
      expect(isAck(bytes([0x05, 0x00, 0x07])), isTrue); // power-on ack
    });
  });

  group('isSendImageFinalAck', () {
    test('exact len-5 final ack', () {
      // 05 _ _ _ 03
      expect(
        isSendImageFinalAck(bytes([0x05, 0x00, 0x00, 0x00, 0x03])),
        isTrue,
      );
    });

    test('len > 5 with trailing bytes still qualifies', () {
      expect(
        isSendImageFinalAck(bytes([0x05, 0x11, 0x22, 0x33, 0x03, 0xAA, 0xBB])),
        isTrue,
      );
    });

    test('len 4 frame is rejected (too short)', () {
      expect(isSendImageFinalAck(bytes([0x05, 0x00, 0x00, 0x03])), isFalse);
    });

    test('first byte not 0x05 is rejected', () {
      expect(
        isSendImageFinalAck(bytes([0x06, 0x00, 0x00, 0x00, 0x03])),
        isFalse,
      );
    });

    test('byte 4 not 0x03 is rejected (e.g. per-window ack 0x00)', () {
      expect(
        isSendImageFinalAck(bytes([0x05, 0x00, 0x00, 0x00, 0x00])),
        isFalse,
      );
      expect(
        isSendImageFinalAck(bytes([0x05, 0x00, 0x00, 0x00, 0x01])),
        isFalse,
      );
    });

    test('empty frame is not a final ack', () {
      expect(isSendImageFinalAck(Uint8List(0)), isFalse);
    });
  });
}
