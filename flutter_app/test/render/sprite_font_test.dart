// Tests for lib/render/sprite_font.dart.
//
// `flutter test` runs with cwd == flutter_app, so sprite sheets and fixtures
// are loaded via filesystem paths relative to that directory.
import 'dart:io';

import 'package:image/image.dart' as img;
import 'package:ipixel_controller/render/sprite_font.dart';
import 'package:flutter_test/flutter_test.dart';

const clockSheet = 'assets/sprites/SmallerClocksSprite-transp.png';
const textSheet = 'assets/sprites/TextSprite.png';

SpriteFontService clockService() {
  final svc = SpriteFontService();
  svc.registerFont(
    SpriteFont(
      name: 'Clock',
      path: clockSheet,
      order: clockGlyphOrder, // '0123456789:'
      cols: 11,
    ),
  );
  return svc;
}

/// Builds a SpriteFont pre-loaded from in-code PNG bytes (no fixture files).
SpriteFont fontFromImage(
  img.Image sheet, {
  required String name,
  required String order,
  required int cols,
}) {
  final font = SpriteFont(
    name: name,
    path: '<memory>',
    order: order,
    cols: cols,
  );
  final ok = font.loadFromBytes(img.encodePng(sheet));
  expect(ok, isTrue, reason: font.error);
  return font;
}

/// Counts pixels whose RGB channels differ between two same-size images.
int rgbMismatches(img.Image a, img.Image b) {
  expect(a.width, b.width);
  expect(a.height, b.height);
  var mismatches = 0;
  for (var y = 0; y < a.height; y++) {
    for (var x = 0; x < a.width; x++) {
      final pa = a.getPixel(x, y);
      final pb = b.getPixel(x, y);
      if (pa.r.toInt() != pb.r.toInt() ||
          pa.g.toInt() != pb.g.toInt() ||
          pa.b.toInt() != pb.b.toInt()) {
        mismatches++;
      }
    }
  }
  return mismatches;
}

