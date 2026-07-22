/// Sprite font rendering, ported from
/// `ipixel_controller/services/sprite_font.py`.
///
/// Pure Dart on top of the `image` package. No `dart:ui`, so it runs in plain
/// `flutter test` VM tests and inside isolates.
///
/// Behavioural parity notes (verified against the Python reference and the
/// legacy monolith `ipixel_controller.py`):
///
/// * Glyphs are NOT recoloured by a text colour. The Python code composites
///   each glyph onto a background-filled canvas using the glyph's own alpha
///   channel as the mask (`base.paste(glyph, (x, 0), glyph)`), preserving the
///   sprite sheet's baked-in RGB. Only [bgColor] is applied, as the fill of the
///   base canvas. There is no black-detection threshold anywhere in the
///   reference; the compositing here reproduces PIL's `paste`-with-mask blend
///   exactly (see [_paste]).
library;

import 'dart:io';
import 'dart:typed_data';

import 'package:image/image.dart' as img;

import 'package:ipixel_controller/render/blend.dart';

/// Default panel canvas dimensions.
const int defaultWidth = 64;
const int defaultHeight = 16;

/// Glyph order for the general-purpose text sprite sheet.
const String textGlyphOrder =
    '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:!?.,+-/\$% ';

/// Glyph order for clock sprite sheets (digits + colon).
const String clockGlyphOrder = '0123456789:';

/// Parses a `#RGB` / `#RRGGBB` (with or without `#`) hex string into an opaque
/// RGBA image colour, or returns `null` if the string is not a valid hex
/// colour.
///
/// Unlike PIL's `ImageColor.getrgb`, this only accepts hex forms — the only
/// shape the app ever produces — and reports malformed input to the caller
/// instead of guessing.
img.ColorRgba8? tryParseHexColor(String hex) {
  var h = hex.trim();
  if (h.startsWith('#')) {
    h = h.substring(1);
  }
  if (h.length == 3) {
    // Expand shorthand (abc -> aabbcc).
    h = h.split('').map((c) => '$c$c').join();
  }
  if (h.length != 6) {
    return null;
  }
  final value = int.tryParse(h, radix: 16);
  if (value == null) {
    return null;
  }
  final r = (value >> 16) & 0xFF;
  final g = (value >> 8) & 0xFF;
  final b = value & 0xFF;
  return img.ColorRgba8(r, g, b, 255);
}

/// Parses a hex colour, throwing [ArgumentError] on malformed input.
///
/// Fail-fast variant for callers that treat an invalid colour as a programmer
/// error (e.g. canvas construction). Render methods that follow the
/// `(result, error)` convention use [tryParseHexColor] instead so they can
/// surface the failure as an error string. PIL raises `ValueError` on the same
/// malformed input, so this is closer to the reference than a silent fallback.
img.ColorRgba8 parseHexColor(String hex) {
  final parsed = tryParseHexColor(hex);
  if (parsed == null) {
    throw ArgumentError.value(hex, 'hex', 'Invalid hex colour');
  }
  return parsed;
}

/// A sprite font loaded from a sprite sheet.
///
/// The sheet is sliced horizontally into `cols` fixed-width tiles and mapped to
/// characters by [order]. Mirrors `SpriteFont` in the Python reference.
class SpriteFont {
  SpriteFont({
    required this.name,
    required this.path,
    required this.order,
    required int cols,
  }) : cols = cols < 1 ? 1 : cols;

  final String name;
  final String path;
  final String order;
  final int cols;

  final Map<String, img.Image> _glyphs = {};
  int _tileWidth = 0;
  int _tileHeight = 0;
  bool _loaded = false;
  String? _error;

  /// Error from the last load attempt, or `null` if loading succeeded.
  String? get error => _error;

  int get tileWidth {
    if (!_loaded) {
      load();
    }
    return _tileWidth;
  }

  int get tileHeight {
    if (!_loaded) {
      load();
    }
    return _tileHeight;
  }

