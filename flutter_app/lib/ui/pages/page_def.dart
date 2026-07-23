/// A single navigable feature surface.
///
/// The shell renders one navigation destination per [PageDef] and builds its
/// [builder] when selected. Feature steps (S7-S9) fill in their own page file
/// and expose a `PageDef` from it; the shared registry
/// (`page_registry.dart`) lists them once. Filling in a feature only edits that
/// feature's own file, never a shared registration file — which keeps the
/// parallel S8/S9 branches conflict-free.
library;

import 'package:flutter/widgets.dart';

/// Immutable description of a feature page and its navigation entry.
@immutable
class PageDef {
  const PageDef({
    required this.id,
    required this.label,
    required this.icon,
    required this.selectedIcon,
    required this.builder,
  });

  /// Stable identifier, also used as the preset `type` discriminator and as the
  /// key suffix for the page widget (`Key('page-<id>')`).
  final String id;

  /// Human-readable navigation label.
  final String label;

  /// Icon shown when the destination is not selected.
  final IconData icon;

  /// Icon shown when the destination is selected.
  final IconData selectedIcon;

  /// Builds the page widget. A closure (not const) so pages can be
  /// `ConsumerWidget`s that read providers directly.
  final Widget Function() builder;
}