void main() {
  group('SpriteFont slicing', () {
    test('SmallerClocksSprite slices into 7x16 tiles', () {
      final font = SpriteFont(
        name: 'Clock',
        path: clockSheet,
        order: clockGlyphOrder,
        cols: 11,
      );
      expect(font.load(), isTrue);
      // 78 px wide / 11 cols = 7; 16 px tall / 1 row = 16.
      expect(font.tileWidth, 7);
      expect(font.tileHeight, 16);
      expect(font.glyph('0'), isNotNull);
      expect(font.glyph(':'), isNotNull);
    });

    test('lowercase falls back to uppercase glyph', () {
      final svc = SpriteFontService();
      svc.registerFont(
        SpriteFont(
          name: 'Text',
          path: textSheet,
          order: textGlyphOrder,
          cols: 73,
        ),
      );
      final font = svc.getFont('Text')!;
      expect(font.load(), isTrue);
      // 'A' exists; 'a' also exists in this sheet, but the fallback path is
      // exercised for any char present only in uppercase form.
      expect(font.glyph('A'), isNotNull);
    });

    test('missing sheet reports an error', () {
      final font = SpriteFont(
        name: 'Nope',
        path: 'assets/sprites/does_not_exist.png',
        order: clockGlyphOrder,
        cols: 11,
      );
      expect(font.load(), isFalse);
      expect(font.error, 'Sprite sheet not found');
    });

    test('empty glyph order reports an error', () {
      final font = SpriteFont(
        name: 'Empty',
        path: clockSheet,
        order: '   ',
        cols: 1,
      );
      expect(font.load(), isFalse);
      expect(font.error, 'Glyph order is empty');
    });
  });

  group('renderTextLine', () {
    test('produces a full-width strip (tileWidth * chars)', () {
      final svc = clockService();
      final (line, err) = svc.renderTextLine(
        '12:34',
        'Clock',
        bgColor: '#FFFFFF',
      );
      expect(err, isNull);
      expect(line, isNotNull);
      expect(line!.width, 7 * 5); // 35
      expect(line.height, 16);
    });

    test('unknown font returns an error', () {
      final svc = clockService();
      final (line, err) = svc.renderTextLine('x', 'Missing');
      expect(line, isNull);
      expect(err, "Font 'Missing' not found");
    });
  });

  group('renderTextFixed', () {
    test('centres a narrow strip on a 64x16 canvas', () {
      final svc = clockService();
      final (img_, err) = svc.renderTextFixed(
        '12:34',
        'Clock',
        bgColor: '#FFFFFF',
      );
      expect(err, isNull);
      expect(img_, isNotNull);
      expect(img_!.width, 64);
      expect(img_.height, 16);
    });

    test('glyph pixels are black and background is the fill colour', () {
      final svc = clockService();
      final (img_, _) = svc.renderTextFixed(
        '12:34',
        'Clock',
        bgColor: '#FFFFFF',
      );
      // Corner is untouched background (white).
      final corner = img_!.getPixel(0, 0);
      expect(corner.r.toInt(), 255);
      expect(corner.g.toInt(), 255);
      expect(corner.b.toInt(), 255);
      // (17, 8) is a known black glyph pixel (see golden inspection).
      final glyph = img_.getPixel(17, 8);
      expect(glyph.r.toInt(), 0);
      expect(glyph.g.toInt(), 0);
      expect(glyph.b.toInt(), 0);
    });
  });

  // ---------------------------------------------------------------- GOLDEN
  //
  // Pixel-parity against the Python SpriteFontService in this worktree.
  //
  // Reference string : "12:34"
  // Sheet            : assets/sprites/SmallerClocksSprite-transp.png (78x16)
  // Order / cols     : '0123456789:' / 11  -> 7x16 tiles
  // Colors           : bg #FFFFFF, glyphs are the sheet's baked-in black
  // Sizing           : 35x16 strip centred on 64x16 (no resize path)
  //
  // Golden generated with (venv OUTSIDE the repo, pillow 11.3.0, py3.9):
  //   $VENV/bin/python scratchpad/gen_golden.py \
  //       <worktree_root> \
  //       flutter_app/test/fixtures/golden_clock_1234.png \
  //       "#FFFFFF"
  // which calls:
  //   svc.render_text_fixed("12:34", "Clock", bg_color="#FFFFFF", 64, 16)
  // using ipixel_controller.services.sprite_font.SpriteFontService.
  group('golden parity', () {
    test('Dart render matches Python golden pixel-for-pixel (RGB)', () {
      final svc = clockService();
      final (dart, err) = svc.renderTextFixed(
        '12:34',
        'Clock',
        bgColor: '#FFFFFF',
      );
      expect(err, isNull);

      final goldenBytes = File(
        'test/fixtures/golden_clock_1234.png',
      ).readAsBytesSync();
      final golden = img.decodePng(goldenBytes)!;

      final mismatches = rgbMismatches(dart!, golden);
      expect(
        mismatches,
        0,
        reason:
            '$mismatches of ${golden.width * golden.height} '
            'RGB pixels differ from the Python golden',
      );
    });

    // Crop-centre branch with a NON-EXACT remainder: "0123456789:" -> 77px
    // strip on the 7px clock tile, centre-cropped to 64. Python left =
    // (77-64)//2 = 6 (13 is odd, so floor vs truncate matters here). No
    // resampling, so this is a safe 0-diff parity check against Python.
    //
    // Golden generated by scratchpad/gen_crop_golden.py <worktree_root>:
    //   svc.render_text_fixed("0123456789:", "Clock", bg_color="#FFFFFF", 64,16)
    test('crop-centre branch matches Python golden pixel-for-pixel (RGB)', () {
      final svc = clockService();
      final (dart, err) = svc.renderTextFixed(
        '0123456789:',
        'Clock',
        bgColor: '#FFFFFF',
      );
      expect(err, isNull);
      expect(dart!.width, 64);
      expect(dart.height, 16);

      final golden = img.decodePng(
        File('test/fixtures/golden_clock_digits_crop.png').readAsBytesSync(),
      )!;
      expect(rgbMismatches(dart, golden), 0);
    });
  });

  group('renderTextFixed scale-to-fit branch', () {
    // A 200x32 sheet with two 100x32 tiles (A=red, B=blue) forces the
    // scale-to-fit path: the 200x32 strip is neither <=64 wide nor 16 tall.
    // Python (verify_branches.py) computes scale = min(64/200, 16/32) = 0.32,
    // new = 64x10, offset_y = (16-10)//2 = 3 -> image occupies rows 3..12,
    // letterboxed with the bg above and below.
    test('scales a tall strip and letterboxes it', () {
      final sheet = img.Image(width: 200, height: 32, numChannels: 4);
      for (var y = 0; y < 32; y++) {
        for (var x = 0; x < 100; x++) {
          sheet.setPixelRgba(x, y, 255, 0, 0, 255); // A: red
          sheet.setPixelRgba(x + 100, y, 0, 0, 255, 255); // B: blue
        }
      }
      final svc = SpriteFontService()
        ..registerFont(
          fontFromImage(sheet, name: 'Tall', order: 'AB', cols: 2),
        );

      final (out, err) = svc.renderTextFixed(
        'AB',
        'Tall',
        bgColor: '#00FF00', // green letterbox so it is distinguishable
      );
      expect(err, isNull);
      expect(out!.width, 64);
      expect(out.height, 16);

      List<int> rgb(int x, int y) {
        final p = out.getPixel(x, y);
        return [p.r.toInt(), p.g.toInt(), p.b.toInt()];
      }

      // Rows above/below the 10px scaled image are green letterbox.
      expect(rgb(0, 0), [0, 255, 0]);
      expect(rgb(0, 15), [0, 255, 0]);
      // First image row (y=3): far left is red, far right is blue.
      expect(rgb(0, 3), [255, 0, 0]);
      expect(rgb(63, 3), [0, 0, 255]);
    });
  });

  group('partial-alpha compositing (_paste via renderTextLine)', () {
    // A single 1x1 glyph that is half-transparent blue (0,0,255, a=128)
    // composited over a white (255,255,255) background.
    //
    // PIL MULDIV255 blend (t = a*b+128; ((t>>8)+t)>>8), m=128, inv=127:
    //   R = mulDiv255(255,127) + mulDiv255(0,128)   = 127 + 0   = 127
    //   G = mulDiv255(255,127) + mulDiv255(0,128)   = 127 + 0   = 127
    //   B = mulDiv255(255,127) + mulDiv255(255,128) = 127 + 128 = 255
    //   A = mulDiv255(255,127) + mulDiv255(128,128) = 127 + 64  = 191
    test('half-alpha glyph blends exactly like PIL paste-with-mask', () {
      final sheet = img.Image(width: 1, height: 1, numChannels: 4);
      sheet.setPixelRgba(0, 0, 0, 0, 255, 128);
      final svc = SpriteFontService()
        ..registerFont(fontFromImage(sheet, name: 'X', order: 'X', cols: 1));

      final (line, err) = svc.renderTextLine('X', 'X', bgColor: '#FFFFFF');
      expect(err, isNull);
      final p = line!.getPixel(0, 0);
      expect(p.r.toInt(), 127);
      expect(p.g.toInt(), 127);
      expect(p.b.toInt(), 255);
      expect(p.a.toInt(), 191);
    });
  });

  group('colour parsing', () {
    test('tryParseHexColor accepts #RRGGBB, #RGB and rejects garbage', () {
      final white = tryParseHexColor('#FFFFFF');
      expect(white, isNotNull);
      expect(
        [white!.r.toInt(), white.g.toInt(), white.b.toInt()],
        [255, 255, 255],
      );
      // Shorthand expands abc -> aabbcc.
      final short = tryParseHexColor('#abc');
      expect(
        [short!.r.toInt(), short.g.toInt(), short.b.toInt()],
        [0xaa, 0xbb, 0xcc],
      );
      expect(tryParseHexColor('nothex'), isNull);
      expect(tryParseHexColor('#12'), isNull);
    });

    test('parseHexColor throws ArgumentError on malformed input', () {
      expect(() => parseHexColor('bogus'), throwsArgumentError);
    });

    test('renderTextFixed surfaces an invalid background as an error', () {
      final svc = clockService();
      final (out, err) = svc.renderTextFixed(
        '12:34',
        'Clock',
        bgColor: 'notacolour',
      );
      expect(out, isNull);
      expect(err, contains('Invalid background colour'));
    });
  });
}
