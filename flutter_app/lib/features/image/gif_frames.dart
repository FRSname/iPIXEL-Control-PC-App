/// Decodes an animated GIF into a list of panel-ready frames.
///
/// Each source frame is fitted onto the 64x16 panel canvas (letterbox or crop)
/// and encoded to PNG, keeping its authored display duration so the playback
/// loop can honour the GIF's own timing. Pure Dart on top of the `image`
/// package — no `dart:ui`, so it runs in `flutter test` VM tests and isolates.
///
/// ## Panel-safe frame interval
///
/// Full-frame BLE writes cannot sustain intervals below ~320 ms (see
/// CLAUDE.md — rapid `send_image` calls race the panel's command queue and trip
/// the disconnect guard). GIF frames therefore never play faster than
/// [kGifMinFrameIntervalMs]; a GIF authored with 40 ms frames plays at the
/// 320 ms floor. The raw authored duration is preserved on each [PanelGifFrame]
/// and the floor is applied at playback time via [gifFrameIntervalMs], so this
/// module stays a pure decode step.
library;

import 'dart:typed_data';

import 'package:image/image.dart' as img;

import 'package:ipixel_controller/features/image/image_fit.dart';
import 'package:ipixel_controller/render/panel_image.dart';

/// Absolute floor for the per-frame GIF interval (ms).
///
/// The panel cannot sustain full-frame writes faster than this, so no GIF —
/// however fast it was authored — plays below it.
const int kGifMinFrameIntervalMs = 320;

/// A single decoded GIF frame: the panel-ready PNG and its authored duration.
class PanelGifFrame {
  const PanelGifFrame({required this.png, required this.durationMs});

  /// The fitted 64x16 frame, PNG-encoded and ready to send.
  final Uint8List png;

  /// The frame's authored display duration in milliseconds, before the
  /// panel-safe floor ([gifFrameIntervalMs]) is applied.
  final int durationMs;
}

/// Clamps a GIF frame's authored [rawMs] duration up to the panel-safe floor.
///
/// Returns [rawMs] unchanged when it already meets or exceeds
/// [kGifMinFrameIntervalMs]; otherwise returns the floor. Always
/// >= [kGifMinFrameIntervalMs].
int gifFrameIntervalMs(int rawMs) =>
    rawMs < kGifMinFrameIntervalMs ? kGifMinFrameIntervalMs : rawMs;

/// Decodes [bytes] as a GIF and fits every frame onto the panel.
///
/// Each returned [PanelGifFrame] carries the fitted PNG and the source frame's
/// authored duration (unclamped). A single-frame GIF yields a one-element list;
/// callers decide whether that is a static image or a (degenerate) loop.
///
/// Throws [ImageDecodeException] when [bytes] is not a decodable GIF.
List<PanelGifFrame> extractGifFrames(
  Uint8List bytes, {
  PanelFit fit = PanelFit.letterbox,
  String bgColor = '#000000',
}) {
  // A trust boundary: bytes come from an arbitrary user-picked file, and the
  // `image` package's GIF decoder can throw a raw `RangeError` on a truncated
  // or garbled file rather than returning `null`. Normalise both into a domain
  // exception so the page shows a clean error instead of crashing.
  final img.Image? decoded;
  try {
    decoded = img.decodeGif(bytes);
  } on Object {
    throw const ImageDecodeException('Could not read that GIF file.');
  }
  if (decoded == null) {
    throw const ImageDecodeException('Could not read that GIF file.');
  }
  // A decoded animation exposes its frames via `frames`; a degenerate GIF with
  // no frame list still holds a single image in itself.
  final frames = decoded.frames.isEmpty ? <img.Image>[decoded] : decoded.frames;
  return <PanelGifFrame>[
    for (final frame in frames)
      PanelGifFrame(
        png: encodePanelPng(fitImage(frame, fit: fit, bgColor: bgColor)),
        durationMs: frame.frameDuration,
      ),
  ];
}
