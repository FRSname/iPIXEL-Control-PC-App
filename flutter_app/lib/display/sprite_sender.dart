/// Renders text with a sprite font and drives it onto the panel.
///
/// Dart port of `ipixel_controller/qt/sprite_sender.py`. It produces
/// [DisplayTask]s for the two text paths every text-based feature needs:
///
/// * **static** — one 64x16 frame, sent once.
/// * **scroll** — a wide text strip cropped into 64x16 windows advanced on a
///   periodic timer, each window sent through the panel.
///
/// ## No glyph recolouring
///
/// The sprite path composites each glyph with its baked-in sheet colour onto a
/// solid background fill; the only colour control is [bgColor]. (The legacy
/// `text_color` fed the non-sprite `send_text` firmware path, which this Dart
/// app does not use.) Callers pick glyph colour by choosing a coloured sheet
/// variant (e.g. "Text White", "Text Yellow").
///
/// ## Rate limiting and no overlapping sends
///
/// The scroll timer reschedules itself only after each frame's send *completes*,
/// so a slow write never lets frames pile up ahead of the BLE queue. The
/// per-frame interval never drops below [kScrollMinIntervalMs] — the documented
/// ~120 ms sprite-scroll floor — so even the fastest speed setting cannot push
/// writes below what the panel sustains. Because [scrollIntervalMs] is read
/// fresh on every reschedule, a live speed change (see [ScrollSpeedControl])
/// takes effect on the next frame without restarting the scroll.
library;

import 'dart:async';
import 'dart:developer';
import 'dart:typed_data';

import 'package:image/image.dart' as img;

import 'package:ipixel_controller/display/display_task.dart';
import 'package:ipixel_controller/render/blend.dart';
import 'package:ipixel_controller/render/panel_image.dart';
import 'package:ipixel_controller/render/sprite_font.dart';

/// Logging channel for display-task failures surfaced via `dart:developer`.
const String _logName = 'SpriteSender';

/// Sends a fully-encoded 64x16 panel PNG. Wired to `DeviceSession.sendImage`.
typedef ImageSink = Future<void> Function(Uint8List png);

/// Publishes a frame to the live preview. Wired to `PanelPreview.setFrame`.
typedef FrameCallback = void Function(Uint8List png);

/// Schedules [callback] after [duration]. Injectable so tests drive frames
/// manually instead of waiting on the wall clock. Defaults to [Timer.new].
typedef TimerFactory =
    Timer Function(Duration duration, void Function() callback);

/// Blank columns appended after the text so a wrap does not look abrupt
/// (matches the Python reference's 8-column pad).
const int kScrollPadColumns = 8;

/// Fastest per-frame scroll interval (ms), reached at the top of the speed
/// slider. The panel sustains ~120 ms sprite crops; faster than this risks
/// tripping the disconnect guard, so this value doubles as the absolute floor.
const int kScrollMinIntervalMs = 120;

/// Slowest per-frame scroll interval (ms), reached at the bottom of the speed
/// slider. Chosen so the slowest setting is a clearly readable crawl rather than
/// a barely-perceptible nudge.
const int kScrollMaxIntervalMs = 540;

/// Maps a UI speed (1..100) to a per-frame scroll interval in milliseconds.
///
/// Linear and monotonic across the panel-safe band
/// [[kScrollMinIntervalMs], [kScrollMaxIntervalMs]]: speed 1 → 540 ms (slow
/// crawl), speed 100 → 120 ms (the fast floor), speed 50 → ~332 ms. Every
/// slider step changes the visible scroll rate.
///
/// This intentionally replaces the legacy `220 - speed*2` mapping. That mapping
/// spanned 218 → 20 ms, so once the 120 ms panel floor was applied every speed
/// from 50 upward collapsed to exactly 120 ms — the entire upper half of the
/// slider produced one identical rate. The floor now lives at the *fast end* of
/// a spread that sits entirely above it, so no speed is clamped away. The result
/// is always ≥ [kScrollMinIntervalMs].
int scrollIntervalMs(int speed) {
  final clamped = speed < 1 ? 1 : (speed > 100 ? 100 : speed);
  const span = kScrollMaxIntervalMs - kScrollMinIntervalMs;
  // speed 1 → +span (slowest), speed 100 → +0 (fastest).
  final offset = (span * (100 - clamped) / 99).round();
  return kScrollMinIntervalMs + offset;
}

/// Advances a scroll [offset] by [step], wrapping at the ends of the strip.
///
/// Forward (step > 0) wraps back to 0 after passing [maxOffset]; reverse wraps
/// to [maxOffset] after passing 0. Mirrors the Python `_scroll_tick` wrap.
int advanceScrollOffset(int offset, int step, int maxOffset) {
  final next = offset + step;
  if (next > maxOffset) return 0;
  if (next < 0) return maxOffset;
  return next;
}

