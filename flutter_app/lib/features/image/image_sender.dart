/// Drives a static image or an animated GIF onto the panel as [DisplayTask]s.
///
/// The static path sends one 64x16 frame. The GIF path loops the pre-decoded
/// frames on a single self-rescheduling timer, exactly mirroring the discipline
/// in `display/sprite_sender.dart`:
///
/// * The timer reschedules itself only after each frame's send *completes*, so a
///   slow BLE write never lets frames pile up ahead of the panel's queue.
/// * Every per-frame interval is floored at [kGifMinFrameIntervalMs] — the
///   ~320 ms panel-safe minimum for full-frame writes (see CLAUDE.md), so even a
///   fast-authored GIF cannot push writes below what the panel sustains.
/// * A mid-loop send failure stops the loop rather than spinning against a dead
///   session.
///
/// Reuses the [ImageSink] / [FrameCallback] / [TimerFactory] typedefs from
/// `sprite_sender.dart` so every feature drives the panel through one seam.
library;

import 'dart:async';
import 'dart:developer';
import 'dart:typed_data';

import 'package:ipixel_controller/display/display_task.dart';
import 'package:ipixel_controller/display/sprite_sender.dart'
    show FrameCallback, ImageSink, TimerFactory;
import 'package:ipixel_controller/features/image/gif_frames.dart';

/// Logging channel for image/GIF display-task failures.
const String _logName = 'ImageSender';

/// Builds [DisplayTask]s that send a static image or loop a GIF to the panel.
///
/// Pass a [send] sink (the device session) and a [publishFrame] callback (the
/// live preview). The returned tasks are handed to the app's
/// `activeDisplayTaskProvider`.
class ImageSender {
  ImageSender({
    required this.send,
    required this.publishFrame,
    TimerFactory? timerFactory,
  }) : _timerFactory = timerFactory ?? Timer.new;

  final ImageSink send;
  final FrameCallback publishFrame;
  final TimerFactory _timerFactory;

  /// A one-shot task that sends [png] once and completes.
  DisplayTask staticImage(Uint8List png) =>
      _StaticImageTask(sender: this, png: png);

  /// A task that loops [frames], showing each for its panel-floored duration.
  ///
  /// A single-frame list degrades to one static send with no timer.
  DisplayTask gifLoop(List<PanelGifFrame> frames) =>
      _GifLoopTask(sender: this, frames: frames);
}

class _StaticImageTask implements DisplayTask {
  _StaticImageTask({required this.sender, required this.png});

  final ImageSender sender;
  final Uint8List png;

  /// The current send, tracked so [stop] can await it and honour the
  /// "no frames after stop returns" contract.
  Future<void>? _inFlightSend;

  @override
  Future<void> start() async {
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

class _GifLoopTask implements DisplayTask {
  _GifLoopTask({required this.sender, required this.frames});

  final ImageSender sender;
  final List<PanelGifFrame> frames;

  bool _running = false;
  Timer? _timer;
  int _index = 0;

  /// The send currently awaiting the BLE queue, tracked so [stop] can await it
  /// and guarantee no frame is delivered after stop() resolves.
  Future<void>? _inFlightSend;

  @override
  Future<void> start() async {
    if (frames.isEmpty) {
      throw const _EmptyGifException();
    }
    _index = 0;
    _running = true;
    // First frame fires immediately; a failure here surfaces to the caller.
    await _renderSend();
    _scheduleNext();
  }

  /// Arms the next frame's timer using the *currently shown* frame's duration,
  /// floored to the panel-safe minimum. A single-frame GIF never schedules —
  /// there is nothing to advance to.
  void _scheduleNext() {
    if (!_running || frames.length < 2) return;
    final intervalMs = gifFrameIntervalMs(frames[_index].durationMs);
    _timer = sender._timerFactory(
      Duration(milliseconds: intervalMs),
      () => unawaited(_tick()),
    );
  }

  Future<void> _tick() async {
    if (!_running) return;
    _index = (_index + 1) % frames.length;
    try {
      await _renderSend();
    } on Exception catch (error, stack) {
      // A mid-loop send failure (e.g. the guard disconnected) stops the loop
      // rather than spinning against a dead session. Only Exceptions are
      // recoverable here; an Error is a programming bug and propagates.
      log(
        'GIF frame send failed; stopping playback loop',
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
    final png = frames[_index].png;
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

/// Raised when a GIF loop task is started with no frames — a programming error
/// the page guards against before building the task.
class _EmptyGifException implements Exception {
  const _EmptyGifException();
  @override
  String toString() => 'Cannot play a GIF with no frames';
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
      'In-flight send failed while stopping image task',
      name: _logName,
      error: error,
      stackTrace: stack,
    );
  }
}
