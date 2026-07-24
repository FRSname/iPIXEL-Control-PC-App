import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';

import 'package:ipixel_controller/config/models.dart';
import 'package:ipixel_controller/display/sprite_font_registry.dart';

const String _textOrder =
    '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:!?.,+-/\$%';

void main() {
  test('bundled entries are decoded eagerly via the asset loader', () async {
    final assetBytes = File('assets/sprites/TextSprite.png').readAsBytesSync();
    final loaded = <String>[];

    final service = await buildSpriteFontService(
      const <SpriteFontEntry>[
        SpriteFontEntry(
          name: 'Text Default',
          path: 'assets/sprites/TextSprite.png',
          order: _textOrder,
          cols: 73,
        ),
      ],
      assetLoader: (key) async {
        loaded.add(key);
        return assetBytes;
      },
    );

    expect(loaded, <String>['assets/sprites/TextSprite.png']);
    expect(service.fontNames, <String>['Text Default']);
    final font = service.getFont('Text Default')!;
    expect(font.error, isNull);
    expect(font.glyph('A'), isNotNull);
    expect(font.tileWidth, 7);
    expect(font.tileHeight, 16);
  });

  test(
    'filesystem entries load lazily from their File path, not the loader',
    () async {
      var loaderCalls = 0;

      final service = await buildSpriteFontService(
        <SpriteFontEntry>[
          SpriteFontEntry(
            name: 'User Font',
            path: File('assets/sprites/TextSprite.png').absolute.path,
            order: _textOrder,
            cols: 73,
          ),
        ],
        assetLoader: (key) async {
          loaderCalls++;
          return Uint8List(0);
        },
      );

      expect(loaderCalls, 0, reason: 'non-asset paths never touch the loader');
      final font = service.getFont('User Font')!;
      // Lazy load triggered by first glyph lookup.
      expect(font.glyph('B'), isNotNull);
      expect(font.error, isNull);
    },
  );

  test(
    'a bundled sheet that fails to load stays registered but unloaded',
    () async {
      final service = await buildSpriteFontService(const <SpriteFontEntry>[
        SpriteFontEntry(
          name: 'Broken',
          path: 'assets/sprites/does-not-exist.png',
          order: _textOrder,
          cols: 73,
        ),
      ], assetLoader: (key) async => throw Exception('asset missing'));

      // Still listed so the dropdown shows it; render will report its own error.
      expect(service.fontNames, <String>['Broken']);
    },
  );

  test('registration order matches the entry order', () async {
    final assetBytes = File('assets/sprites/TextSprite.png').readAsBytesSync();
    final service = await buildSpriteFontService(const <SpriteFontEntry>[
      SpriteFontEntry(
        name: 'First',
        path: 'assets/sprites/TextSprite.png',
        order: _textOrder,
        cols: 73,
      ),
      SpriteFontEntry(
        name: 'Second',
        path: 'assets/sprites/TextSprite.png',
        order: _textOrder,
        cols: 73,
      ),
    ], assetLoader: (key) async => assetBytes);

    expect(service.fontNames, <String>['First', 'Second']);
  });
}