/// Raised when sprite rendering fails (unknown font, bad colour, empty text).
class SpriteRenderException implements Exception {
  const SpriteRenderException(this.message);
  final String message;
  @override
  String toString() => 'SpriteRenderException: $message';
}

/// Result of planning a scroll: either a single centred frame (the text fits)
/// or an animated strip to crop.
sealed class ScrollPlan {
  const ScrollPlan();
}

/// The text fits the panel; [png] is the single centred 64x16 frame to send.
final class ScrollStatic extends ScrollPlan {
  const ScrollStatic(this.png);
  final Uint8List png;
}

/// The text is wider than the panel; crop [strip] into 64x16 windows.
final class ScrollAnimated extends ScrollPlan {
  const ScrollAnimated({
    required this.strip,
    required this.maxOffset,
    required this.step,
    required this.initialOffset,
  });

  /// The full RGB text strip (already at panel height).
  final img.Image strip;

  /// Largest valid left offset (`strip.width - panelWidth`).
  final int maxOffset;

  /// Per-frame advance: +1 forward, -1 reverse.
  final int step;

  /// Offset of the first frame.
  final int initialOffset;
}

/// Renders [text] centred on a 64x16 canvas and encodes it to PNG.
///
/// Throws [SpriteRenderException] on any render failure.
Uint8List renderStaticPng(
  SpriteFontService fonts,
  String text,
  String fontName,
  String bgColor,
) {
  final (image, error) = fonts.renderTextFixed(
    text,
    fontName,
    bgColor: bgColor,
  );
  if (error != null || image == null) {
    throw SpriteRenderException(error ?? 'Sprite render failed');
  }
  return encodePanelPng(image);
}

/// Plans a scroll for [text]: pads, resizes to panel height, and decides
/// static-vs-animated exactly as the Python `start_scroll` does.
///
/// Throws [SpriteRenderException] on any render failure.
ScrollPlan planScroll(
  SpriteFontService fonts,
  String text,
  String fontName,
  String bgColor, {
  required bool reverse,
}) {
  final (line, error) = fonts.renderTextLine(text, fontName, bgColor: bgColor);
  if (error != null || line == null) {
    throw SpriteRenderException(error ?? 'Sprite render failed');
  }
  final bg = parseHexColor(bgColor);

  // Pad with blank columns, compositing the (RGBA) line onto a solid RGB strip.
  var strip = img.Image(
    width: line.width + kScrollPadColumns,
    height: line.height,
    numChannels: 3,
  );
  img.fill(strip, color: bg);
  compositeOnto(strip, line, 0, 0);

  // Scale to the panel height if the sheet's tiles are not already 16px tall.
  if (strip.height != panelHeight) {
    final scale = panelHeight / strip.height;
    final newW = (strip.width * scale).toInt();
    strip = img.copyResize(
      strip,
      width: newW < 1 ? 1 : newW,
      height: panelHeight,
      interpolation: img.Interpolation.nearest,
    );
  }

  if (strip.width <= panelWidth) {
    final canvas = img.Image(
      width: panelWidth,
      height: panelHeight,
      numChannels: 3,
    );
    img.fill(canvas, color: bg);
    final offsetX = floorDiv(panelWidth - strip.width, 2);
    compositeOnto(canvas, strip, offsetX, 0);
    return ScrollStatic(encodePanelPng(canvas));
  }

  final maxOffset = strip.width - panelWidth;
  return ScrollAnimated(
    strip: strip,
    maxOffset: maxOffset,
    step: reverse ? -1 : 1,
    initialOffset: reverse ? maxOffset : 0,
  );
}

/// Crops a 64x16 window from [strip] at [offset] and encodes it to PNG.
Uint8List cropScrollFrame(img.Image strip, int offset) {
  final crop = img.copyCrop(
    strip,
    x: offset,
    y: 0,
    width: panelWidth,
    height: panelHeight,
  );
  return encodePanelPng(crop);
}

/// Builds [DisplayTask]s that render text and drive it to the panel.
///
/// Reused by every text-based feature: pass the loaded [fonts], a [send] sink
/// (the device session), and a [publishFrame] callback (the live preview). The
/// returned tasks are handed to the app's `activeDisplayTaskProvider`.
class SpriteSender {
  SpriteSender({
    required this.fonts,
    required this.send,
    required this.publishFrame,
    TimerFactory? timerFactory,
  }) : _timerFactory = timerFactory ?? Timer.new;

  final SpriteFontService fonts;
  final ImageSink send;
  final FrameCallback publishFrame;
  final TimerFactory _timerFactory;

  /// A one-shot task that renders [text] centred and sends a single frame.
  DisplayTask staticText({
    required String text,
    required String fontName,
    required String bgColor,
  }) {
    return _StaticTask(
      sender: this,
      text: text,
      fontName: fontName,
      bgColor: bgColor,
    );
  }

