/// Typed, immutable models for the on-disk configuration layer.
///
/// These mirror the shapes produced by the legacy Python app so that its
/// `ipixel_settings.json`, `ipixel_presets.json` and playlist files can be
/// imported without loss. Every model round-trips through [fromJson]/[toJson].
///
/// The `fromJson` factories are deliberately defensive: a key that is present
/// with an unexpected type is coerced or falls back to a sensible default
/// rather than throwing. This keeps the never-throw import contract intact even
/// when a legacy file has been hand-edited into a wrong shape. Strict per-entry
/// validation (skip + report) lives in `import_legacy.dart`.
library;

/// Reads [value] as a [String], falling back to [fallback] for any other type.
String _asString(Object? value, [String fallback = '']) =>
    value is String ? value : fallback;

/// Reads [value] as an [int], coercing numeric strings and other [num]s.
int _asInt(Object? value, [int fallback = 1]) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  if (value is String) return int.tryParse(value.trim()) ?? fallback;
  return fallback;
}

/// Reads [value] as a [num], coercing numeric strings.
num _asNum(Object? value, [num fallback = 0]) {
  if (value is num) return value;
  if (value is String) return num.tryParse(value.trim()) ?? fallback;
  return fallback;
}

/// A saved panel preset.
///
/// The legacy app stores presets as a heterogeneous list of dicts, each keyed
/// by a `type` discriminator (`image`, `text`, `clock`, `weather`, `stock`,
/// `youtube`, `instagram`). The feature-specific payload varies per type, so we
/// keep the full [raw] map intact and only surface the two fields every preset
/// shares — [type] and [name].
class Preset {
  const Preset({required this.type, required this.name, required this.raw});

  /// The feature discriminator matching a feature id (e.g. `text`, `image`).
  final String type;

  /// Human-facing preset name.
  final String name;

  /// The preset payload as stored on disk.
  ///
  /// Top-level unmodifiable: reassigning or adding a key throws, but nested
  /// collections are shared by reference and remain mutable. Callers must not
  /// mutate nested values in place — treat the whole map as read-only.
  final Map<String, dynamic> raw;

  factory Preset.fromJson(Map<String, dynamic> json) {
    return Preset(
      type: _asString(json['type']).trim(),
      name: _asString(json['name']),
      raw: Map<String, dynamic>.unmodifiable(json),
    );
  }

  /// Serializes back to the exact stored shape (a copy of [raw]).
  Map<String, dynamic> toJson() => Map<String, dynamic>.from(raw);

  /// Whether this preset carries a usable discriminator.
  bool get hasType => type.isNotEmpty;
}

/// A single sprite-font sheet definition.
///
/// `order` is the glyph order string; `cols` is the number of glyph columns in
/// the sheet. `path` is either a bundled Flutter asset (`assets/sprites/...`) or
/// an absolute path to a user-supplied sheet copied into app support.
class SpriteFontEntry {
  const SpriteFontEntry({
    required this.name,
    required this.path,
    required this.order,
    required this.cols,
  });

  final String name;
  final String path;
  final String order;
  final int cols;

  factory SpriteFontEntry.fromJson(Map<String, dynamic> json) {
    return SpriteFontEntry(
      name: _asString(json['name']),
      path: _asString(json['path']),
      order: _asString(json['order']),
      cols: _asInt(json['cols'], 1),
    );
  }

  /// Best-effort decode of a stored sprite-font list value. A non-list value or
  /// a non-object entry is dropped; each object is parsed leniently.
  static List<SpriteFontEntry> listFrom(Object? value) {
    if (value is! List) return const <SpriteFontEntry>[];
    return value
        .whereType<Map<String, dynamic>>()
        .map(SpriteFontEntry.fromJson)
        .toList(growable: false);
  }

  Map<String, dynamic> toJson() => <String, dynamic>{
    'name': name,
    'path': path,
    'order': order,
    'cols': cols,
  };

  SpriteFontEntry copyWith({
    String? name,
    String? path,
    String? order,
    int? cols,
  }) {
    return SpriteFontEntry(
      name: name ?? this.name,
      path: path ?? this.path,
      order: order ?? this.order,
      cols: cols ?? this.cols,
    );
  }
}

/// One item in a playlist: a reference to a preset by name plus a dwell time.
///
/// Mirrors the legacy shape `{"preset_name": ..., "duration": ...}`. Duration is
/// kept as [num] because legacy files use both int and float seconds.
///
/// NOTE: Playlist persistence and import are deferred to Step 10 — these models
/// exist now so the shape is fixed, but no loader/importer references them yet.
class PlaylistItem {
  const PlaylistItem({required this.presetName, required this.duration});

  final String presetName;
  final num duration;

  factory PlaylistItem.fromJson(Map<String, dynamic> json) {
    return PlaylistItem(
      presetName: _asString(json['preset_name']),
      duration: _asNum(json['duration'], 0),
    );
  }

  Map<String, dynamic> toJson() => <String, dynamic>{
    'preset_name': presetName,
    'duration': duration,
  };
}

/// A named, ordered list of preset references.
///
/// Mirrors `playlists/*.json`: `{"name": ..., "items": [...]}`.
///
/// NOTE: Playlist persistence and import are deferred to Step 10 (intentional);
/// this model is defined now only to lock in the on-disk shape.
class Playlist {
  const Playlist({required this.name, required this.items});

  final String name;
  final List<PlaylistItem> items;

  factory Playlist.fromJson(Map<String, dynamic> json) {
    final rawItems = (json['items'] as List<dynamic>?) ?? const <dynamic>[];
    return Playlist(
      name: _asString(json['name']),
      items: List<PlaylistItem>.unmodifiable(
        rawItems.whereType<Map<String, dynamic>>().map(PlaylistItem.fromJson),
      ),
    );
  }

  Map<String, dynamic> toJson() => <String, dynamic>{
    'name': name,
    'items': items.map((item) => item.toJson()).toList(),
  };
}