  /// Loads and slices the sheet from [path] on the local filesystem.
  ///
  /// Idempotent: subsequent calls return the cached result.
  bool load() {
    if (_loaded) {
      return _error == null;
    }
    final file = File(path);
    if (!file.existsSync()) {
      _error = 'Sprite sheet not found';
      _loaded = true;
      return false;
    }
    late final Uint8List bytes;
    try {
      bytes = file.readAsBytesSync();
    } on Exception catch (e) {
      _error = 'Sprite load failed: $e';
      _loaded = true;
      return false;
    }
    return loadFromBytes(bytes);
  }

  /// Loads and slices the sheet from raw PNG bytes (isolate-friendly path).
  bool loadFromBytes(Uint8List bytes) {
    if (_loaded) {
      return _error == null;
    }
    final trimmedOrder = order.trim();
    if (trimmedOrder.isEmpty) {
      _error = 'Glyph order is empty';
      _loaded = true;
      return false;
    }
    final decoded = img.decodeImage(bytes);
    if (decoded == null) {
      _error = 'Sprite load failed: could not decode image';
      _loaded = true;
      return false;
    }
    // Match PIL's convert("RGBA") so alpha compositing is well defined.
    final sheet = decoded.convert(numChannels: 4);
    _sliceGlyphs(sheet, trimmedOrder);
    if (_glyphs.isEmpty) {
      _error = 'No glyphs found in sprite sheet';
      _loaded = true;
      return false;
    }
    _loaded = true;
    return true;
  }

  void _sliceGlyphs(img.Image sheet, String order) {
    final chars = order.split('');
    final rows = (chars.length / cols).ceil().clamp(1, chars.length);
    _tileWidth = (sheet.width ~/ cols).clamp(1, sheet.width);
    _tileHeight = (sheet.height ~/ rows).clamp(1, sheet.height);

    for (var idx = 0; idx < chars.length; idx++) {
      final ch = chars[idx];
      final row = idx ~/ cols;
      final col = idx % cols;
      final left = col * _tileWidth;
      final upper = row * _tileHeight;
      if (left + _tileWidth <= sheet.width &&
          upper + _tileHeight <= sheet.height) {
        _glyphs[ch] = img.copyCrop(
          sheet,
          x: left,
          y: upper,
          width: _tileWidth,
          height: _tileHeight,
        );
      }
    }
  }

  /// Returns the glyph for [char], falling back to its uppercase form.
  img.Image? glyph(String char) {
    if (!_loaded) {
      load();
    }
    return _glyphs[char] ?? _glyphs[char.toUpperCase()];
  }
}

/// Registry of sprite fonts plus text-rendering helpers.
///
/// Mirrors `SpriteFontService` in the Python reference.
class SpriteFontService {
  final Map<String, SpriteFont> _fonts = {};

  void registerFont(SpriteFont font) {
    _fonts[font.name] = font;
  }

  SpriteFont? getFont(String name) => _fonts[name];

  List<String> get fontNames => _fonts.keys.toList();

  /// Renders [text] as a full-width RGBA strip (one tile wide per character).
  ///
  /// Returns `(image, null)` on success or `(null, error)` on failure. Used for
  /// the scrolling path where the entire text width is needed.
  (img.Image?, String?) renderTextLine(
    String text,
    String fontName, {
    String bgColor = '#000000',
  }) {
    final font = _fonts[fontName];
    if (font == null) {
      return (null, "Font '$fontName' not found");
    }
    if (!font.load()) {
      return (null, font.error);
    }

    final bg = tryParseHexColor(bgColor);
    if (bg == null) {
      return (null, "Invalid background colour '$bgColor'");
    }

    final chars = text.split('');
    final totalW = font.tileWidth * chars.length;
    if (totalW == 0) {
      return (null, 'No characters to render');
    }

    final base = img.Image(
      width: totalW < 1 ? 1 : totalW,
      height: font.tileHeight,
      numChannels: 4,
    );
    img.fill(base, color: bg);

    var x = 0;
    for (final ch in chars) {
      final glyph = font.glyph(ch);
      if (glyph == null) {
        x += font.tileWidth;
        continue;
      }
      _paste(base, glyph, x, 0);
      x += font.tileWidth;
    }
    return (base, null);
  }

