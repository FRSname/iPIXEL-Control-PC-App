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

/// A raw, un-fitted GIF frame: the decoded source [image] and its authored
/// duration.
///
/// This is the cheap-to-produce, expensive-to-decode half of the pipeline. The
/// page decodes a picked GIF into these *once* and keeps them; toggling
/// Letterbox/Crop or the background colour then only re-runs the cheap fit step
/// ([fitGifFrames]) over the cached list rather than re-decoding every frame.
class DecodedGifFrame {
  const DecodedGifFrame({required this.image, required this.durationMs});

  /// The decoded source frame at its original resolution.
  final img.Image image;

  /// The frame's authored display duration in milliseconds.
  final int durationMs;
}

/// Clamps a GIF frame's authored [rawMs] duration up to the panel-safe floor.
///
/// Returns [rawMs] unchanged when it already meets or exceeds
/// [kGifMinFrameIntervalMs]; otherwise returns the floor. Always
/// >= [kGifMinFrameIntervalMs].
int gifFrameIntervalMs(int rawMs) =>
    rawMs < kGifMinFrameIntervalMs ? kGifMinFrameIntervalMs : rawMs;

/// Decodes [bytes] as a GIF into its raw source frames — the expensive step.
///
/// Runs the `image` package's GIF decoder exactly once and captures each
/// frame's authored duration. No fitting or encoding happens here, so the
/// result can be cached and re-fitted cheaply via [fitGifFrames] whenever the
/// fit mode or background colour changes.
///
/// A single-frame GIF yields a one-element list; callers decide whether that is
/// a static image or a (degenerate) loop.
///
/// Throws [ImageDecodeException] when [bytes] is not a decodable GIF.
List<DecodedGifFrame> decodeGifFrames(Uint8List bytes) {
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
  return <DecodedGifFrame>[
    for (final frame in frames)
      DecodedGifFrame(image: frame, durationMs: frame.frameDuration),
  ];
}

/// Fits already-decoded [frames] onto the panel — the cheap step.
///
/// Each returned [PanelGifFrame] carries the fitted PNG and the source frame's
/// authored duration (unclamped). Pure fit + encode over cached frames, so it
/// is safe to re-run on every fit/background change without re-decoding.
List<PanelGifFrame> fitGifFrames(
  List<DecodedGifFrame> frames, {
  PanelFit fit = PanelFit.letterbox,
  String bgColor = '#000000',
}) {
  return <PanelGifFrame>[
    for (final frame in frames)
      PanelGifFrame(
        png: encodePanelPng(fitImage(frame.image, fit: fit, bgColor: bgColor)),
        durationMs: frame.durationMs,
      ),
  ];
}

/// Decodes [bytes] as a GIF and fits every frame onto the panel in one pass.
///
/// A convenience composition of [decodeGifFrames] + [fitGifFrames] for callers
/// that do not need to cache the decode (e.g. the pure-module tests). The page
/// decodes once and re-fits via the two steps directly.
///
/// Throws [ImageDecodeException] when [bytes] is not a decodable GIF.
List<PanelGifFrame> extractGifFrames(
  Uint8List bytes, {
  PanelFit fit = PanelFit.letterbox,
  String bgColor = '#000000',
}) => fitGifFrames(decodeGifFrames(bytes), fit: fit, bgColor: bgColor);
