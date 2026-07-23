/// Renders the current 64x16 preview frame upscaled with nearest-neighbour
/// filtering, so individual LEDs stay crisp instead of being blurred.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:ipixel_controller/render/panel_image.dart';
import 'package:ipixel_controller/ui/preview/preview_provider.dart';

/// A framed, aspect-locked preview of the panel's current frame.
///
/// Watches [panelPreviewProvider] and upscales the frame with
/// [FilterQuality.none] (nearest-neighbour). The panel is 64x16, so the widget
/// keeps a 4:1 aspect ratio regardless of the space it is given.
class PanelPreview extends ConsumerWidget {
  const PanelPreview({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final frame = ref.watch(panelPreviewProvider);
    return Semantics(
      label: 'Panel preview',
      image: true,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: Colors.black,
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: const Color(0xFF232A33)),
        ),
        child: Padding(
          padding: const EdgeInsets.all(4),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(3),
            child: AspectRatio(
              aspectRatio: panelWidth / panelHeight,
              child: Image.memory(
                frame,
                fit: BoxFit.fill,
                filterQuality: FilterQuality.none,
                gaplessPlayback: true,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