  /// Renders [text] to a fixed [width]x[height] RGB canvas (default 64x16),
  /// centred/cropped to match the Python `render_text_fixed` logic.
  (img.Image?, String?) renderTextFixed(
    String text,
    String fontName, {
    String bgColor = '#000000',
    int width = defaultWidth,
    int height = defaultHeight,
  }) {
    final (line, error) = renderTextLine(text, fontName, bgColor: bgColor);
    if (error != null || line == null) {
      return (null, error);
    }

    if (line.width == width && line.height == height) {
      return (_toRgb(line), null);
    }

    final bg = parseHexColor(bgColor);

    // Height matches, wider than target: centre-crop, keep glyphs full size.
    // Python: left = (line.width - width) // 2.
    if (line.height == height && line.width > width) {
      final left = floorDiv(line.width - width, 2);
      final cropped = img.copyCrop(
        line,
        x: left,
        y: 0,
        width: width,
        height: height,
      );
      return (_toRgb(cropped), null);
    }

    // Smaller than target in both dimensions: centre without scaling.
    // Python offsets use // (floor division).
    if (line.height <= height && line.width <= width) {
      final canvas = img.Image(width: width, height: height, numChannels: 4);
      img.fill(canvas, color: bg);
      final offsetX = floorDiv(width - line.width, 2);
      final offsetY = floorDiv(height - line.height, 2);
      _paste(canvas, line, offsetX, offsetY);
      return (_toRgb(canvas), null);
    }

    // Otherwise scale to fit (nearest neighbour), then centre.
    // Python: scale = min(w/lw, h/lh); new = max(1, int(dim * scale)).
    // int() truncates toward zero, which Dart's toInt() also does; for these
    // positive values that equals floor.
    final scale = (width / line.width) < (height / line.height)
        ? width / line.width
        : height / line.height;
    final newW = _atLeastOne((line.width * scale).toInt());
    final newH = _atLeastOne((line.height * scale).toInt());
    final resized = img.copyResize(
      line,
      width: newW,
      height: newH,
      interpolation: img.Interpolation.nearest,
    );
    final canvas = img.Image(width: width, height: height, numChannels: 4);
    img.fill(canvas, color: bg);
    final offsetX = floorDiv(width - newW, 2);
    final offsetY = floorDiv(height - newH, 2);
    _paste(canvas, resized, offsetX, offsetY);
    return (_toRgb(canvas), null);
  }

  /// Alpha-composites [src] onto [dst] at ([dx],[dy]) using [src]'s own alpha
  /// channel as the mask — the exact behaviour of PIL's
  /// `base.paste(glyph, (x, y), glyph)`.
  void _paste(img.Image dst, img.Image src, int dx, int dy) {
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
        final dp = dst.getPixel(x, y);
        final inv = 255 - m;
        final r = mulDiv255(dp.r.toInt(), inv) + mulDiv255(sp.r.toInt(), m);
        final g = mulDiv255(dp.g.toInt(), inv) + mulDiv255(sp.g.toInt(), m);
        final b = mulDiv255(dp.b.toInt(), inv) + mulDiv255(sp.b.toInt(), m);
        final a = mulDiv255(dp.a.toInt(), inv) + mulDiv255(m, m);
        dst.setPixelRgba(x, y, r, g, b, a);
      }
    }
  }

  /// Mirrors Python's `max(1, value)` used when clamping scaled dimensions.
  int _atLeastOne(int value) => value < 1 ? 1 : value;

  /// Drops the alpha channel (equivalent to PIL's `convert("RGB")`).
  img.Image _toRgb(img.Image src) {
    final out = img.Image(width: src.width, height: src.height, numChannels: 3);
    for (var y = 0; y < src.height; y++) {
      for (var x = 0; x < src.width; x++) {
        final p = src.getPixel(x, y);
        out.setPixelRgb(x, y, p.r, p.g, p.b);
      }
    }
    return out;
  }
}

/// Converts a UI speed value (1..100) to a scroll interval in milliseconds.
///
/// Higher speed means a shorter interval. Ported verbatim from the Python
/// `speed_to_interval_ms`: speed 1 -> 218 ms, speed 100 -> 20 ms.
int speedToIntervalMs(int speed) {
  final clamped = speed < 1 ? 1 : (speed > 100 ? 100 : speed);
  final interval = 220 - clamped * 2;
  return interval < 20 ? 20 : interval;
}
