import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;

import 'package:ipixel_controller/features/image/image_fit.dart';
import 'package:ipixel_controller/render/panel_image.dart';

/// Encodes a solid-colour [w]x[h] RGB image to PNG bytes.
Uint8List _solidPng(int w, int h, img.Color color) {
  final image = img.Image(width: w, height: h, numChannels: 3);
  img.fill(image, color: color);
  return img.encodePng(image);
}

img.Color get _red => img.ColorRgb8(255, 0, 0);

void main() {
  group('fitImageToPanelPng dimensions', () {
    test('always produces a 64x16 panel PNG', () {
      for (final fit in PanelFit.values) {
        final png = fitImageToPanelPng(_solidPng(20, 20, _red), fit: fit);
        final decoded = img.decodePng(png)!;
        expect(decoded.width, panelWidth);
        expect(decoded.height, panelHeight);
      }
    });
  });

  group('letterbox', () {
    test('pads a non-panel-aspect image with the background colour', () {
      // A 20x20 square scales to 16x16 (min(64/20, 16/20) = 0.8), centred with
      // 24 px of padding on each side.
      final png = fitImageToPanelPng(
        _solidPng(20, 20, _red),
        fit: PanelFit.letterbox,
        bgColor: '#FFFFFF',
      );
      final decoded = img.decodePng(png)!;

      // Corner is padding (white); the centre is the source (red).
      final corner = decoded.getPixel(0, 0);
      expect(corner.r, 255);
      expect(corner.g, 255);
      expect(corner.b, 255);

      final centre = decoded.getPixel(panelWidth ~/ 2, panelHeight ~/ 2);
      expect(centre.r, 255);
      expect(centre.g, 0);
      expect(centre.b, 0);
    });

    test('a tall image is scaled to fit inside and padded left/right', () {
      // 16x64 → scale min(64/16, 16/64)=0.25 → 4x16: full panel height, thin.
      final png = fitImageToPanelPng(
        _solidPng(16, 64, _red),
        fit: PanelFit.letterbox,
        bgColor: '#FFFFFF',
      );
      final decoded = img.decodePng(png)!;
      // Left edge is padding; the centre column is the (full-height) image.
      expect(decoded.getPixel(0, 8).r, 255);
      expect(decoded.getPixel(0, 8).g, 255);
      final centre = decoded.getPixel(panelWidth ~/ 2, 8);
      expect(centre.r, 255);
      expect(centre.g, 0);
    });
  });

  group('crop', () {
    test('covers the whole panel with no background showing', () {
      // A 20x20 square scales to cover (max(64/20, 16/20)=3.2 → 64x64) and is
      // centre-cropped, so every panel pixel is the source colour.
      final png = fitImageToPanelPng(
        _solidPng(20, 20, _red),
        fit: PanelFit.crop,
        bgColor: '#FFFFFF',
      );
      final decoded = img.decodePng(png)!;
      for (final (x, y) in <(int, int)>[
        (0, 0),
        (panelWidth - 1, panelHeight - 1),
        (panelWidth ~/ 2, panelHeight ~/ 2),
      ]) {
        final pixel = decoded.getPixel(x, y);
        expect(pixel.r, 255, reason: 'crop fills ($x,$y)');
        expect(pixel.g, 0);
        expect(pixel.b, 0);
      }
    });
  });

  group('decode failures', () {
    test('throws ImageDecodeException on non-image bytes', () {
      expect(
        () => fitImageToPanelPng(Uint8List.fromList(<int>[1, 2, 3, 4])),
        throwsA(isA<ImageDecodeException>()),
      );
    });

    test('throws ImageDecodeException on a truncated image file', () {
      // A valid PNG signature + IHDR followed by truncated data: a decoder
      // claims it by signature but throws mid-parse — normalised to the domain
      // exception rather than escaping as a RangeError.
      final corrupt = Uint8List.fromList(_solidPng(8, 8, _red).sublist(0, 30));
      expect(
        () => fitImageToPanelPng(corrupt),
        throwsA(isA<ImageDecodeException>()),
      );
    });

    test(
      'crop ignores the background colour when the panel is fully covered',
      () {
        // A differently-coloured bg does not change a fully-covered panel.
        final onWhite = fitImageToPanelPng(
          _solidPng(20, 20, _red),
          fit: PanelFit.crop,
          bgColor: '#FFFFFF',
        );
        final onBlack = fitImageToPanelPng(
          _solidPng(20, 20, _red),
          fit: PanelFit.crop,
          bgColor: '#000000',
        );
        expect(img.decodePng(onWhite)!.getPixel(0, 0).r, 255);
        expect(img.decodePng(onBlack)!.getPixel(0, 0).r, 255);
      },
    );
  });
}
