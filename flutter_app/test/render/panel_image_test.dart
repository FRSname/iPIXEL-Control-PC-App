// Tests for lib/render/panel_image.dart.
import 'package:image/image.dart' as img;
import 'package:ipixel_controller/render/panel_image.dart';
import 'package:flutter_test/flutter_test.dart';

img.Image solid(int w, int h, int r, int g, int b) {
  final im = img.Image(width: w, height: h, numChannels: 3);
  img.fill(im, color: img.ColorRgb8(r, g, b));
  return im;
}

void main() {
  group('newCanvas', () {
    test('is 64x16 and filled with the background colour', () {
      final c = newCanvas(bgColor: '#123456');
      expect(c.width, panelWidth);
      expect(c.height, panelHeight);
      final p = c.getPixel(0, 0);
      expect(p.r.toInt(), 0x12);
      expect(p.g.toInt(), 0x34);
      expect(p.b.toInt(), 0x56);
    });
  });

  group('fitImage', () {
    test('letterbox pads a tall square with background and centres it', () {
      final src = solid(8, 8, 255, 0, 0); // red 8x8
      final out = fitImage(src, bgColor: '#000000', fit: PanelFit.letterbox);
      expect(out.width, 64);
      expect(out.height, 16);
      // scale = min(64/8, 16/8) = 2 -> 16x16, centred at x=24.
      // Corner is background (black), centre is the source (red).
      final corner = out.getPixel(0, 0);
      expect([corner.r.toInt(), corner.g.toInt(), corner.b.toInt()], [0, 0, 0]);
      final centre = out.getPixel(32, 8);
      expect(
        [centre.r.toInt(), centre.g.toInt(), centre.b.toInt()],
        [255, 0, 0],
      );
      // Just left of the centred 16px block is still background.
      final edge = out.getPixel(10, 8);
      expect([edge.r.toInt(), edge.g.toInt(), edge.b.toInt()], [0, 0, 0]);
    });

    test('crop covers the whole canvas (no background visible)', () {
      final src = solid(8, 8, 0, 128, 255);
      final out = fitImage(src, bgColor: '#000000', fit: PanelFit.crop);
      expect(out.width, 64);
      expect(out.height, 16);
      // Every pixel should be the source colour (uniform cover crop).
      for (final (x, y) in [(0, 0), (63, 15), (32, 8)]) {
        final p = out.getPixel(x, y);
        expect([p.r.toInt(), p.g.toInt(), p.b.toInt()], [0, 128, 255]);
      }
    });
  });

  group('compositeOnto', () {
    test('respects source alpha (transparent pixels skipped)', () {
      final dst = newCanvas(bgColor: '#ffffff');
      final src = img.Image(width: 4, height: 4, numChannels: 4);
      // Left half opaque black, right half fully transparent.
      for (var y = 0; y < 4; y++) {
        for (var x = 0; x < 4; x++) {
          src.setPixelRgba(x, y, 0, 0, 0, x < 2 ? 255 : 0);
        }
      }
      compositeOnto(dst, src, 0, 0);
      expect(dst.getPixel(0, 0).r.toInt(), 0); // opaque black painted
      expect(dst.getPixel(3, 0).r.toInt(), 255); // transparent -> unchanged
    });

    // Half-transparent blue (0,0,255, a=128) over white (255,255,255).
    // PIL MULDIV255 blend, m=128, inv=127:
    //   R = mulDiv255(255,127) + mulDiv255(0,128)   = 127 + 0   = 127
    //   G = mulDiv255(255,127) + mulDiv255(0,128)   = 127 + 0   = 127
    //   B = mulDiv255(255,127) + mulDiv255(255,128) = 127 + 128 = 255
    test('blends a half-alpha pixel exactly like PIL paste-with-mask', () {
      final dst = newCanvas(bgColor: '#ffffff');
      final src = img.Image(width: 1, height: 1, numChannels: 4);
      src.setPixelRgba(0, 0, 0, 0, 255, 128);
      compositeOnto(dst, src, 0, 0);
      final p = dst.getPixel(0, 0);
      expect([p.r.toInt(), p.g.toInt(), p.b.toInt()], [127, 127, 255]);
    });
  });

  group('fitImage guards', () {
    test('throws ArgumentError for a zero-dimension source', () {
      final degenerate = img.Image(width: 0, height: 0, numChannels: 3);
      expect(() => fitImage(degenerate), throwsArgumentError);
      // A valid 1x1 source must NOT throw.
      expect(() => fitImage(solid(1, 1, 0, 0, 0)), returnsNormally);
    });

    test('crop mode with a larger scaled image uses floored centering', () {
      // src 51x7 -> cover-scale to 64x16: scale = max(64/51, 16/7) = 16/7,
      // newW = round(51 * 16/7) = 117 (odd), newH = round(7 * 16/7) = 16.
      // offsetX = floorDiv(64 - 117, 2) = floorDiv(-53, 2) = -27 (NOT -26).
      // A uniform source still lets us assert the branch runs and fully
      // covers the canvas without a crash; the floor semantics themselves are
      // pinned by blend_test's floorDiv(-53/-5, 2) cases.
      final src = solid(51, 7, 10, 20, 30);
      final out = fitImage(src, fit: PanelFit.crop);
      expect(out.width, 64);
      expect(out.height, 16);
      for (final (x, y) in [(0, 0), (63, 15), (32, 8)]) {
        final p = out.getPixel(x, y);
        expect([p.r.toInt(), p.g.toInt(), p.b.toInt()], [10, 20, 30]);
      }
    });
  });

  group('encodePanelPng', () {
    test('round-trips through PNG decode preserving pixels', () {
      final canvas = newCanvas(bgColor: '#00ff00');
      canvas.setPixelRgb(5, 5, 255, 0, 0);
      final bytes = encodePanelPng(canvas);
      final decoded = img.decodePng(bytes)!;
      expect(decoded.width, 64);
      expect(decoded.height, 16);
      final bg = decoded.getPixel(0, 0);
      expect([bg.r.toInt(), bg.g.toInt(), bg.b.toInt()], [0, 255, 0]);
      final dot = decoded.getPixel(5, 5);
      expect([dot.r.toInt(), dot.g.toInt(), dot.b.toInt()], [255, 0, 0]);
    });
  });
}
