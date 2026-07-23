/// Shared layout for a feature surface: a titled, scrollable content column
/// with the panel preview pinned at the top.
///
/// Feature steps (S7-S9) replace their page body while keeping this frame, so
/// every surface previews before sending — the UX upgrade called for in S6.
library;

import 'package:flutter/material.dart';

import 'package:ipixel_controller/ui/widgets/panel_preview.dart';

class FeatureScaffold extends StatelessWidget {
  const FeatureScaffold({
    required this.title,
    required this.children,
    this.showPreview = true,
    super.key,
  });

  final String title;
  final List<Widget> children;

  /// Whether to pin the [PanelPreview] above the content.
  final bool showPreview;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(title, style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 16),
            if (showPreview) ...[
              ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 512),
                child: const PanelPreview(),
              ),
              const SizedBox(height: 24),
            ],
            ...children,
          ],
        ),
      ),
    );
  }
}

/// Simple "not built yet" card used by placeholder feature pages.
class ComingSoonCard extends StatelessWidget {
  const ComingSoonCard({required this.feature, super.key});

  final String feature;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Row(
          children: [
            const Icon(Icons.construction, size: 28),
            const SizedBox(width: 16),
            Expanded(
              child: Text(
                '$feature is coming in a later build.',
                style: Theme.of(context).textTheme.bodyLarge,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
