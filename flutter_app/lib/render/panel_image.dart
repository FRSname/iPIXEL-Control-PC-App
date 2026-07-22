/// 64x16 panel canvas operations: build a canvas, fit arbitrary images by
/// letterbox or crop, composite, and encode to PNG.
///
/// Pure Dart on top of the `image` package. No `dart:ui`, so it runs in plain
/// `flutter test` VM tests and inside isolates.
library;

import 'dart:math' as math;
import 'dart:typed_data';

import 'package:image/image.dart' as img;
import 'package:ipixel_controller/render/blend.dart';
import 'package:ipixel_controller/render/sprite_font.dart' show parseHexColor;

/// Panel dimensions in pixels.
const int panelWidth = 64;
const int panelHeight = 16;

/// How an arbitrary source image is mapped onto the fixed panel canvas.
enum PanelFit {
  /// Scale to fit entirely inside the canvas (preserve aspect), pad with bg.
  letterbox,

  /// Scale to cover the whole canvas (preserve aspect), centre-crop overflow.
  crop,
}

/// Creates a fresh RGB canvas of [width]x[height] filled with [bgColor].
img.Image newCanvas({
  int width = panelWidth,
  int height = panelHeight,
  String bgColor = '#000000',
}) {
  final canvas = img.Image(width: width, height: height, numChannels: 3);
  img.fill(canvas, color: parseHexColor(bgColor));
  return canvas;
}

/// Fits [src] onto a [width]x[height] canvas using [fit], centred.
///
/// * [PanelFit.letterbox] scales the whole image inside the canvas and pads the
///   remaining space with [bgColor].
/// * [PanelFit.crop] scales the image to cover the canvas and centre-crops the
///   overflow.
///
/// Uses nearest-neighbour resampling for deterministic, pixel-crisp output on
/// the low-resolution panel.
img.Image fitImage(
  img.Image src, {
  int width = panelWidth,
  int height = panelHeight,
  String bgColor = '#000000',
  PanelFit fit = PanelFit.letterbox,
  img.Interpolation interpolation = img.Interpolation.nearest,
}) {
  if (src.width <= 0 || src.height <= 0) {
    throw ArgumentError.value(
      '${src.width}x${src.height}',
      'src',
      'Source image must have positive dimensions',
    );
  }
  final scaleFitInside = math.min(width / src.width, height / src.height);
  final scaleCover = math.max(width / src.width, height / src.height);
  final scale = fit == PanelFit.letterbox ? scaleFitInside : scaleCover;

  // Scale is bounded by target/src, so rounded dimensions are already sane;
  // the max(1, ...) only guards the degenerate "rounds to zero" case.
  final newW = math.max(1, (src.width * scale).round());
  final newH = math.max(1, (src.height * scale).round());
  final resized = img.copyResize(
    src,
    width: newW,
    height: newH,
    interpolation: interpolation,
  );

  final canvas = newCanvas(width: width, height: height, bgColor: bgColor);
  // floorDiv keeps centering symmetric even when the offset is negative
  // (crop mode, where the resized image is larger than the canvas).
  final offsetX = floorDiv(width - newW, 2);
  final offsetY = floorDiv(height - newH, 2);
  compositeOnto(canvas, resized, offsetX, offsetY);
  return canvas;
}

/// Alpha-composites [src] onto [dst] at ([dx],[dy]), respecting [src]'s alpha.
///
/// Pixels falling outside [dst] are clipped. Mirrors PIL's masked `paste`.
void compositeOnto(img.Image dst, img.Image src, int dx, int dy) {
  for (var sy = 0; sy < src.height; sy++) {
    final y = dy + sy;
    if (y < 0 || y >= dst.height) {
      continue;
    }
    for (var sx = 0; sx < src.width; sx++) {
      final x = dx + sx;
      if (x < 0 || x >= dst.width) {
        continue;
      }
      final sp = src.getPixel(sx, sy);
      final m = sp.a.toInt();
      if (m == 0) {
        continue;
      }
      if (m == 255) {
        dst.setPixelRgb(x, y, sp.r, sp.g, sp.b);
        continue;
      }
      final dp = dst.getPixel(x, y);
      final inv = 255 - m;
      final r = mulDiv255(dp.r.toInt(), inv) + mulDiv255(sp.r.toInt(), m);
      final g = mulDiv255(dp.g.toInt(), inv) + mulDiv255(sp.g.toInt(), m);
      final b = mulDiv255(dp.b.toInt(), inv) + mulDiv255(sp.b.toInt(), m);
      dst.setPixelRgb(x, y, r, g, b);
    }
  }
}

/// Fills [canvas] with [bgColor] in place.
void fillBackground(img.Image canvas, String bgColor) {
  img.fill(canvas, color: parseHexColor(bgColor));
}

/// Encodes [image] to PNG bytes.
Uint8List encodePanelPng(img.Image image) => img.encodePng(image);
