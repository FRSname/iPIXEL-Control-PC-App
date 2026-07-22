import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:path_provider/path_provider.dart';

import 'default_sprite_fonts.dart';
import 'models.dart';

/// Thrown when an existing config file cannot be parsed as the expected shape.
///
/// A *missing* file is not an error (callers get the supplied default); only
/// corrupt/unexpected content raises this so the UI can surface a clear message
/// instead of a raw [FormatException] or type error.
class ConfigParseException implements Exception {
  const ConfigParseException(this.path, this.message, [this.cause]);

  /// Absolute path of the offending file.
  final String path;

  /// Human-readable explanation.
  final String message;

  /// The underlying error, if any.
  final Object? cause;

  @override
  String toString() =>
      'ConfigParseException: failed to read "$path": $message'
      '${cause == null ? '' : ' ($cause)'}';
}

/// Persists settings, presets and secrets as JSON under an injectable base
/// directory.
///
/// ## Injectable directory
///
/// The store never reaches for a platform-specific directory on its own. The
/// constructor takes an explicit [baseDir]:
///
/// * Production code calls [ConfigStore.forApplicationSupport], which resolves
///   `getApplicationSupportDirectory()` via `path_provider` and forwards it to
///   the plain constructor.
/// * Tests construct `ConfigStore(tempDir)` directly, so they exercise the real
///   file I/O without ever touching a `MethodChannel`.
///
/// ## Atomic writes
///
/// Every save writes to a uniquely-named sibling `*.tmp` file (flushed to disk)
/// and then renames it over the target. `rename` is atomic on POSIX and
/// Windows, so a reader never observes a half-written file even if the process
/// is killed mid-write. The temp name carries a per-instance counter so two
/// in-flight writes never share a temp path.
///
/// ## Write serialization
///
/// All mutations on a single instance are serialized through an internal
/// Future-chain lock ([_serialized]). This covers read-modify-write merges
/// ([saveSpriteFonts], [ensureDefaultSpriteFonts], [updateSettings]) — not just
/// the file write — so concurrent updates cannot interleave their read and
/// write halves and lose data. A failing write does not poison the lock.
class ConfigStore {
  ConfigStore(this.baseDir);

  /// Resolves the OS application-support directory and returns a store rooted
  /// there. Only this factory touches platform channels.
  static Future<ConfigStore> forApplicationSupport() async {
    final dir = await getApplicationSupportDirectory();
    return ConfigStore(dir);
  }

  /// Root directory holding the three JSON files (and copied user sprites).
  final Directory baseDir;

  static const String settingsFileName = 'settings.json';
  static const String presetsFileName = 'presets.json';
  static const String secretsFileName = 'secrets.json';

  /// Key under `settings.json` holding the sprite-font library list.
  static const String spriteFontsKey = 'sprite_fonts';

  /// Key under `settings.json` holding the last connected device address.
  static const String lastDeviceKey = 'last_device';

  /// Serializes all mutations on this instance. Each queued action runs only
  /// after the previous one settles.
  Future<void> _writeLock = Future<void>.value();

  /// Monotonic counter making each temp file name unique per instance.
  int _tmpCounter = 0;

  File get settingsFile => _fileFor(settingsFileName);
  File get presetsFile => _fileFor(presetsFileName);
  File get secretsFile => _fileFor(secretsFileName);

  // ---- Settings -----------------------------------------------------------

  /// Loads the raw settings map. Returns an empty map when the file is absent.
  Future<Map<String, dynamic>> loadSettings() => _readJsonMap(settingsFile);

  /// Overwrites the whole settings map (serialized).
  Future<void> saveSettings(Map<String, dynamic> settings) =>
      _serialized(() => _writeJsonAtomic(settingsFile, settings));

  /// Atomically read-modify-writes settings under the instance write lock.
  ///
  /// [mutate] receives the current settings (an empty map on first launch),
  /// returns the map to persist, and runs with no other mutation interleaving
  /// its read and write. Returns the persisted map.
  Future<Map<String, dynamic>> updateSettings(
    Map<String, dynamic> Function(Map<String, dynamic> current) mutate,
  ) {
    return _serialized(() async {
      final current = await loadSettings();
      final next = mutate(current);
      await _writeJsonAtomic(settingsFile, next);
      return next;
    });
  }

  /// Loads the sprite-font library from settings.
  Future<List<SpriteFontEntry>> loadSpriteFonts() async {
    final settings = await loadSettings();
    return _decodeSpriteFonts(settings[spriteFontsKey], settingsFile.path);
  }

  /// Replaces the sprite-font library, preserving other settings keys.
  Future<void> saveSpriteFonts(List<SpriteFontEntry> fonts) async {
    await updateSettings((settings) {
      settings[spriteFontsKey] = fonts
          .map((f) => f.toJson())
          .toList(growable: false);
      return settings;
    });
  }

  // ---- Presets ------------------------------------------------------------

