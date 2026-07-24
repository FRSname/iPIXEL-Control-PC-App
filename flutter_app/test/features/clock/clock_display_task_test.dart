import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';

import 'package:ipixel_controller/features/clock/clock_display_task.dart';
import 'package:ipixel_controller/features/clock/clock_time.dart';
import 'package:ipixel_controller/display/sprite_sender.dart';
import 'package:ipixel_controller/render/sprite_font.dart';

const String _textOrder =
    '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:!?.,+-/\$%';

SpriteFontService _textFontService() {
  final bytes = File('assets/sprites/TextSprite.png').readAsBytesSync();
  final font = SpriteFont(
    name: 'Text Default',
    path: 'assets/sprites/TextSprite.png',
    order: _textOrder,
    cols: 73,
  )..loadFromBytes(bytes);
  return SpriteFontService()..registerFont(font);
}

/// A [Timer] whose callback fires only when the test calls [fire].
class _ManualTimer implements Timer {
  _ManualTimer(this._callback);

  final void Function() _callback;
  bool _active = true;

  void fire() {
    if (_active) _callback();
  }

  @override
  void cancel() => _active = false;

  @override
  bool get isActive => _active;

  @override
  int get tick => 0;
}

/// Captures scheduled timers + durations and hands back [_ManualTimer]s.
class _ManualScheduler {
  final List<Duration> durations = <Duration>[];
  final List<_ManualTimer> timers = <_ManualTimer>[];

  Timer factory(Duration duration, void Function() callback) {
    durations.add(duration);
    final timer = _ManualTimer(callback);
    timers.add(timer);
    return timer;
  }

  _ManualTimer get latest => timers.last;
}

/// Lets a microtask/timer drain so awaited sends complete.
Future<void> _pump() => Future<void>.delayed(Duration.zero);

