import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:ipixel_controller/config/config_store.dart';
import 'package:ipixel_controller/config/default_sprite_fonts.dart';
import 'package:ipixel_controller/config/models.dart';

void main() {
  late Directory tempDir;
  late ConfigStore store;

  setUp(() async {
    tempDir = await Directory.systemTemp.createTemp('ipixel_cfg_test_');
    store = ConfigStore(tempDir);
  });

  tearDown(() async {
    if (await tempDir.exists()) {
      await tempDir.delete(recursive: true);
    }
  });

  group('settings round-trip', () {
    test('saves and loads a settings map unchanged', () async {
      final settings = <String, dynamic>{
        'last_device': 'AA:BB:CC:DD:EE:FF',
        'auto_connect': true,
        'text_static_delay_seconds': 2,
      };

      await store.saveSettings(settings);
      final loaded = await store.loadSettings();

      expect(loaded, equals(settings));
    });

    test('missing settings file loads as an empty map', () async {
      expect(await store.loadSettings(), isEmpty);
    });
  });

  group('presets round-trip', () {
    test('saves and loads typed presets preserving the full payload', () async {
      final presets = <Preset>[
        Preset.fromJson(const {
          'name': 'Busy',
          'type': 'text',
          'text': 'BUSY',
          'text_color': '#ff0000',
          'bg_color': '#ffffff',
        }),
        Preset.fromJson(const {
          'name': 'Heart',
          'type': 'image',
          'image_path': 'Gallery/heart.gif',
        }),
      ];

      await store.savePresets(presets);
      final loaded = await store.loadPresets();

      expect(loaded, hasLength(2));
      expect(loaded[0].type, 'text');
      expect(loaded[0].name, 'Busy');
      expect(loaded[0].raw['text_color'], '#ff0000');
      expect(loaded[1].type, 'image');
      expect(loaded[1].raw['image_path'], 'Gallery/heart.gif');
    });

    test('missing presets file loads as an empty list', () async {
      expect(await store.loadPresets(), isEmpty);
    });

    test('a wrong-typed entry does not crash the loader', () async {
      await store.presetsFile.parent.create(recursive: true);
      await store.presetsFile.writeAsString(
        '[{"type": 5, "name": 9}, {"type": "text", "name": "Good"}]',
      );

      // Lenient loader: coerces rather than throwing.
      final presets = await store.loadPresets();
      expect(presets, hasLength(2));
      expect(presets[0].hasType, isFalse);
      expect(presets[1].type, 'text');
      expect(presets[1].name, 'Good');
    });
  });

  group('secrets round-trip', () {
    test('saves and loads a secrets map unchanged', () async {
      final secrets = <String, dynamic>{
        'youtube_api_key': 'yt',
        'weather_api_key': 'wx',
        'ig_user_id': '123',
        'ig_access_token': 'tok',
      };

      await store.saveSecrets(secrets);

      expect(await store.loadSecrets(), equals(secrets));
    });
  });

  group('atomic write', () {
    test('written file exists, parses, and leaves no temp file', () async {
      await store.saveSettings({'a': 1});

      expect(await store.settingsFile.exists(), isTrue);
      final tmp = File('${store.settingsFile.path}.tmp');
      expect(await tmp.exists(), isFalse);

      final parsed = jsonDecode(await store.settingsFile.readAsString());
      expect(parsed, equals({'a': 1}));
    });

    test('overwriting keeps the file readable', () async {
      await store.saveSettings({'v': 1});
      await store.saveSettings({'v': 2});

      final parsed = jsonDecode(await store.settingsFile.readAsString()) as Map;
      expect(parsed['v'], 2);
    });
  });

  group('concurrent merge serialization', () {
    Future<int> tmpFileCount() async {
      final entries = await tempDir
          .list()
          .where((e) => e.path.endsWith('.tmp'))
          .toList();
      return entries.length;
    }

    test('N concurrent read-modify-write updates lose none', () async {
      const n = 25;

      // Each update increments a per-key counter from the CURRENT value, so any
      // interleaving of the read and write halves would drop increments.
      final futures = List.generate(
        n,
        (_) => store.updateSettings((settings) {
          final current = (settings['counter'] as num?)?.toInt() ?? 0;
          settings['counter'] = current + 1;
          return settings;
        }),
      );
      await Future.wait(futures);

      final settings = await store.loadSettings();
      expect(settings['counter'], n);
      expect(await tmpFileCount(), 0, reason: 'no temp files should remain');
    });

    test('two concurrent single-key secret merges both survive', () async {
      await Future.wait([
        store.updateSecrets((secrets) {
          secrets['youtube_api_key'] = 'yt';
          return secrets;
        }),
        store.updateSecrets((secrets) {
          secrets['weather_api_key'] = 'wx';
          return secrets;
        }),
      ]);

      final secrets = await store.loadSecrets();
      expect(secrets['youtube_api_key'], 'yt');
      expect(secrets['weather_api_key'], 'wx');
      expect(await tmpFileCount(), 0);
    });

    test(
      'concurrent saveSpriteFonts + ensureDefaults leave no temp files',
      () async {
        await Future.wait([
          store.ensureDefaultSpriteFonts(),
          store.saveSpriteFonts(const [
            SpriteFontEntry(
              name: 'Custom',
              path: '/x.png',
              order: '01',
              cols: 2,
            ),
          ]),
          store.saveSettings({'k': 'v'}),
        ]);

        expect(await tmpFileCount(), 0);
        expect(await store.loadSettings(), isA<Map<String, dynamic>>());
      },
    );
  });

  group('malformed / error handling', () {
    test(
      'malformed settings JSON throws a clear ConfigParseException',
      () async {
        await store.settingsFile.parent.create(recursive: true);
        await store.settingsFile.writeAsString('{ not valid json');

        expect(
          store.loadSettings,
          throwsA(
            isA<ConfigParseException>().having(
              (e) => e.message,
              'message',
              contains('invalid JSON'),
            ),
          ),
        );
      },
    );

    test('presets file that is a JSON object (not a list) throws', () async {
      await store.presetsFile.parent.create(recursive: true);
      await store.presetsFile.writeAsString('{"not": "a list"}');

      expect(store.loadPresets, throwsA(isA<ConfigParseException>()));
    });

    test('empty file is treated as absent (returns default)', () async {
      await store.settingsFile.parent.create(recursive: true);
      await store.settingsFile.writeAsString('   ');

      expect(await store.loadSettings(), isEmpty);
    });
  });

  group('ensureDefaultSpriteFonts', () {
    test('seeds all bundled fonts on first launch', () async {
      final changed = await store.ensureDefaultSpriteFonts();

      expect(changed, isTrue);
      final fonts = await store.loadSpriteFonts();
      expect(fonts, hasLength(defaultSpriteFonts.length));
      expect(
        fonts.map((f) => f.name),
        containsAll(<String>['Text Default', 'Clock Default']),
      );
      // Bundled paths use the Flutter asset dir, not the legacy Gallery path.
      expect(
        fonts.every((f) => f.path.startsWith(bundledSpriteAssetDir)),
        isTrue,
      );
    });

    test('is idempotent and preserves existing custom fonts', () async {
      await store.saveSpriteFonts(<SpriteFontEntry>[
        const SpriteFontEntry(
          name: 'My Font',
          path: '/abs/my.png',
          order: '0123',
          cols: 4,
        ),
      ]);

      final firstChanged = await store.ensureDefaultSpriteFonts();
      final secondChanged = await store.ensureDefaultSpriteFonts();

      expect(firstChanged, isTrue);
      expect(secondChanged, isFalse);

      final fonts = await store.loadSpriteFonts();
      expect(fonts, hasLength(defaultSpriteFonts.length + 1));
      expect(fonts.map((f) => f.name), contains('My Font'));
    });
  });
}
