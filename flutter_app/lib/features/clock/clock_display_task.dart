/// A [DisplayTask] that ticks a clock/countdown onto the panel.
///
/// It owns a single self-rescheduling timer: each tick re-renders the current
/// display string and **sends only when that string changed** since the last
/// frame that reached the panel. That change-only-send discipline is the
/// ESP32 lesson (`CLAUDE.md`: "compare the formatted text string … not the raw
/// time") — a per-second timer that re-sent an identical frame every tick would
/// hammer the BLE queue and trip the disconnect guard.
///
/// Everything time-dependent is injected: [renderText] turns a [DateTime] into
/// the string to show, [nextDelay] turns a [DateTime] into the delay before the
/// next tick, and [now] supplies the current time. Tests drive them with a fake
/// clock and a manual [TimerFactory] instead of waiting on the wall clock.
library;

import 'dart:async';
import 'dart:developer';

import 'package:ipixel_controller/display/display_task.dart';
import 'package:ipixel_controller/display/sprite_sender.dart';
import 'package:ipixel_controller/render/sprite_font.dart';

/// Logging channel for clock-task failures surfaced via `dart:developer`.
const String _logName = 'ClockDisplayTask';

/// Drives a clock or countdown onto the panel, one frame per *change*.
class ClockDisplayTask implements DisplayTask {
  ClockDisplayTask({
    required this.fonts,
    required this.fontName,
    required this.bgColor,
    required this.send,
    required this.publishFrame,
    required this.renderText,
    required this.nextDelay,
    DateTime Function()? now,
    TimerFactory? timerFactory,
  }) : _now = now ?? DateTime.now,
       _timerFactory = timerFactory ?? Timer.new;

  final SpriteFontService fonts;
  final String fontName;
  final String bgColor;
  final ImageSink send;
  final FrameCallback publishFrame;

  /// The current display string for a given instant.
  final String Function(DateTime now) renderText;

  /// The delay before the next tick, given the instant that tick was scheduled.
  final Duration Function(DateTime now) nextDelay;

  final DateTime Function() _now;
  final TimerFactory _timerFactory;

  bool _running = false;
  Timer? _timer;

  /// The last string actually sent to the panel, or `null` before the first
  /// send. The dedupe compares against this so an unchanged tick sends nothing.
  String? _lastSentText;

  /// The send currently awaiting the BLE queue, tracked so [stop] can await it
  /// and honour the "no frame after stop resolves" contract.
  Future<void>? _inFlightSend;

  @override
  Future<void> start() async {
    _running = true;
    // First frame always renders and sends (nothing has been shown yet); a
    // render failure here (e.g. unknown font) surfaces to the caller and leaves
    // the display slot empty.
    await _renderMaybeSend();
    _scheduleNext();
  }

  void _scheduleNext() {
    if (!_running) return;
    _timer = _timerFactory(nextDelay(_now()), () => unawaited(_tick()));
  }

  Future<void> _tick() async {
    if (!_running) return;
    try {
      await _renderMaybeSend();
    } on Exception catch (error, stack) {
      // A mid-run send failure (e.g. the guard disconnected) stops the loop
      // rather than spinning against a dead session. Only Exceptions are
      // recoverable; an Error is a programming bug and propagates.
      log(
        'Clock frame send failed; stopping clock loop',
        name: _logName,
        error: error,
        stackTrace: stack,
      );
      await stop();
      return;
    }
    _scheduleNext();
  }

  Future<void> _renderMaybeSend() async {
    final text = renderText(_now());
    // Change-only send: skip the encode + BLE write when nothing changed.
    if (text == _lastSentText) return;
    final png = renderStaticPng(fonts, text, fontName, bgColor);
    publishFrame(png);
    final send = this.send(png);
    _inFlightSend = send;
    try {
      await send;
      // Only mark the string sent once the write actually resolved, so a failed
      // frame is retried on the next tick instead of being deduped away.
      _lastSentText = text;
    } finally {
      if (identical(_inFlightSend, send)) _inFlightSend = null;
    }
  }

  @override
  Future<void> stop() async {
    _running = false;
    _timer?.cancel();
    _timer = null;
    final inFlight = _inFlightSend;
    if (inFlight == null) return;
    try {
      await inFlight;
    } on Exception catch (error, stack) {
      log(
        'In-flight send failed while stopping clock task',
        name: _logName,
        error: error,
        stackTrace: stack,
      );
    }
  }
}
