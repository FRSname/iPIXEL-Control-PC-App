import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:ipixel_controller/config/config_store.dart';
import 'package:ipixel_controller/config/import_legacy.dart';

const _fixturesDir = 'test/fixtures';

void main() {
  late Directory tempDir;
  late ConfigStore store;

  setUp(() async {
    tempDir = await Directory.systemTemp.createTemp('ipixel_import_test_');
    store = ConfigStore(tempDir);
  });

  tearDown(() async {
    if (await tempDir.exists()) {
      await tempDir.delete(recursive: true);
    }
  });

  test('imports the real committed presets fixture as typed presets', () async {
    final report = await importLegacy(
      store,
      presetsPath: '$_fixturesDir/legacy_presets.json',
    );

    expect(report.presetsImported, 13);
    final presets = await store.loadPresets();
    expect(presets, hasLength(13));
    // Every entry has a non-empty discriminator.
    expect(presets.every((p) => p.type.isNotEmpty), isTrue);
    // The set of types seen in the committed file.
    expect(
      presets.map((p) => p.type).toSet(),
      containsAll(<String>[
        'image',
        'text',
        'clock',
        'youtube',
        'weather',
        'stock',
        'instagram',
      ]),
    );
  });

  test('imports synthetic settings with sprite-font remapping', () async {
    final report = await importLegacy(
      store,
      settingsPath: '$_fixturesDir/legacy_settings.json',
    );

    // last_device preserved.
    expect(report.lastDevice, 'AA:BB:CC:DD:EE:FF');
    final settings = await store.loadSettings();
    expect(settings[ConfigStore.lastDeviceKey], 'AA:BB:CC:DD:EE:FF');

    final fonts = await store.loadSpriteFonts();
    final byName = {for (final f in fonts) f.name: f};

    // Bundled Gallery/Sprites path remapped to the Flutter asset path.
    expect(byName['Text Thin']!.path, 'assets/sprites/Text-thin-Sprite.png');
    expect(report.remappedBundled, contains('Text Thin'));

    // The user font points at a non-existent source, so it is skipped+reported.
    expect(byName.containsKey('My Custom Font'), isFalse);
    expect(report.skippedMissing, isNotEmpty);
  });

  test('copies a user sprite sheet that exists into app support', () async {
    // Arrange: a real user sprite file on disk and a settings file pointing to
    // it.
    final userSprite = File('${tempDir.path}/user-sprite.png');
    await userSprite.writeAsBytes(<int>[1, 2, 3, 4]);
    final settingsFile = File('${tempDir.path}/legacy_settings.json');
    await settingsFile.writeAsString('''
{
  "last_device": "11:22:33:44:55:66",
  "sprite_fonts": [
    {"name": "User Font", "path": "${userSprite.path}", "order": "01", "cols": 2}
  ]
}
''');

    // Act.
    final report = await importLegacy(store, settingsPath: settingsFile.path);

    // Assert: copied into <base>/sprites/ and the entry rewritten to point at it.
    expect(report.copiedUserFonts, contains('User Font'));
    final fonts = await store.loadSpriteFonts();
    final entry = fonts.firstWhere((f) => f.name == 'User Font');
    expect(entry.path, contains(importedSpritesDirName));
    expect(await File(entry.path).exists(), isTrue);
  });

  test(
    'skips and reports a wrong-typed preset entry, keeps good ones',
    () async {
      final presetsFile = File('${tempDir.path}/legacy_presets.json');
      await presetsFile.writeAsString(
        '[{"type": 5, "name": "bad"}, {"type": "text", "name": "Good"}]',
      );

      final report = await importLegacy(store, presetsPath: presetsFile.path);

      expect(report.presetsImported, 1);
      expect(
        report.warnings.any((w) => w.contains('malformed preset')),
        isTrue,
      );
      final presets = await store.loadPresets();
      expect(presets, hasLength(1));
      expect(presets.single.name, 'Good');
    },
  );

  test(
    'skips and reports a wrong-typed sprite-font entry, keeps good ones',
    () async {
      final settingsFile = File('${tempDir.path}/legacy_settings.json');
      await settingsFile.writeAsString('''
{
  "sprite_fonts": [
    {"name": "Bad", "path": "Gallery/Sprites/x.png", "order": "01", "cols": "73"},
    {"name": "Good", "path": "Gallery/Sprites/TextSprite.png", "order": "01", "cols": 73}
  ]
}
''');

      final report = await importLegacy(store, settingsPath: settingsFile.path);

      expect(report.spriteFontsImported, 1);
      expect(
        report.warnings.any((w) => w.contains('malformed sprite-font')),
        isTrue,
      );
      final fonts = await store.loadSpriteFonts();
      expect(fonts.map((f) => f.name), ['Good']);
    },
  );

  test('same-basename user fonts from different dirs do not collide', () async {
    final dirA = Directory('${tempDir.path}/a')..createSync();
    final dirB = Directory('${tempDir.path}/b')..createSync();
    final fileA = File('${dirA.path}/sprite.png');
    final fileB = File('${dirB.path}/sprite.png');
    await fileA.writeAsBytes(<int>[1]);
    await fileB.writeAsBytes(<int>[2]);

    final settingsFile = File('${tempDir.path}/legacy_settings.json');
    await settingsFile.writeAsString('''
{
  "sprite_fonts": [
    {"name": "A", "path": "${fileA.path}", "order": "01", "cols": 2},
    {"name": "B", "path": "${fileB.path}", "order": "01", "cols": 2}
  ]
}
''');

    final report = await importLegacy(store, settingsPath: settingsFile.path);

    expect(report.copiedUserFonts, containsAll(<String>['A', 'B']));
    final fonts = await store.loadSpriteFonts();
    final pathA = fonts.firstWhere((f) => f.name == 'A').path;
    final pathB = fonts.firstWhere((f) => f.name == 'B').path;
    expect(pathA, isNot(pathB));
    expect(await File(pathA).readAsBytes(), <int>[1]);
    expect(await File(pathB).readAsBytes(), <int>[2]);
  });

  test('imports synthetic secrets fixture', () async {
    final report = await importLegacy(
      store,
      secretsPath: '$_fixturesDir/legacy_secrets.json',
    );

    expect(report.secretsImported, 4);
    final secrets = await store.loadSecrets();
    expect(secrets['youtube_api_key'], 'REDACTED');
    expect(secrets['ig_access_token'], 'REDACTED');
  });

  test('malformed settings file is reported, not thrown', () async {
    final report = await importLegacy(
      store,
      settingsPath: '$_fixturesDir/legacy_settings_malformed.json',
    );

    expect(report.warnings, isNotEmpty);
    expect(report.warnings.first, contains('invalid JSON'));
    // Store remains usable / untouched.
    expect(await store.loadSettings(), isEmpty);
  });

  test('missing files are reported, not thrown', () async {
    final report = await importLegacy(
      store,
      settingsPath: '$_fixturesDir/does_not_exist.json',
      presetsPath: '$_fixturesDir/also_missing.json',
      secretsPath: '$_fixturesDir/nope.json',
    );

    expect(report.warnings.where((w) => w.contains('not found')), hasLength(3));
    expect(report.presetsImported, 0);
  });
}
