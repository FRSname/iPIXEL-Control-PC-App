import 'dart:convert';
import 'dart:io';

import 'config_store.dart';
import 'default_sprite_fonts.dart';
import 'models.dart';

/// Legacy path prefix used by the Python app for its bundled sprite sheets.
const String _legacyBundledPrefix = 'Gallery/Sprites/';

/// Sub-directory of the store's base dir where imported user sprites are copied.
const String importedSpritesDirName = 'sprites';

/// Summary of a legacy import run. Never raised as an error itself — individual
/// bad entries are recorded here rather than aborting the whole import.
class LegacyImportReport {
  LegacyImportReport({
    this.presetsImported = 0,
    this.spriteFontsImported = 0,
    this.lastDevice,
    this.secretsImported = 0,
    List<String>? remappedBundled,
    List<String>? copiedUserFonts,
    List<String>? skippedMissing,
    List<String>? warnings,
  }) : remappedBundled = remappedBundled ?? <String>[],
       copiedUserFonts = copiedUserFonts ?? <String>[],
       skippedMissing = skippedMissing ?? <String>[],
       warnings = warnings ?? <String>[];

  int presetsImported;
  int spriteFontsImported;
  String? lastDevice;
  int secretsImported;

  /// Names of fonts whose bundled `Gallery/Sprites/...` path was remapped to the
  /// Flutter asset path.
  final List<String> remappedBundled;

  /// Names of user fonts whose sheet was copied into app support.
  final List<String> copiedUserFonts;

  /// Human-readable notes about fonts skipped because their source was missing.
  final List<String> skippedMissing;

  /// Non-fatal problems encountered (e.g. a file that could not be parsed).
  final List<String> warnings;

  bool get hasWarnings => warnings.isNotEmpty || skippedMissing.isNotEmpty;
}

/// Reads the three legacy JSON files (any of which may be null / missing) and
/// merges their contents into [store].
///
/// * Presets from [presetsPath] replace the store's preset list.
/// * `last_device` and the remapped sprite-font library from [settingsPath] are
///   merged into settings (other existing settings keys are preserved).
/// * Secrets from [secretsPath] are merged into the store's secrets.
///
/// A malformed or unreadable file is recorded in the returned report's
/// [LegacyImportReport.warnings] and skipped; it never throws.
Future<LegacyImportReport> importLegacy(
  ConfigStore store, {
  String? settingsPath,
  String? presetsPath,
  String? secretsPath,
}) async {
  final report = LegacyImportReport();

  if (presetsPath != null) {
    await _importPresets(store, presetsPath, report);
  }
  if (settingsPath != null) {
    await _importSettings(store, settingsPath, report);
  }
  if (secretsPath != null) {
    await _importSecrets(store, secretsPath, report);
  }

  return report;
}

Future<void> _importPresets(
  ConfigStore store,
  String path,
  LegacyImportReport report,
) async {
  final decoded = await _readJsonFile(path, report);
  if (decoded == null) return;
  if (decoded is! List) {
    report.warnings.add('$path: expected a list of presets, skipped');
    return;
  }

  final presets = <Preset>[];
  for (final entry in decoded) {
    if (entry is! Map<String, dynamic>) {
      report.warnings.add('$path: skipped non-object preset entry');
      continue;
    }
    final issue = _presetIssue(entry);
    if (issue != null) {
      report.warnings.add('$path: skipped malformed preset ($issue)');
      continue;
    }
    presets.add(Preset.fromJson(entry));
  }

  await store.savePresets(presets);
  report.presetsImported = presets.length;
}

/// Returns a reason string if [json] has a wrong-typed shared field, else null.
/// Only the fields every preset shares are validated; feature-specific payload
/// is preserved verbatim.
String? _presetIssue(Map<String, dynamic> json) {
  final type = json['type'];
  if (type != null && type is! String) {
    return 'type is ${type.runtimeType}, expected String';
  }
  if (type == null || (type is String && type.trim().isEmpty)) {
    return 'missing type discriminator';
  }
  final name = json['name'];
  if (name != null && name is! String) {
    return 'name is ${name.runtimeType}, expected String';
  }
  return null;
}

Future<void> _importSettings(
  ConfigStore store,
  String path,
  LegacyImportReport report,
) async {
  final decoded = await _readJsonFile(path, report);
  if (decoded == null) return;
  if (decoded is! Map<String, dynamic>) {
    report.warnings.add('$path: expected a settings object, skipped');
    return;
  }

  final lastDevice = decoded[ConfigStore.lastDeviceKey];
  final String? validLastDevice =
      (lastDevice is String && lastDevice.isNotEmpty) ? lastDevice : null;

  // Path remapping / user-font copying happens up front so the atomic
  // read-modify-write below stays synchronous and short.
  final imported = <SpriteFontEntry>[];
  final rawFonts = decoded[ConfigStore.spriteFontsKey];
  if (rawFonts is List) {
    for (final raw in rawFonts) {
      if (raw is! Map<String, dynamic>) {
        report.warnings.add('$path: skipped non-object sprite-font entry');
        continue;
      }
      final issue = _spriteFontIssue(raw);
      if (issue != null) {
        report.warnings.add('$path: skipped malformed sprite-font ($issue)');
        continue;
      }
      final entry = SpriteFontEntry.fromJson(raw);
      final mapped = await _mapSpriteFontPath(store, entry, report);
      if (mapped != null) imported.add(mapped);
    }
  }

  // Merge atomically under the store's write lock so a concurrent settings
  // mutation cannot clobber last_device or the font library.
  await store.updateSettings((settings) {
    if (validLastDevice != null) {
      settings[ConfigStore.lastDeviceKey] = validLastDevice;
    }
    if (rawFonts is List) {
      final existing = SpriteFontEntry.listFrom(
        settings[ConfigStore.spriteFontsKey],
      );
      final byName = <String, SpriteFontEntry>{
        for (final f in existing) f.name: f,
      };
      for (final f in imported) {
        byName[f.name] = f;
      }
      settings[ConfigStore.spriteFontsKey] = byName.values
          .map((f) => f.toJson())
          .toList(growable: false);
    }
    return settings;
  });

  if (validLastDevice != null) report.lastDevice = validLastDevice;
  report.spriteFontsImported = imported.length;
}

