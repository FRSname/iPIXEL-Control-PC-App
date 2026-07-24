import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;

import 'package:ipixel_controller/features/image/gif_frames.dart';
import 'package:ipixel_controller/features/image/image_fit.dart';
import 'package:ipixel_controller/render/panel_image.dart';

/// Builds a two-frame animated GIF: red for [firstMs], green for [secondMs].
///
/// Durations are multiples of 10 ms so they survive the GIF format's
/// centisecond delay field cleanly on the decode round-trip.
Uint8List _twoFrameGif({required int firstMs, required int secondMs}) {
  final anim = img.Image(width: 8, height: 8, numChannels: 3)
    ..frameDuration = firstMs;
  img.fill(anim, color: img.ColorRgb8(255, 0, 0));
  final second = anim.addFrame()..frameDuration = secondMs;
  img.fill(second, color: img.ColorRgb8(0, 255, 0));
  return img.encodeGif(anim);
}

void main() {
  group('gifFrameIntervalMs', () {
    test('floors sub-320 ms durations to the panel-safe minimum', () {
      expect(gifFrameIntervalMs(40), kGifMinFrameIntervalMs);
      expect(gifFrameIntervalMs(100), kGifMinFrameIntervalMs);
      expect(gifFrameIntervalMs(0), kGifMinFrameIntervalMs);
    });

    test('keeps durations already at or above the floor', () {
      expect(
        gifFrameIntervalMs(kGifMinFrameIntervalMs),
        kGifMinFrameIntervalMs,
      );
      expect(gifFrameIntervalMs(500), 500);
      expect(gifFrameIntervalMs(1000), 1000);
    });

    test('is never below the floor for any non-negative input', () {
      for (var ms = 0; ms <= 700; ms += 10) {
        expect(
          gifFrameIntervalMs(ms),
          greaterThanOrEqualTo(kGifMinFrameIntervalMs),
        );
      }
    });
  });

  group('extractGifFrames', () {
    test('extracts every frame as a 64x16 panel PNG', () {
      final frames = extractGifFrames(
        _twoFrameGif(firstMs: 100, secondMs: 500),
      );
      expect(frames, hasLength(2));
      for (final frame in frames) {
        final decoded = img.decodePng(frame.png)!;
        expect(decoded.width, panelWidth);
        expect(decoded.height, panelHeight);
      }
    });

    test('preserves each frame authored duration (unclamped)', () {
      final frames = extractGifFrames(
        _twoFrameGif(firstMs: 100, secondMs: 500),
      );
      // Raw durations are kept; the panel floor is applied only at play time.
      expect(frames[0].durationMs, 100);
      expect(frames[1].durationMs, 500);
      expect(
        frames[0].durationMs,
        lessThan(kGifMinFrameIntervalMs),
        reason: 'the fast frame is below the floor pre-clamp',
      );
    });

    test('fits frames by the requested mode and background', () {
      // Letterbox an 8x8 (square) frame onto 64x16 with a white background: the
      // corners are padding (white), so the bg colour is honoured per frame.
      final frames = extractGifFrames(
        _twoFrameGif(firstMs: 100, secondMs: 500),
        fit: PanelFit.letterbox,
        bgColor: '#FFFFFF',
      );
      final firstDecoded = img.decodePng(frames.first.png)!;
      final corner = firstDecoded.getPixel(0, 0);
      expect(corner.r, 255);
      expect(corner.g, 255);
      expect(corner.b, 255);
    });

    test('throws ImageDecodeException on non-GIF bytes', () {
      expect(
        () => extractGifFrames(Uint8List.fromList(<int>[9, 9, 9, 9])),
        throwsA(isA<ImageDecodeException>()),
      );
    });
  });
}
