import 'dart:async';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;

import 'package:ipixel_controller/features/image/gif_frames.dart';
import 'package:ipixel_controller/features/image/image_sender.dart';

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

/// A tiny solid PNG stand-in for a panel frame.
Uint8List _frame(int seed) {
  final image = img.Image(width: 4, height: 4, numChannels: 3);
  img.fill(image, color: img.ColorRgb8(seed, 0, 0));
  return img.encodePng(image);
}

List<PanelGifFrame> _gif(List<int> durationsMs) => <PanelGifFrame>[
  for (var i = 0; i < durationsMs.length; i++)
    PanelGifFrame(png: _frame(i * 40), durationMs: durationsMs[i]),
];

void main() {
  group('staticImage task', () {
    test('sends the frame once and publishes it to the preview', () async {
      final sends = <Uint8List>[];
      final previews = <Uint8List>[];
      final sender = ImageSender(
        send: (png) async => sends.add(png),
        publishFrame: previews.add,
      );
      final png = _frame(200);

      await sender.staticImage(png).start();

      expect(sends, hasLength(1));
      expect(sends.single, equals(png));
      expect(previews, hasLength(1));
      expect(previews.single, equals(png));
    });

    test('stop is safe before and after start', () async {
      final sender = ImageSender(send: (_) async {}, publishFrame: (_) {});
      final task = sender.staticImage(_frame(1));
      await task.stop();
      await task.start();
      await task.stop();
    });

    test('stop awaits an in-flight send before completing', () async {
      final gate = Completer<void>();
      var started = 0;
      final sender = ImageSender(
        send: (_) async {
          started++;
          await gate.future;
        },
        publishFrame: (_) {},
      );
      final task = sender.staticImage(_frame(1));

      final startFuture = task.start();
      await _pump();
      expect(started, 1);

      var stopDone = false;
      final stopFuture = task.stop().then((_) => stopDone = true);
      await _pump();
      expect(stopDone, isFalse, reason: 'stop waits for the in-flight send');

      gate.complete();
      await startFuture;
      await stopFuture;
      expect(stopDone, isTrue);
    });
  });

  group('gifLoop task', () {
    test('emits the first frame on start and arms one timer', () async {
      final scheduler = _ManualScheduler();
      final sends = <Uint8List>[];
      final sender = ImageSender(
        send: (png) async => sends.add(png),
        publishFrame: (_) {},
        timerFactory: scheduler.factory,
      );

      final task = sender.gifLoop(_gif(<int>[500, 500]));
      await task.start();

      expect(sends, hasLength(1));
      expect(scheduler.durations, hasLength(1));
      // First frame's authored duration is above the floor, used verbatim.
      expect(scheduler.durations.single.inMilliseconds, 500);
      await task.stop();
    });

    test(
      'advances frames and reschedules only after each send completes',
      () async {
        final scheduler = _ManualScheduler();
        final sends = <Uint8List>[];
        final sender = ImageSender(
          send: (png) async => sends.add(png),
          publishFrame: (_) {},
          timerFactory: scheduler.factory,
        );

        final frames = _gif(<int>[500, 500, 500]);
        final task = sender.gifLoop(frames);
        await task.start();
        expect(sends, hasLength(1));
        expect(sends.single, equals(frames[0].png));

        // Firing the timer sends the next frame synchronously, but the NEXT timer
        // is only armed once that send completes — proving frames never overlap.
        scheduler.latest.fire();
        expect(sends, hasLength(2));
        expect(sends.last, equals(frames[1].png));
        expect(
          scheduler.durations,
          hasLength(1),
          reason: 'no reschedule mid-send',
        );
        await _pump();
        expect(
          scheduler.durations,
          hasLength(2),
          reason: 'rescheduled after send',
        );
        await task.stop();
      },
    );

    test('loops back to the first frame after the last', () async {
      final scheduler = _ManualScheduler();
      final sends = <Uint8List>[];
      final sender = ImageSender(
        send: (png) async => sends.add(png),
        publishFrame: (_) {},
        timerFactory: scheduler.factory,
      );
      final frames = _gif(<int>[500, 500]);
      final task = sender.gifLoop(frames);
      await task.start(); // frame 0

      scheduler.latest.fire(); // frame 1
      await _pump();
      scheduler.latest.fire(); // wraps to frame 0
      await _pump();

      expect(sends, hasLength(3));
      expect(sends[2], equals(frames[0].png), reason: 'looped to frame 0');
      await task.stop();
    });

    test('applies the panel-safe floor to fast frames at play time', () async {
      final scheduler = _ManualScheduler();
      final sender = ImageSender(
        send: (_) async {},
        publishFrame: (_) {},
        timerFactory: scheduler.factory,
      );
      // 40 ms authored frames must play no faster than the 320 ms floor.
      final task = sender.gifLoop(_gif(<int>[40, 40]));
      await task.start();

      expect(
        scheduler.durations.single.inMilliseconds,
        kGifMinFrameIntervalMs,
        reason: 'a fast GIF is clamped up to the panel floor',
      );
      await task.stop();
    });

    test(
      'a single-frame GIF degrades to a static send with no timer',
      () async {
        final scheduler = _ManualScheduler();
        final sends = <Uint8List>[];
        final sender = ImageSender(
          send: (png) async => sends.add(png),
          publishFrame: (_) {},
          timerFactory: scheduler.factory,
        );
        await sender.gifLoop(_gif(<int>[500])).start();

        expect(sends, hasLength(1));
        expect(scheduler.durations, isEmpty, reason: 'nothing to loop to');
      },
    );

    test('stop cancels the timer so no further frames are sent', () async {
      final scheduler = _ManualScheduler();
      final sends = <Uint8List>[];
      final sender = ImageSender(
        send: (png) async => sends.add(png),
        publishFrame: (_) {},
        timerFactory: scheduler.factory,
      );
      final task = sender.gifLoop(_gif(<int>[500, 500]));
      await task.start();
      expect(sends, hasLength(1));

      await task.stop();
      scheduler.latest.fire(); // cancelled timer: callback is inert
      await _pump();
      expect(sends, hasLength(1), reason: 'no frames after stop');
    });

    test('a mid-loop send failure stops the loop without escaping', () async {
      final scheduler = _ManualScheduler();
      final sends = <Uint8List>[];
      var callCount = 0;
      final sender = ImageSender(
        send: (png) async {
          callCount++;
          if (callCount == 2) throw Exception('send boom');
          sends.add(png);
        },
        publishFrame: (_) {},
        timerFactory: scheduler.factory,
      );
      final task = sender.gifLoop(_gif(<int>[500, 500]));
      await task.start();
      expect(sends, hasLength(1));
      expect(scheduler.durations, hasLength(1));

      // Fire the timer: the second send throws inside _tick. The callback is
      // `unawaited(_tick())`, so a leaked exception would fail the test.
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
  });
}