/// Returns a reason string if [json] has a wrong-typed field, else null.
String? _spriteFontIssue(Map<String, dynamic> json) {
  for (final key in const ['name', 'path', 'order']) {
    final value = json[key];
    if (value != null && value is! String) {
      return '$key is ${value.runtimeType}, expected String';
    }
  }
  final cols = json['cols'];
  if (cols != null && cols is! num) {
    return 'cols is ${cols.runtimeType}, expected a number';
  }
  return null;
}

/// Applies the sprite-font path policy for one entry.
///
/// * `Gallery/Sprites/<file>` -> bundled asset `assets/sprites/<file>`.
/// * Any other (user) path -> the sheet is copied into app support and the
///   entry rewritten to point at the copy. A missing source is skipped and
///   reported; it never throws.
Future<SpriteFontEntry?> _mapSpriteFontPath(
  ConfigStore store,
  SpriteFontEntry entry,
  LegacyImportReport report,
) async {
  final normalized = entry.path.replaceAll('\\', '/');

  if (normalized.startsWith(_legacyBundledPrefix)) {
    final filename = normalized.substring(normalized.lastIndexOf('/') + 1);
    report.remappedBundled.add(entry.name);
    return entry.copyWith(path: '$bundledSpriteAssetDir$filename');
  }

  // User-supplied path: copy the source into app support if it exists.
  final source = File(entry.path);
  if (!await source.exists()) {
    report.skippedMissing.add('${entry.name} (missing: ${entry.path})');
    return null;
  }

  try {
    final destDir = Directory(
      '${store.baseDir.path}${Platform.pathSeparator}$importedSpritesDirName',
    );
    await destDir.create(recursive: true);
    final destPath =
        '${destDir.path}${Platform.pathSeparator}${_uniqueFileName(normalized)}';
    await source.copy(destPath);
    report.copiedUserFonts.add(entry.name);
    return entry.copyWith(path: destPath);
  } on IOException catch (e) {
    report.warnings.add('${entry.name}: copy failed ($e)');
    return null;
  }
}

/// Builds a collision-resistant destination file name for a user sprite sheet.
///
/// Two user fonts with the same basename but different source directories would
/// otherwise overwrite each other in the shared import dir, so the source path
/// is hashed and inserted before the extension: `sprite.<hash>.png`. The hash is
/// FNV-1a over UTF-8 bytes — stable across SDK versions (unlike
/// [String.hashCode], which is unspecified and would break persisted filenames
/// on an SDK upgrade).
String _uniqueFileName(String normalizedSourcePath) {
  final basename = normalizedSourcePath.substring(
    normalizedSourcePath.lastIndexOf('/') + 1,
  );
  final hash = _fnv1a32(normalizedSourcePath).toRadixString(16);
  final dot = basename.lastIndexOf('.');
  if (dot <= 0) return '$basename.$hash';
  return '${basename.substring(0, dot)}.$hash${basename.substring(dot)}';
}

/// 32-bit FNV-1a hash over the UTF-8 bytes of [input]. Deterministic and
/// SDK-version stable, so it is safe for persisted file names.
int _fnv1a32(String input) {
  var hash = 0x811c9dc5;
  for (final byte in utf8.encode(input)) {
    hash = (hash ^ byte) & 0xffffffff;
    hash = (hash * 0x01000193) & 0xffffffff;
  }
  return hash;
}

Future<void> _importSecrets(
  ConfigStore store,
  String path,
  LegacyImportReport report,
) async {
  final decoded = await _readJsonFile(path, report);
  if (decoded == null) return;
  if (decoded is! Map<String, dynamic>) {
    report.warnings.add('$path: expected a secrets object, skipped');
    return;
  }

  var count = 0;
  await store.updateSecrets((secrets) {
    decoded.forEach((key, value) {
      secrets[key] = value;
      count++;
    });
    return secrets;
  });
  report.secretsImported = count;
}

/// Reads and decodes a JSON file, recording (not throwing) any problem.
/// Returns null when the file is missing, empty, or malformed.
Future<Object?> _readJsonFile(String path, LegacyImportReport report) async {
  final file = File(path);
  if (!await file.exists()) {
    report.warnings.add('$path: file not found, skipped');
    return null;
  }
  try {
    final contents = await file.readAsString();
    if (contents.trim().isEmpty) {
      report.warnings.add('$path: file is empty, skipped');
      return null;
    }
    return jsonDecode(contents);
  } on FormatException catch (e) {
    report.warnings.add('$path: invalid JSON, skipped ($e)');
    return null;
  } on IOException catch (e) {
    report.warnings.add('$path: could not be read, skipped ($e)');
    return null;
  }
}
