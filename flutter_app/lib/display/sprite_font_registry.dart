/// Builds a [SpriteFontService] from the persisted sprite-font library.
///
/// The render core's [SpriteFont] loads its sheet from a filesystem [File]; that
/// works for user sprites copied into app-support, but the bundled sheets live
/// in the Flutter asset bundle (`assets/sprites/...`), which is not a real file.
/// This layer bridges the two: bundled entries are decoded from asset bytes via
/// [rootBundle], user entries fall back to the render core's lazy [File] load.
///
/// This is the seam feature pages (Text, and later Clock) read to populate their
/// font dropdown and to render — it is deliberately outside the pure `render/`
/// library because it depends on Flutter's asset bundle.
library;

import 'dart:typed_data';

import 'package:flutter/services.dart' show rootBundle;
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:ipixel_controller/config/default_sprite_fonts.dart';
import 'package:ipixel_controller/config/models.dart';
import 'package:ipixel_controller/config/providers.dart';
import 'package:ipixel_controller/render/sprite_font.dart';

/// Loads the raw bytes for a bundled asset key. Injectable for tests.
typedef AssetLoader = Future<Uint8List> Function(String assetKey);

Future<Uint8List> _rootBundleLoader(String assetKey) async {
  final data = await rootBundle.load(assetKey);
  return data.buffer.asUint8List();
}

/// Registers every [entry] into a fresh [SpriteFontService].
///
/// Bundled entries (path under [bundledSpriteAssetDir]) are eagerly decoded from
/// asset bytes so they render without touching the filesystem. User entries are
/// registered unloaded and decode lazily from their [File] path on first render.
/// A single sheet that fails to load never fails the whole registry — the font
/// is still registered and surfaces its own error only if selected.
Future<SpriteFontService> buildSpriteFontService(
  List<SpriteFontEntry> entries, {
  AssetLoader assetLoader = _rootBundleLoader,
}) async {
  final service = SpriteFontService();
  for (final entry in entries) {
    final font = SpriteFont(
      name: entry.name,
      path: entry.path,
      order: entry.order,
      cols: entry.cols,
    );
    if (entry.path.startsWith(bundledSpriteAssetDir)) {
      try {
        final bytes = await assetLoader(entry.path);
        font.loadFromBytes(bytes);
      } on Object {
        // Missing/corrupt bundled sheet: keep the font registered but unloaded
        // so the dropdown still lists it and only its own render reports failure.
      }
    }
    service.registerFont(font);
  }
  return service;
}

/// The app-wide sprite-font service, seeded with the bundled defaults on first
/// launch and populated from the persisted library.
///
/// Overridden in widget tests with a pre-built service so they avoid the config
/// store and the asset bundle.
final spriteFontRegistryProvider = FutureProvider<SpriteFontService>((
  ref,
) async {
  final store = await ref.watch(configStoreProvider.future);
  await store.ensureDefaultSpriteFonts();
  final entries = await store.loadSpriteFonts();
  return buildSpriteFontService(entries);
});
