import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;

import 'package:ipixel_controller/display/display_task.dart';
import 'package:ipixel_controller/display/sprite_sender.dart';
import 'package:ipixel_controller/render/panel_image.dart';
import 'package:ipixel_controller/render/sprite_font.dart';

const String _textOrder =
    '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:!?.,+-/\$%';

/// Loads the bundled default text font (7x16 tiles, 73 glyphs) from disk.
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
  group('advanceScrollOffset', () {
    test('advances forward and wraps back to zero past the end', () {
      expect(advanceScrollOffset(0, 1, 3), 1);
      expect(advanceScrollOffset(2, 1, 3), 3);
      expect(advanceScrollOffset(3, 1, 3), 0);
    });

    test('advances in reverse and wraps to maxOffset past zero', () {
      expect(advanceScrollOffset(3, -1, 3), 2);
      expect(advanceScrollOffset(1, -1, 3), 0);
      expect(advanceScrollOffset(0, -1, 3), 3);
    });

    test('a multi-pixel step lands on the far edge before wrapping', () {
      // Forward: an overshooting step lands exactly on maxOffset (so the last
      // columns are shown), then wraps to 0 on the following frame.
      expect(advanceScrollOffset(8, 4, 10), 10);
      expect(advanceScrollOffset(10, 4, 10), 0);
      // Reverse: an overshooting step lands on 0, then wraps to maxOffset.
      expect(advanceScrollOffset(2, -4, 10), 0);
      expect(advanceScrollOffset(0, -4, 10), 10);
    });
  });

  group('scrollIntervalMs', () {
    test('maps the slider endpoints to the panel-safe band', () {
      // Slowest speed → the slow-crawl ceiling; fastest → the 120 ms floor.
      expect(scrollIntervalMs(1), kScrollMaxIntervalMs); // 540
      expect(scrollIntervalMs(100), kScrollMinIntervalMs); // 120
    });

    test('spreads the mid-range across the band instead of flattening it', () {
      // Regression for the flattened-slider bug: under the legacy 220-speed*2
      // mapping every speed >= 50 collapsed to exactly 120 ms. Now each of these
      // is a distinct, monotonically-decreasing rate above the floor.
      expect(scrollIntervalMs(50), 332);
      expect(scrollIntervalMs(75), 226);
      expect(scrollIntervalMs(90), 162);
      // The whole upper half is a genuine spread, not one repeated value.
      expect(scrollIntervalMs(60), greaterThan(scrollIntervalMs(80)));
      expect(scrollIntervalMs(80), greaterThan(scrollIntervalMs(100)));
    });

    test('is monotonic and never drops below the floor across 1..100', () {
      var previous = scrollIntervalMs(1);
      for (var speed = 2; speed <= 100; speed++) {
        final interval = scrollIntervalMs(speed);
        expect(
          interval,
          lessThanOrEqualTo(previous),
          reason: 'speed $speed must not be slower than $previous',
        );
        expect(interval, greaterThanOrEqualTo(kScrollMinIntervalMs));
        previous = interval;
      }
    });

    test('clamps out-of-range speeds to the endpoints', () {
      expect(scrollIntervalMs(0), kScrollMaxIntervalMs);
      expect(scrollIntervalMs(-5), kScrollMaxIntervalMs);
      expect(scrollIntervalMs(101), kScrollMinIntervalMs);
      expect(scrollIntervalMs(500), kScrollMinIntervalMs);
    });
  });

  group('scrollStepPx', () {
    test('spans 1 px at the slow end to kScrollMaxStepPx at the fast end', () {
      expect(scrollStepPx(1), 1);
      expect(scrollStepPx(100), kScrollMaxStepPx);
    });

    test('is monotonic non-decreasing across the slider', () {
      var previous = scrollStepPx(1);
      for (var speed = 2; speed <= 100; speed++) {
        final step = scrollStepPx(speed);
        expect(step, greaterThanOrEqualTo(previous));
        previous = step;
      }
    });

    test('the fast end steps more pixels than the slow end', () {
      expect(scrollStepPx(100), greaterThan(scrollStepPx(1)));
    });

    test('clamps out-of-range speeds to the 1..max band', () {
      expect(scrollStepPx(0), 1);
      expect(scrollStepPx(-5), 1);
      expect(scrollStepPx(101), kScrollMaxStepPx);
      expect(scrollStepPx(500), kScrollMaxStepPx);
    });
  });

  group('cropScrollFrame', () {
    test('returns a 64x16 window starting at the given offset', () {
      // A strip whose column x is encoded in the red channel.
      final strip = img.Image(width: 128, height: panelHeight, numChannels: 3);
      for (var x = 0; x < strip.width; x++) {
        for (var y = 0; y < strip.height; y++) {
          strip.setPixelRgb(x, y, x, 0, 0);
        }
      }

      for (final offset in <int>[0, 10, 40]) {
        final png = cropScrollFrame(strip, offset);
        final decoded = img.decodePng(png)!;
        expect(decoded.width, panelWidth);
        expect(decoded.height, panelHeight);
        // Leftmost column of the crop is column `offset` of the strip.
        expect(decoded.getPixel(0, 0).r, offset);
        expect(decoded.getPixel(1, 0).r, offset + 1);
      }
    });
  });

  group('renderStaticPng', () {
    test('encodes a 64x16 PNG for valid text', () {
      final png = renderStaticPng(
        _textFontService(),
        'HI',
        'Text Default',
        '#000000',
      );
      final decoded = img.decodePng(png)!;
      expect(decoded.width, panelWidth);
      expect(decoded.height, panelHeight);
    });

    test('throws SpriteRenderException for an unknown font', () {
      expect(
        () => renderStaticPng(_textFontService(), 'HI', 'Missing', '#000000'),
        throwsA(isA<SpriteRenderException>()),
      );
    });
  });

  group('planScroll', () {
    test('returns a static centred frame when the text fits the panel', () {
      final plan = planScroll(
        _textFontService(),
        'HI',
        'Text Default',
        '#000000',
        reverse: false,
      );
      expect(plan, isA<ScrollStatic>());
    });

    test('returns an animated strip when the text is wider than the panel', () {
      final plan = planScroll(
        _textFontService(),
        'ABCDEFGHIJKLMNOP', // 16 * 7 + 8 pad = 120 px wide
        'Text Default',
        '#000000',
        reverse: false,
      );
      expect(plan, isA<ScrollAnimated>());
      final animated = plan as ScrollAnimated;
      expect(animated.strip.height, panelHeight);
      expect(animated.maxOffset, animated.strip.width - panelWidth);
      expect(animated.step, 1);
      expect(animated.initialOffset, 0);
    });

    test('reverse animation starts at the far end and steps backward', () {
      final plan = planScroll(
        _textFontService(),
        'ABCDEFGHIJKLMNOP',
        'Text Default',
        '#000000',
        reverse: true,
      );
      final animated = plan as ScrollAnimated;
      expect(animated.step, -1);
      expect(animated.initialOffset, animated.maxOffset);
    });
  });

  group('SpriteSender static task', () {
    test('sends exactly one frame and publishes it to the preview', () async {
      final sends = <Uint8List>[];
      final previews = <Uint8List>[];
      final sender = SpriteSender(
        fonts: _textFontService(),
        send: (png) async => sends.add(png),
        publishFrame: previews.add,
      );

      final task = sender.staticText(
        text: 'HI',
        fontName: 'Text Default',
        bgColor: '#FFFFFF',
      );
      await task.start();

      expect(sends, hasLength(1));
      expect(previews, hasLength(1));
      expect(previews.single, equals(sends.single));
      final decoded = img.decodePng(sends.single)!;
      expect(decoded.width, panelWidth);
      expect(decoded.height, panelHeight);
    });
  });

  group('SpriteSender scroll task', () {
    test(
      'emits the first frame on start and reschedules after each send',
      () async {
        final scheduler = _ManualScheduler();
        final sends = <Uint8List>[];
        final previews = <Uint8List>[];
        final sender = SpriteSender(
          fonts: _textFontService(),
          send: (png) async => sends.add(png),
          publishFrame: previews.add,
          timerFactory: scheduler.factory,
        );

        final task = sender.scrollText(
          text: 'ABCDEFGHIJKLMNOP',
          fontName: 'Text Default',
          bgColor: '#000000',
          speed: 50,
          reverse: false,
        );
        await task.start();

        // First frame sent; exactly one timer armed at speed 50's interval.
        expect(sends, hasLength(1));
        expect(scheduler.durations, hasLength(1));
        expect(scheduler.durations.single.inMilliseconds, scrollIntervalMs(50));

        // Firing the timer sends the next frame synchronously, but the NEXT timer
        // is only armed once that send completes — proving frames never overlap.
        scheduler.latest.fire();
        expect(sends, hasLength(2));
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

        // Every frame is a valid 64x16 panel image.
        for (final png in sends) {
          final decoded = img.decodePng(png)!;
          expect(decoded.width, panelWidth);
          expect(decoded.height, panelHeight);
        }
        expect(previews, hasLength(sends.length));
      },
    );

    test(
      'a live speed change retunes the next frame without a restart',
      () async {
        final scheduler = _ManualScheduler();
        final sends = <Uint8List>[];
        final sender = SpriteSender(
          fonts: _textFontService(),
          send: (png) async => sends.add(png),
          publishFrame: (_) {},
          timerFactory: scheduler.factory,
        );

        final task = sender.scrollText(
          text: 'ABCDEFGHIJKLMNOP',
          fontName: 'Text Default',
          bgColor: '#000000',
          speed: 1, // slowest → 540 ms
          reverse: false,
        );
        await task.start();

        // First frame armed at the slow rate.
        expect(scheduler.durations.single.inMilliseconds, scrollIntervalMs(1));
        expect(scrollIntervalMs(1), kScrollMaxIntervalMs);

        // Retune to the fastest speed mid-scroll. The offset is preserved (only
        // one frame sent so far); the NEXT reschedule must pick up the new rate.
        expect(task, isA<ScrollSpeedControl>());
        (task as ScrollSpeedControl).updateSpeed(100);

        scheduler.latest.fire();
        await _pump();

        expect(
          sends,
          hasLength(2),
          reason: 'scroll continued, was not restarted',
        );
        expect(scheduler.durations, hasLength(2));
        expect(
          scheduler.durations.last.inMilliseconds,
          scrollIntervalMs(100),
          reason: 'next frame uses the updated speed',
        );
        expect(scrollIntervalMs(100), kScrollMinIntervalMs);
      },
    );

    test(
      'the fast speed advances several pixels per frame, wrapping much sooner',
      () async {
        bool sameBytes(Uint8List a, Uint8List b) {
          if (a.length != b.length) return false;
          for (var i = 0; i < a.length; i++) {
            if (a[i] != b[i]) return false;
          }
          return true;
        }

        // Drives a scroll at [speed], returning the send index at which the
        // offset-0 frame recurs (a full wrap), or -1 if it has not wrapped
        // within the fired window. A larger per-frame pixel step wraps sooner.
        Future<int> wrapIndexAtSpeed(int speed) async {
          final scheduler = _ManualScheduler();
          final sends = <Uint8List>[];
          final sender = SpriteSender(
            fonts: _textFontService(),
            send: (png) async => sends.add(png),
            publishFrame: (_) {},
            timerFactory: scheduler.factory,
          );
          final task = sender.scrollText(
            text: 'ABCDEFGHIJKLMNOP',
            fontName: 'Text Default',
            // A contrasting background makes each 64-wide window pixel-distinct,
            // so a recurring offset-0 frame reliably signals a full wrap (on a
            // matching background the strip is uniform and the offset is
            // unobservable from frame content).
            bgColor: '#FFFFFF',
            speed: speed,
            reverse: false,
          );
          await task.start(); // sends[0] is offset 0
          for (var fired = 0; fired < 20; fired++) {
            scheduler.latest.fire();
            await _pump();
            if (sameBytes(sends.last, sends.first)) {
              await task.stop();
              return sends.length - 1;
            }
          }
          await task.stop();
          return -1;
        }

        final fast = await wrapIndexAtSpeed(100);
        final slow = await wrapIndexAtSpeed(1);

        expect(
          fast,
          greaterThan(0),
          reason: 'fast speed steps multiple px/frame and wraps within 20',
        );
        expect(
          slow,
          -1,
          reason: 'slow speed (1 px/frame) does not wrap within 20 frames',
        );
      },
    );

    test('stop cancels the timer so no further frames are sent', () async {
      final scheduler = _ManualScheduler();
      final sends = <Uint8List>[];
      final sender = SpriteSender(
        fonts: _textFontService(),
        send: (png) async => sends.add(png),
        publishFrame: (_) {},
        timerFactory: scheduler.factory,
      );

      final task = sender.scrollText(
        text: 'ABCDEFGHIJKLMNOP',
        fontName: 'Text Default',
        bgColor: '#000000',
        speed: 50,
        reverse: false,
      );
      await task.start();
      expect(sends, hasLength(1));

      await task.stop();
      scheduler.latest.fire(); // cancelled timer: callback is inert
      await _pump();

      expect(sends, hasLength(1), reason: 'no frames after stop');
    });

    test(
      'a mid-scroll send failure stops the loop without escaping the timer',
      () async {
        final scheduler = _ManualScheduler();
        final sends = <Uint8List>[];
        var callCount = 0;
        final sender = SpriteSender(
          fonts: _textFontService(),
          // The second send (first timer tick) throws; earlier ones record.
          send: (png) async {
            callCount++;
            if (callCount == 2) throw Exception('send boom');
            sends.add(png);
          },
          publishFrame: (_) {},
          timerFactory: scheduler.factory,
        );

        final task = sender.scrollText(
          text: 'ABCDEFGHIJKLMNOP',
          fontName: 'Text Default',
          bgColor: '#000000',
          speed: 50,
          reverse: false,
        );
        await task.start();
        expect(sends, hasLength(1));
        expect(scheduler.durations, hasLength(1), reason: 'first timer armed');

        // Fire the timer: the second send throws inside _tick. The callback is
        // `unawaited(_tick())`, so a leaked exception would surface as an
        // unhandled async error and fail the test.
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

        // The timer stop() cancelled is inert if it somehow fires again.
        scheduler.latest.fire();
        await _pump();
        expect(sends, hasLength(1));
        expect(scheduler.durations, hasLength(1));
      },
    );

    test('stop awaits an in-flight send before completing', () async {
      final scheduler = _ManualScheduler();
      final gate = Completer<void>();
      var sendStarted = 0;
      final sender = SpriteSender(
        fonts: _textFontService(),
        send: (png) async {
          sendStarted++;
          await gate.future;
        },
        publishFrame: (_) {},
        timerFactory: scheduler.factory,
      );

      final task = sender.scrollText(
        text: 'ABCDEFGHIJKLMNOP',
        fontName: 'Text Default',
        bgColor: '#000000',
        speed: 50,
        reverse: false,
      );
      // start() awaits the first frame's send, which blocks on the gate.
      final startFuture = task.start();
      await _pump();
      expect(sendStarted, 1);

      // stop() must not resolve until the in-flight send resolves.
      var stopDone = false;
      final stopFuture = task.stop().then((_) => stopDone = true);
      await _pump();
      expect(stopDone, isFalse, reason: 'stop waits for the in-flight send');

      gate.complete();
      await startFuture;
      await stopFuture;
      expect(stopDone, isTrue);
      // No timer was armed after stop, so no frames keep coming.
      expect(scheduler.durations, isEmpty);
    });

    test('degrades to a single static send when the text fits', () async {
      final scheduler = _ManualScheduler();
      final sends = <Uint8List>[];
      final sender = SpriteSender(
        fonts: _textFontService(),
        send: (png) async => sends.add(png),
        publishFrame: (_) {},
        timerFactory: scheduler.factory,
      );

      final task = sender.scrollText(
        text: 'HI',
        fontName: 'Text Default',
        bgColor: '#000000',
        speed: 50,
        reverse: false,
      );
      await task.start();

      expect(sends, hasLength(1));
      expect(scheduler.durations, isEmpty, reason: 'fits: no scroll timer');
    });

    test('start surfaces a render error for an unknown font', () async {
      final sender = SpriteSender(
        fonts: _textFontService(),
        send: (_) async {},
        publishFrame: (_) {},
      );
      final task = sender.scrollText(
        text: 'ABCDEFGHIJKLMNOP',
        fontName: 'Missing',
        bgColor: '#000000',
        speed: 50,
        reverse: false,
      );

      await expectLater(task.start(), throwsA(isA<SpriteRenderException>()));
    });
  });

  group('DisplayTask contract', () {
    test('static task stop is safe to call before and after start', () async {
      final sender = SpriteSender(
        fonts: _textFontService(),
        send: (_) async {},
        publishFrame: (_) {},
      );
      final DisplayTask task = sender.staticText(
        text: 'HI',
        fontName: 'Text Default',
        bgColor: '#000000',
      );
      await task.stop(); // before start
      await task.start();
      await task.stop(); // after start
    });
  });
}
