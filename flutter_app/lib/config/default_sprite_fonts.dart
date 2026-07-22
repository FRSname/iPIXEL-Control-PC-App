import 'models.dart';

/// Directory (relative to the Flutter asset root) that holds bundled sprite
/// sheets. The canonical copies live in the repo-root `Gallery/Sprites/`; the
/// vendored copies under this path are declared in `pubspec.yaml`.
const String bundledSpriteAssetDir = 'assets/sprites/';

/// Glyph order shared by every full-alphabet text sprite sheet.
const String _textFontOrder =
    '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:!?.,+-/\$%';

/// The bundled sprite fonts seeded on first launch.
///
/// Mirrors `_ensure_default_sprite_fonts` in the legacy `ipixel_controller.py`,
/// but rewrites the legacy `Gallery/Sprites/<file>` paths to the bundled Flutter
/// asset path `assets/sprites/<file>`.
const List<SpriteFontEntry> defaultSpriteFonts = <SpriteFontEntry>[
  SpriteFontEntry(
    name: 'Text Default',
    path: '${bundledSpriteAssetDir}TextSprite.png',
    order: _textFontOrder,
    cols: 73,
  ),
  SpriteFontEntry(
    name: 'Text Long',
    path: '${bundledSpriteAssetDir}Text-Long-Sprite.png',
    order: _textFontOrder,
    cols: 73,
  ),
  SpriteFontEntry(
    name: 'Text Long White',
    path: '${bundledSpriteAssetDir}Text-Long-White-Sprite.png',
    order: _textFontOrder,
    cols: 73,
  ),
  SpriteFontEntry(
    name: 'Text Long Yellow',
    path: '${bundledSpriteAssetDir}Text-Long-Yellow-Sprite.png',
    order: _textFontOrder,
    cols: 73,
  ),
  SpriteFontEntry(
    name: 'Text Thin',
    path: '${bundledSpriteAssetDir}Text-thin-Sprite.png',
    order: _textFontOrder,
    cols: 73,
  ),
  SpriteFontEntry(
    name: 'Text Thin White',
    path: '${bundledSpriteAssetDir}Text-thin-White-Sprite.png',
    order: _textFontOrder,
    cols: 73,
  ),
  SpriteFontEntry(
    name: 'Text Thin Yellow',
    path: '${bundledSpriteAssetDir}Text-thin-Yellow-Sprite.png',
    order: _textFontOrder,
    cols: 73,
  ),
  SpriteFontEntry(
    name: 'Text White',
    path: '${bundledSpriteAssetDir}TextSpriteWhite.png',
    order: _textFontOrder,
    cols: 73,
  ),
  SpriteFontEntry(
    name: 'Text Yellow',
    path: '${bundledSpriteAssetDir}TextSpriteYellow.png',
    order: _textFontOrder,
    cols: 73,
  ),
  SpriteFontEntry(
    name: 'Clock Default',
    path: '${bundledSpriteAssetDir}SmallerClocksSprite-transp.png',
    order: '0123456789:',
    cols: 11,
  ),
];
