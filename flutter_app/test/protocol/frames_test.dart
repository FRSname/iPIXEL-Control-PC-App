import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:ipixel_controller/protocol/frames.dart';

/// Decodes a hex string into bytes for golden-vector comparison.
Uint8List hex(String s) {
  final out = Uint8List(s.length ~/ 2);
  for (var i = 0; i < out.length; i++) {
    out[i] = int.parse(s.substring(i * 2, i * 2 + 2), radix: 16);
  }
  return out;
}

String toHex(List<int> b) =>
    b.map((x) => x.toRadixString(16).padLeft(2, '0')).join();

Uint8List concat(List<Uint8List> chunks) {
  final total = chunks.fold<int>(0, (a, c) => a + c.length);
  final out = Uint8List(total);
  var pos = 0;
  for (final c in chunks) {
    out.setRange(pos, pos + c.length, c);
    pos += c.length;
  }
  return out;
}

void main() {
  // All golden vectors below were generated once by executing the vendored
  // pypixelcolor package under a Python 3.13 throwaway venv:
  //   from pypixelcolor.commands.send_image import _build_send_plan
  //   from pypixelcolor.commands.set_brightness import set_brightness
  //   from pypixelcolor.commands.set_power import set_power
  //   from pypixelcolor.lib.internal_commands import build_get_device_info_command
  // and printing `.windows[0].data.hex()`.

  group('buildHandshake', () {
    test('encodes fixed time bytes', () {
      // Source layout: [8,0,1,0x80,hour,minute,second,0]
      // (pyref lib/internal_commands.py lines 26-35).
      final frame = buildHandshake(DateTime(2026, 7, 21, 13, 45, 7));
      expect(toHex(frame), '080001800d2d0700');
    });

    test('encodes midnight (all-zero time)', () {
      final frame = buildHandshake(DateTime(2026, 1, 1, 0, 0, 0));
      expect(toHex(frame), '0800018000000000');
    });

    test('encodes max time components 23:59:59', () {
      final frame = buildHandshake(DateTime(2026, 1, 1, 23, 59, 59));
      expect(toHex(frame), '08000180173b3b00');
    });
  });

  group('buildPower', () {
    test('on', () {
      // pyref set_power(True) -> 0500070101
      expect(toHex(buildPower(true)), '0500070101');
    });
    test('off', () {
      // pyref set_power(False) -> 0500070100
      expect(toHex(buildPower(false)), '0500070100');
    });
  });

  group('buildBrightness', () {
    test('level 0', () {
      // pyref set_brightness(0) -> 0500048000
      expect(toHex(buildBrightness(0)), '0500048000');
    });
    test('level 50', () {
      // pyref set_brightness(50) -> 0500048032
      expect(toHex(buildBrightness(50)), '0500048032');
    });
    test('level 100', () {
      // pyref set_brightness(100) -> 0500048064
      expect(toHex(buildBrightness(100)), '0500048064');
    });
    test('rejects out-of-range low', () {
      expect(() => buildBrightness(-1), throwsArgumentError);
    });
    test('rejects out-of-range high', () {
      expect(() => buildBrightness(101), throwsArgumentError);
    });
  });

  group('buildSendImageFrames', () {
    // deadbeef PNG: pngLen=4, crc32=0x7c9ca35a.
    final png4 = hex('deadbeef');
    const png4Message =
        '1300020000040000005aa39c7c0000deadbeef'; // pyref golden

    test(
      'single-chunk message matches pyref golden (prefix, crc LE, tail)',
      () {
        final frames = buildSendImageFrames(png4, chunkSize: 244);
        expect(frames.length, 1);
        expect(toHex(frames.single), png4Message);
      },
    );

    test('prefix equals 15 + pngLen, little-endian', () {
      final frames = buildSendImageFrames(png4, chunkSize: 244);
      final msg = frames.single;
      // prefix bytes 0x13,0x00 == 19 == 15 + 4.
      expect(msg[0] | (msg[1] << 8), 15 + png4.length);
    });

    test('crc is stored little-endian in the frame', () {
      final frames = buildSendImageFrames(png4, chunkSize: 244);
      final msg = frames.single;
      // Frame bytes 9..12 = 5a a3 9c 7c (LE of 0x7c9ca35a).
      expect(msg.sublist(9, 13), <int>[0x5a, 0xa3, 0x9c, 0x7c]);
    });

    test('slot occupies the second tail byte', () {
      // pyref _build_send_plan(save_slot=3) -> tail "0003".
      final frames = buildSendImageFrames(png4, slot: 3, chunkSize: 244);
      expect(toHex(frames.single), '1300020000040000005aa39c7c0003deadbeef');
    });

    test('182-byte png: chunk boundaries at 244 (single) and 182 (split)', () {
      // pyref: message len 197. @244 -> [197]; @182 -> [182, 15].
      final png182 = Uint8List.fromList(List<int>.generate(182, (i) => i));
      final at244 = buildSendImageFrames(png182, chunkSize: 244);
      expect(at244.map((c) => c.length).toList(), <int>[197]);

      final at182 = buildSendImageFrames(png182, chunkSize: 182);
      expect(at182.map((c) => c.length).toList(), <int>[182, 15]);
      // Reassembly is order-preserving and lossless.
      expect(toHex(concat(at182)), toHex(at244.single));
    });

    test('300-byte png: split at 244 and at 182 match pyref sizes', () {
      // pyref: message len 315. @244 -> [244, 71]; @182 -> [182, 133].
      final png300 = Uint8List.fromList(
        List<int>.generate(300, (i) => (i * 7 + 3) & 0xFF),
      );
      final at244 = buildSendImageFrames(png300, chunkSize: 244);
      expect(at244.map((c) => c.length).toList(), <int>[244, 71]);

      final at182 = buildSendImageFrames(png300, chunkSize: 182);
      expect(at182.map((c) => c.length).toList(), <int>[182, 133]);

      const png300Message =
          '3b010200002c010000ce570ede0000'
          '030a11181f262d343b424950575e656c737a81888f969da4abb2b9c0c7ced5dce3'
          'eaf1f8ff060d141b222930373e454c535a61686f767d848b9299a0a7aeb5bcc3ca'
          'd1d8dfe6edf4fb020910171e252c333a41484f565d646b727980878e959ca3aab1'
          'b8bfc6cdd4dbe2e9f0f7fe050c131a21282f363d444b525960676e757c838a9198'
          '9fa6adb4bbc2c9d0d7dee5ecf3fa01080f161d242b323940474e555c636a71787f'
          '868d949ba2a9b0b7bec5ccd3dae1e8eff6fd040b121920272e353c434a51585f66'
          '6d747b828990979ea5acb3bac1c8cfd6dde4ebf2f900070e151c232a31383f464d'
          '545b626970777e858c939aa1a8afb6bdc4cbd2d9e0e7eef5fc030a11181f262d34'
          '3b424950575e656c737a81888f969da4abb2b9c0c7ced5dce3eaf1f8ff060d141b'
          '222930';
      expect(toHex(concat(at244)), png300Message);
    });

    test('chunkSize larger than message yields one chunk', () {
      final frames = buildSendImageFrames(png4, chunkSize: 4096);
      expect(frames.length, 1);
    });

    test('chunkSize of 1 splits into single bytes', () {
      final frames = buildSendImageFrames(png4, chunkSize: 1);
      expect(frames.length, 15 + png4.length);
      expect(frames.every((c) => c.length == 1), isTrue);
    });

    test(
      'message an exact multiple of chunkSize has no trailing empty chunk',
      () {
        // Choose pngLen so total message == 2 * chunkSize exactly.
        // message = 15 + pngLen; for chunkSize 182 -> 2*182 = 364 -> pngLen 349.
        const chunkSize = 182;
        final png = Uint8List.fromList(
          List<int>.generate(2 * chunkSize - 15, (i) => i & 0xFF),
        );
        final frames = buildSendImageFrames(png, chunkSize: chunkSize);
        expect(frames.length, 2);
        expect(frames.map((c) => c.length).toList(), <int>[
          chunkSize,
          chunkSize,
        ]);
        expect(frames.every((c) => c.isNotEmpty), isTrue);
      },
    );

    test('accepts the maximum single-window png and rejects one byte more', () {
      // pyref single-window limit: window_size = 12 * 1024 = 12288 bytes
      // (send_image.py line 335 / send_plan.py line 19).
      const maxLen = 12 * 1024;
      final maxPng = Uint8List.fromList(
        List<int>.generate(maxLen, (i) => i & 0xFF),
      );
      final frames = buildSendImageFrames(maxPng, chunkSize: 244);
      expect(concat(frames).length, 15 + maxLen);
      // Prefix still fits in u16 and round-trips exactly.
      final msg = concat(frames);
      expect(msg[0] | (msg[1] << 8), 15 + maxLen);

      final tooBig = Uint8List.fromList(
        List<int>.generate(maxLen + 1, (i) => i & 0xFF),
      );
      expect(
        () => buildSendImageFrames(tooBig, chunkSize: 244),
        throwsArgumentError,
      );
    });

    test('returned chunk list is unmodifiable', () {
      final frames = buildSendImageFrames(png4, chunkSize: 244);
      expect(() => frames.add(Uint8List(0)), throwsUnsupportedError);
    });

    test('rejects empty png', () {
      expect(
        () => buildSendImageFrames(Uint8List(0), chunkSize: 244),
        throwsArgumentError,
      );
    });

    test('rejects non-positive chunkSize', () {
      expect(
        () => buildSendImageFrames(png4, chunkSize: 0),
        throwsArgumentError,
      );
    });

    test('rejects slot out of byte range', () {
      expect(
        () => buildSendImageFrames(png4, slot: 256, chunkSize: 244),
        throwsArgumentError,
      );
      expect(
        () => buildSendImageFrames(png4, slot: -1, chunkSize: 244),
        throwsArgumentError,
      );
    });
  });
}
