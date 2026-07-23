/// Holds the frame currently shown in the panel preview.
///
/// Feature pages publish the exact 64x16 frame they are about to send (or are
/// sending) by calling [PanelPreviewController.setFrame] with PNG bytes. The
/// [PanelPreview] widget renders whatever this provider holds, upscaled
/// nearest-neighbour. Until a feature publishes a frame the controller seeds a
/// static placeholder so the preview is never empty.
library;

import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image/image.dart' as img;

import 'package:ipixel_controller/render/panel_image.dart';

/// Current preview frame as PNG bytes, or the seeded placeholder.
class PanelPreviewController extends Notifier<Uint8List> {
  @override
  Uint8List build() => _placeholderFrame();

  /// Replaces the preview with [png]. Features call this before/while sending.
  void setFrame(Uint8List png) => state = png;

  /// Resets the preview back to the seeded placeholder.
  void clear() => state = _placeholderFrame();
}

final panelPreviewProvider =
    NotifierProvider<PanelPreviewController, Uint8List>(
      PanelPreviewController.new,
    );

/// A subtle diagonal gradient so the empty preview reads as "panel, no content"
/// rather than a broken/black image.
Uint8List _placeholderFrame() {
  final canvas = img.Image(
    width: panelWidth,
    height: panelHeight,
    numChannels: 3,
  );
  for (var y = 0; y < panelHeight; y++) {
    for (var x = 0; x < panelWidth; x++) {
      final r = (x / (panelWidth - 1) * 40).round();
      final g = (y / (panelHeight - 1) * 60 + 20).round();
      final b = (x / (panelWidth - 1) * 90 + 30).round();
      canvas.setPixelRgb(x, y, r, g, b);
    }
  }
  return encodePanelPng(canvas);
}