void main() {
  group('ClockDisplayTask change-only send', () {
    test('sends the first frame, then only when the string changes', () async {
      final scheduler = _ManualScheduler();
      final sends = <Uint8List>[];
      var now = DateTime(2026, 1, 1, 12, 0, 0);

      final task = ClockDisplayTask(
        fonts: _textFontService(),
        fontName: 'Text Default',
        bgColor: '#000000',
        send: (png) async => sends.add(png),
        publishFrame: (_) {},
        renderText: (n) => formatCustomTime(n, '%H:%M:%S'),
        nextDelay: (_) => const Duration(seconds: 1),
        now: () => now,
        timerFactory: scheduler.factory,
      );

      await task.start();
      expect(sends, hasLength(1), reason: 'first frame always sends');
      expect(scheduler.durations, hasLength(1), reason: 'timer armed');

      // Same second: the rendered string is identical, so nothing is sent.
      scheduler.latest.fire();
      await _pump();
      expect(sends, hasLength(1), reason: 'identical render is deduped');
      expect(scheduler.durations, hasLength(2), reason: 'still rescheduled');

      // The clock advances a second: the string changes, so a frame is sent.
      now = DateTime(2026, 1, 1, 12, 0, 1);
      scheduler.latest.fire();
      await _pump();
      expect(sends, hasLength(2), reason: 'changed render is sent');

      // Same second again: deduped once more.
      scheduler.latest.fire();
      await _pump();
      expect(sends, hasLength(2));

      await task.stop();
    });

    test('a minute clock sends once per minute, not once per tick', () async {
      final scheduler = _ManualScheduler();
      final sends = <Uint8List>[];
      var now = DateTime(2026, 1, 1, 12, 0, 0);

      final task = ClockDisplayTask(
        fonts: _textFontService(),
        fontName: 'Text Default',
        bgColor: '#000000',
        send: (png) async => sends.add(png),
        publishFrame: (_) {},
        renderText: (n) => formatCustomTime(n, '%H:%M'),
        nextDelay: (_) => const Duration(seconds: 1),
        now: () => now,
        timerFactory: scheduler.factory,
      );

      await task.start();
      // Tick through 59 seconds within the same minute: no new sends.
      for (var s = 1; s < 60; s++) {
        now = DateTime(2026, 1, 1, 12, 0, s);
        scheduler.latest.fire();
        await _pump();
      }
      expect(sends, hasLength(1), reason: 'minute unchanged across the ticks');

      // Cross the minute boundary: exactly one send.
      now = DateTime(2026, 1, 1, 12, 1, 0);
      scheduler.latest.fire();
      await _pump();
      expect(sends, hasLength(2));

      await task.stop();
    });
  });

  group('ClockDisplayTask countdown', () {
    test('reaches a stable zero state and stops sending', () async {
      final scheduler = _ManualScheduler();
      final sends = <Uint8List>[];
      final rendered = <String>[];
      final target = DateTime(2026, 1, 1, 12, 0, 0);
      var now = target.subtract(const Duration(seconds: 2));

      String render(DateTime n) {
        final text = formatCountdown(n, target, CountdownFormat.hoursMinsSecs);
        rendered.add(text);
        return text;
      }

      final task = ClockDisplayTask(
        fonts: _textFontService(),
        fontName: 'Text Default',
        bgColor: '#000000',
        send: (png) async => sends.add(png),
        publishFrame: (_) {},
        renderText: render,
        nextDelay: (_) => const Duration(seconds: 1),
        now: () => now,
        timerFactory: scheduler.factory,
      );

      await task.start(); // 0:00:02
      now = target.subtract(const Duration(seconds: 1));
      scheduler.latest.fire();
      await _pump(); // 0:00:01

      now = target;
      scheduler.latest.fire();
      await _pump(); // NOW!

      now = target.add(const Duration(seconds: 1));
      scheduler.latest.fire();
      await _pump(); // still NOW! -> deduped

      expect(
        sends,
        hasLength(3),
        reason: '0:00:02, 0:00:01, NOW! — the stable zero state sent once',
      );
      expect(rendered.last, kCountdownZeroText);
      expect(
        rendered.where((t) => t == kCountdownZeroText).length,
        greaterThanOrEqualTo(2),
        reason: 'rendered NOW! at zero and past zero, but only sent once',
      );

      await task.stop();
    });
  });

  group('ClockDisplayTask lifecycle', () {
    test('stop cancels the timer so no further frames are sent', () async {
      final scheduler = _ManualScheduler();
      final sends = <Uint8List>[];
      var now = DateTime(2026, 1, 1, 12, 0, 0);

      final task = ClockDisplayTask(
        fonts: _textFontService(),
        fontName: 'Text Default',
        bgColor: '#000000',
        send: (png) async => sends.add(png),
        publishFrame: (_) {},
        renderText: (n) => formatCustomTime(n, '%H:%M:%S'),
        nextDelay: (_) => const Duration(seconds: 1),
        now: () => now,
        timerFactory: scheduler.factory,
      );

      await task.start();
      expect(sends, hasLength(1));

      await task.stop();
      now = DateTime(2026, 1, 1, 12, 0, 5);
      scheduler.latest.fire(); // cancelled timer: callback is inert
      await _pump();
      expect(sends, hasLength(1), reason: 'no frames after stop');
    });

    test('a mid-run send failure stops the loop', () async {
      final scheduler = _ManualScheduler();
      final sends = <Uint8List>[];
      var callCount = 0;
      var now = DateTime(2026, 1, 1, 12, 0, 0);

      final task = ClockDisplayTask(
        fonts: _textFontService(),
        fontName: 'Text Default',
        bgColor: '#000000',
        send: (png) async {
          callCount++;
          if (callCount == 2) throw Exception('send boom');
          sends.add(png);
        },
        publishFrame: (_) {},
        renderText: (n) => formatCustomTime(n, '%H:%M:%S'),
        nextDelay: (_) => const Duration(seconds: 1),
        now: () => now,
        timerFactory: scheduler.factory,
      );

      await task.start();
      expect(sends, hasLength(1));
      expect(scheduler.durations, hasLength(1));

      now = DateTime(2026, 1, 1, 12, 0, 1);
      scheduler.latest.fire();
      await _pump();
      await _pump();

      expect(callCount, 2);
      expect(sends, hasLength(1), reason: 'the failed frame is not recorded');
      expect(
        scheduler.durations,
        hasLength(1),
        reason: 'no reschedule after a failure (stop cleanup ran)',
      );
    });

    test('start surfaces a render error for an unknown font', () async {
      final task = ClockDisplayTask(
        fonts: _textFontService(),
        fontName: 'Missing',
        bgColor: '#000000',
        send: (_) async {},
        publishFrame: (_) {},
        renderText: (n) => formatCustomTime(n, '%H:%M'),
        nextDelay: (_) => const Duration(seconds: 1),
        now: DateTime.now,
      );

      await expectLater(task.start(), throwsA(isA<SpriteRenderException>()));
    });
  });
}