  /// Loads presets. Returns an empty list when the file is absent.
  ///
  /// Best-effort by design: the whole file being a non-list throws
  /// [ConfigParseException], but individual non-object entries are silently
  /// dropped and each object is parsed leniently (see [Preset.fromJson]) so a
  /// single bad element never fails the load. Strict per-entry validation with
  /// skip+report lives in the legacy importer, not here.
  Future<List<Preset>> loadPresets() async {
    final decoded = await _readJson(presetsFile, fallback: const <dynamic>[]);
    if (decoded is! List) {
      throw ConfigParseException(
        presetsFile.path,
        'expected a JSON list of presets, got ${decoded.runtimeType}',
      );
    }
    return decoded
        .whereType<Map<String, dynamic>>()
        .map(Preset.fromJson)
        .toList(growable: false);
  }

  Future<void> savePresets(List<Preset> presets) => _serialized(
    () => _writeJsonAtomic(
      presetsFile,
      presets.map((p) => p.toJson()).toList(growable: false),
    ),
  );

  // ---- Secrets ------------------------------------------------------------

  /// Loads secrets. Returns an empty map when the file is absent.
  Future<Map<String, dynamic>> loadSecrets() => _readJsonMap(secretsFile);

  Future<void> saveSecrets(Map<String, dynamic> secrets) =>
      _serialized(() => _writeJsonAtomic(secretsFile, secrets));

  /// Atomically read-modify-writes secrets under the instance write lock.
  ///
  /// Mirrors [updateSettings]: [mutate] receives the current secrets, returns
  /// the map to persist, and runs with no other mutation interleaving its read
  /// and write halves. Returns the persisted map.
  Future<Map<String, dynamic>> updateSecrets(
    Map<String, dynamic> Function(Map<String, dynamic> current) mutate,
  ) {
    return _serialized(() async {
      final current = await loadSecrets();
      final next = mutate(current);
      await _writeJsonAtomic(secretsFile, next);
      return next;
    });
  }

  // ---- First-launch seeding ----------------------------------------------

  /// Registers the bundled sprite fonts on first launch, mirroring the legacy
  /// `_ensure_default_sprite_fonts`: only names not already present are added,
  /// and the file is rewritten only if something changed.
  ///
  /// Returns `true` when new fonts were seeded.
  Future<bool> ensureDefaultSpriteFonts() {
    return _serialized(() async {
      final settings = await loadSettings();
      final existing = _decodeSpriteFonts(
        settings[spriteFontsKey],
        settingsFile.path,
      );
      final existingNames = existing.map((f) => f.name).toSet();

      final merged = <SpriteFontEntry>[...existing];
      var added = false;
      for (final font in defaultSpriteFonts) {
        if (!existingNames.contains(font.name)) {
          merged.add(font);
          added = true;
        }
      }

      if (added) {
        settings[spriteFontsKey] = merged
            .map((f) => f.toJson())
            .toList(growable: false);
        await _writeJsonAtomic(settingsFile, settings);
      }
      return added;
    });
  }

  // ---- Helpers ------------------------------------------------------------

  File _fileFor(String name) =>
      File('${baseDir.path}${Platform.pathSeparator}$name');

  /// Decodes the sprite-font list from a settings value.
  ///
  /// Best-effort by design (see [loadPresets]): a non-list value throws
  /// [ConfigParseException], but individual non-object entries are dropped and
  /// each object is parsed leniently via [SpriteFontEntry.fromJson].
  List<SpriteFontEntry> _decodeSpriteFonts(Object? value, String sourcePath) {
    if (value == null) return const <SpriteFontEntry>[];
    if (value is! List) {
      throw ConfigParseException(
        sourcePath,
        'expected "$spriteFontsKey" to be a list, got ${value.runtimeType}',
      );
    }
    return value
        .whereType<Map<String, dynamic>>()
        .map(SpriteFontEntry.fromJson)
        .toList(growable: false);
  }

  /// Queues [action] behind any in-flight mutation. A failure in one action is
  /// surfaced to its own caller and does not break the chain for later ones.
  Future<T> _serialized<T>(Future<T> Function() action) {
    final completer = Completer<T>();
    _writeLock = _writeLock.then((_) async {
      try {
        completer.complete(await action());
      } on Object catch (error, stack) {
        completer.completeError(error, stack);
      }
    });
    return completer.future;
  }

  Future<Map<String, dynamic>> _readJsonMap(File file) async {
    final decoded = await _readJson(file, fallback: const <String, dynamic>{});
    if (decoded is! Map<String, dynamic>) {
      throw ConfigParseException(
        file.path,
        'expected a JSON object, got ${decoded.runtimeType}',
      );
    }
    // Return a mutable copy so callers can amend and re-save.
    return Map<String, dynamic>.from(decoded);
  }

  Future<Object?> _readJson(File file, {required Object? fallback}) async {
    if (!await file.exists()) return fallback;
    final String contents;
    try {
      contents = await file.readAsString();
    } on IOException catch (e) {
      throw ConfigParseException(file.path, 'could not be read', e);
    }
    if (contents.trim().isEmpty) return fallback;
    try {
      return jsonDecode(contents);
    } on FormatException catch (e) {
      throw ConfigParseException(file.path, 'contains invalid JSON', e);
    }
  }

  Future<void> _writeJsonAtomic(File file, Object? data) async {
    await baseDir.create(recursive: true);
    final tmp = File('${file.path}.${_tmpCounter++}.tmp');
    const encoder = JsonEncoder.withIndent('  ');
    await tmp.writeAsString(encoder.convert(data), flush: true);
    await tmp.rename(file.path);
  }
}
