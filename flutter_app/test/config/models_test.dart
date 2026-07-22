import 'package:flutter_test/flutter_test.dart';
import 'package:ipixel_controller/config/models.dart';

void main() {
  group('Preset', () {
    test('extracts type and name, keeps full payload, and round-trips', () {
      const json = <String, dynamic>{
        'name': 'Clock - Classic',
        'type': 'clock',
        'style': 3,
        'nested': {'a': 1},
      };

      final preset = Preset.fromJson(json);

      expect(preset.type, 'clock');
      expect(preset.name, 'Clock - Classic');
      expect(preset.hasType, isTrue);
      expect(preset.raw['style'], 3);
      expect(preset.toJson(), equals(json));
    });

    test('trims whitespace and treats a missing type as empty', () {
      expect(Preset.fromJson(const {'type': '  text  '}).type, 'text');
      final noType = Preset.fromJson(const {'name': 'x'});
      expect(noType.type, '');
      expect(noType.hasType, isFalse);
    });

    test('raw payload is unmodifiable', () {
      final preset = Preset.fromJson(const {'type': 't'});
      expect(() => preset.raw['x'] = 1, throwsUnsupportedError);
    });

    test('does not throw when type/name are present with the wrong type', () {
      final preset = Preset.fromJson(const {'type': 5, 'name': 42});
      // Non-string discriminator coerces to empty (invalid) rather than crashing.
      expect(preset.type, '');
      expect(preset.name, '');
      expect(preset.hasType, isFalse);
      // Raw payload still preserves the original values.
      expect(preset.raw['type'], 5);
    });
  });

  group('SpriteFontEntry', () {
    test('round-trips through JSON', () {
      const json = <String, dynamic>{
        'name': 'Text Thin',
        'path': 'Gallery/Sprites/Text-thin-Sprite.png',
        'order': '0123456789',
        'cols': 73,
      };
      final entry = SpriteFontEntry.fromJson(json);
      expect(entry.name, 'Text Thin');
      expect(entry.cols, 73);
      expect(entry.toJson(), equals(json));
    });

    test('defaults cols to 1 and copyWith swaps only the given field', () {
      final entry = SpriteFontEntry.fromJson(const {'name': 'X'});
      expect(entry.cols, 1);
      final moved = entry.copyWith(path: 'assets/sprites/X.png');
      expect(moved.path, 'assets/sprites/X.png');
      expect(moved.name, 'X');
    });

    test('does not throw and coerces a string cols value', () {
      final entry = SpriteFontEntry.fromJson(const {'name': 'X', 'cols': '73'});
      expect(entry.cols, 73);
    });

    test('falls back to cols=1 when cols is an uncoercible type', () {
      final entry = SpriteFontEntry.fromJson(const {'cols': true});
      expect(entry.cols, 1);
    });
  });

  group('Playlist', () {
    test('round-trips legacy preset_name/duration shape', () {
      const json = <String, dynamic>{
        'name': 'Rotation',
        'items': [
          {'preset_name': 'Busy', 'duration': 5},
          {'preset_name': 'Heart', 'duration': 2.5},
        ],
      };
      final playlist = Playlist.fromJson(json);
      expect(playlist.name, 'Rotation');
      expect(playlist.items, hasLength(2));
      expect(playlist.items[0].presetName, 'Busy');
      expect(playlist.items[1].duration, 2.5);
      expect(playlist.toJson(), equals(json));
    });

    test('tolerates a missing items list', () {
      final playlist = Playlist.fromJson(const {'name': 'Empty'});
      expect(playlist.items, isEmpty);
    });
  });
}
