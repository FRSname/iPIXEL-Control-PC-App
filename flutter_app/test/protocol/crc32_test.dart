import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:ipixel_controller/protocol/crc32.dart';

void main() {
  group('crc32', () {
    test('matches canonical IEEE test vector "123456789"', () {
      // Standard CRC-32 check value; also verified via Python
      // `binascii.crc32(b"123456789") & 0xFFFFFFFF == 0xCBF43926`.
      final data = Uint8List.fromList(ascii.encode('123456789'));
      expect(crc32(data), 0xCBF43926);
    });

    test('empty input yields 0', () {
      expect(crc32(Uint8List(0)), 0);
    });

    test('matches pypixelcolor for the deadbeef send_image payload', () {
      // Provenance: pyref binascii.crc32(bytes([0xDE,0xAD,0xBE,0xEF])).
      final data = Uint8List.fromList(<int>[0xDE, 0xAD, 0xBE, 0xEF]);
      expect(crc32(data), 0x7C9CA35A);
    });

    test('matches pypixelcolor for a 300-byte payload', () {
      // Provenance: pyref crc32 of bytes([(i*7+3)&0xFF for i in range(300)]).
      final data = Uint8List.fromList(
        List<int>.generate(300, (i) => (i * 7 + 3) & 0xFF),
      );
      expect(crc32(data), 0xDE0E57CE);
    });
  });
}