  /// A task that scrolls [text] across the panel at [speed] (1..100).
  ///
  /// [reverse] scrolls right-to-left content the other way. If the rendered
  /// text already fits the panel the task degrades to a single static send.
  DisplayTask scrollText({
    required String text,
    required String fontName,
    required String bgColor,
    required int speed,
    required bool reverse,
  }) {
    return _ScrollTask(
      sender: this,
      text: text,
      fontName: fontName,
      bgColor: bgColor,
      speed: speed,
      reverse: reverse,
    );
  }
}

class _StaticTask implements DisplayTask {
  _StaticTask({
    required this.sender,
    required this.text,
    required this.fontName,
    required this.bgColor,
  });

  final SpriteSender sender;
  final String text;
  final String fontName;
  final String bgColor;

  /// The current send, tracked so [stop] can await it and honour the
  /// "no frames after stop returns" contract.
  Future<void>? _inFlightSend;

  @override
  Future<void> start() async {
    final png = renderStaticPng(sender.fonts, text, fontName, bgColor);
    sender.publishFrame(png);
    final send = sender.send(png);
    _inFlightSend = send;
    try {
      await send;
    } finally {
      if (identical(_inFlightSend, send)) _inFlightSend = null;
    }
  }

  @override
  Future<void> stop() async {
    // No timer to cancel, but a send may still be in flight; wait it out so a
    // caller that awaits stop() knows no further frame is coming.
    await _awaitInFlight(_inFlightSend);
  }
}

class _ScrollTask implements DisplayTask, ScrollSpeedControl {
  _ScrollTask({
    required this.sender,
    required this.text,
    required this.fontName,
    required this.bgColor,
    required this.speed,
    required this.reverse,
  });

  final SpriteSender sender;
  final String text;
  final String fontName;
  final String bgColor;
  final bool reverse;

  /// Current UI speed (1..100). Mutable so the Text page's slider can retune the
  /// scroll live; [_scheduleNext] reads it fresh each frame.
  int speed;

  @override
  void updateSpeed(int speed) {
    this.speed = speed < 1 ? 1 : (speed > 100 ? 100 : speed);
  }

  bool _running = false;
  Timer? _timer;
  img.Image? _strip;
  int _maxOffset = 0;
  int _step = 1;
  int _offset = 0;

  /// The send currently awaiting the BLE queue, tracked so [stop] can await it
  /// and guarantee no frame is delivered after stop() resolves.
  Future<void>? _inFlightSend;

  @override
  Future<void> start() async {
    final plan = planScroll(
      sender.fonts,
      text,
      fontName,
      bgColor,
      reverse: reverse,
    );
    switch (plan) {
      case ScrollStatic(:final png):
        sender.publishFrame(png);
        await sender.send(png);
        return;
      case ScrollAnimated(
        :final strip,
        :final maxOffset,
        :final step,
        :final initialOffset,
      ):
        _strip = strip;
        _maxOffset = maxOffset;
        _step = step;
        _offset = initialOffset;
        _running = true;
        // First frame fires immediately; a failure here surfaces to the caller.
        await _renderSend();
        _scheduleNext();
    }
  }

  void _scheduleNext() {
    if (!_running) return;
    _timer = sender._timerFactory(
      Duration(milliseconds: scrollIntervalMs(speed)),
      () => unawaited(_tick()),
    );
  }

  Future<void> _tick() async {
    if (!_running) return;
    _offset = advanceScrollOffset(_offset, _step, _maxOffset);
    try {
      await _renderSend();
    } on Exception catch (error, stack) {
      // A mid-scroll send failure (e.g. the guard disconnected) stops the loop
      // rather than spinning against a dead session. Only Exceptions are
      // recoverable here; an Error is a programming bug and propagates.
      log(
        'Scroll frame send failed; stopping scroll loop',
        name: _logName,
        error: error,
        stackTrace: stack,
      );
      await stop();
      return;
    }
    _scheduleNext();
  }

  Future<void> _renderSend() async {
    final strip = _strip;
    if (strip == null) return;
    final png = cropScrollFrame(strip, _offset);
    sender.publishFrame(png);
    final send = sender.send(png);
    _inFlightSend = send;
    try {
      await send;
    } finally {
      if (identical(_inFlightSend, send)) _inFlightSend = null;
    }
  }

  @override
  Future<void> stop() async {
    _running = false;
    _timer?.cancel();
    _timer = null;
    // A send may still be awaiting the BLE queue; wait it out so stop()
    // resolving means no further frame will be delivered.
    await _awaitInFlight(_inFlightSend);
  }
}

/// Awaits an in-flight send during [DisplayTask.stop], swallowing (but logging)
/// any [Exception] so stop() never throws. An [Error] still propagates — it
/// signals a programming bug, not a recoverable send failure.
Future<void> _awaitInFlight(Future<void>? inFlight) async {
  if (inFlight == null) return;
  try {
    await inFlight;
  } on Exception catch (error, stack) {
    log(
      'In-flight send failed while stopping display task',
      name: _logName,
      error: error,
      stackTrace: stack,
    );
  }
}
