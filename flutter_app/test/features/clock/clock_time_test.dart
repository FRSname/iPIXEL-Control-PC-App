import 'package:flutter_test/flutter_test.dart';

import 'package:ipixel_controller/features/clock/clock_time.dart';

void main() {
  group('formatCustomTime', () {
    final now = DateTime(2026, 1, 2, 9, 5, 7);

    test('formats 24-hour tokens', () {
      expect(formatCustomTime(now, '%H:%M'), '09:05');
      expect(formatCustomTime(now, '%H:%M:%S'), '09:05:07');
    });

    test('formats 12-hour tokens with AM/PM', () {
      expect(formatCustomTime(now, '%I:%M %p'), '09:05 AM');
      expect(
        formatCustomTime(DateTime(2026, 1, 2, 13, 5), '%I:%M %p'),
        '01:05 PM',
      );
      // Midnight and noon both map to 12.
      expect(formatCustomTime(DateTime(2026, 1, 2, 0, 5), '%I'), '12');
      expect(formatCustomTime(DateTime(2026, 1, 2, 12, 5), '%I'), '12');
    });

    test('passes literals through and escapes %%', () {
      expect(formatCustomTime(now, '%H.%M'), '09.05');
      expect(formatCustomTime(now, '100%%'), '100%');
      // An unknown token is emitted verbatim.
      expect(formatCustomTime(now, '%Z'), '%Z');
      // A trailing bare percent is literal.
      expect(formatCustomTime(now, 'x%'), 'x%');
    });
  });

  group('formatSpriteClock', () {
    final now = DateTime(2026, 1, 2, 9, 5, 7);

    test('renders HH:MM without seconds', () {
      expect(formatSpriteClock(now, showSeconds: false), '09:05');
    });

    test('renders HH:MM:SS with seconds', () {
      expect(formatSpriteClock(now, showSeconds: true), '09:05:07');
    });
  });

  group('formatCountdown', () {
    final now = DateTime(2026, 1, 1);
    // 2 days, 3 hours, 4 minutes, 5 seconds ahead.
    final target = now.add(
      const Duration(days: 2, hours: 3, minutes: 4, seconds: 5),
    );

    test('days_hours_mins', () {
      expect(
        formatCountdown(now, target, CountdownFormat.daysHoursMins),
        '2d 3h 4m',
      );
    });

    test('hours_mins_secs shows the within-day hours', () {
      expect(
        formatCountdown(now, target, CountdownFormat.hoursMinsSecs),
        '3:04:05',
      );
    });

    test('days_only', () {
      expect(formatCountdown(now, target, CountdownFormat.daysOnly), '2 days');
    });

    test('full', () {
      expect(formatCountdown(now, target, CountdownFormat.full), '2d 3:04:05');
    });

    test('renders the zero state at and past the target', () {
      expect(
        formatCountdown(now, now, CountdownFormat.full),
        kCountdownZeroText,
      );
      final past = now.subtract(const Duration(seconds: 30));
      expect(
        formatCountdown(now, past, CountdownFormat.daysHoursMins),
        kCountdownZeroText,
      );
      // Never rolls over into negative components.
      expect(formatCountdown(now, past, CountdownFormat.full), 'NOW!');
    });
  });

  group('cadence selection', () {
    test('customFormatShowsSeconds detects %S', () {
      expect(customFormatShowsSeconds('%H:%M'), isFalse);
      expect(customFormatShowsSeconds('%H:%M:%S'), isTrue);
      expect(customFormatShowsSeconds('%I:%M %p'), isFalse);
    });

    test('countdownShowsSeconds is true only for seconds-bearing formats', () {
      expect(countdownShowsSeconds(CountdownFormat.hoursMinsSecs), isTrue);
      expect(countdownShowsSeconds(CountdownFormat.full), isTrue);
      expect(countdownShowsSeconds(CountdownFormat.daysHoursMins), isFalse);
      expect(countdownShowsSeconds(CountdownFormat.daysOnly), isFalse);
    });
  });

  group('nextClockTickDelay', () {
    test('per-second aligns to the next whole second', () {
      final now = DateTime(2026, 1, 1, 0, 0, 30, 250);
      expect(
        nextClockTickDelay(now, perSecond: true),
        const Duration(milliseconds: 750),
      );
    });

    test('per-minute aligns to the next whole minute', () {
      final now = DateTime(2026, 1, 1, 0, 0, 10);
      expect(
        nextClockTickDelay(now, perSecond: false),
        const Duration(milliseconds: 50000),
      );
    });

    test('never returns a zero or negative delay', () {
      final onSecond = DateTime(2026, 1, 1, 0, 0, 30);
      expect(
        nextClockTickDelay(onSecond, perSecond: true),
        const Duration(milliseconds: 1000),
      );
      final onMinute = DateTime(2026, 1, 1, 0, 0, 0);
      expect(
        nextClockTickDelay(onMinute, perSecond: false),
        const Duration(milliseconds: 60000),
      );
    });
  });

  group('nextCountdownTickDelay', () {
    test('per-second aligns to the remaining seconds phase', () {
      expect(
        nextCountdownTickDelay(
          const Duration(milliseconds: 5432),
          perSecond: true,
        ),
        const Duration(milliseconds: 432),
      );
    });

    test('per-minute aligns to the remaining minutes phase', () {
      expect(
        nextCountdownTickDelay(
          const Duration(milliseconds: 125000),
          perSecond: false,
        ),
        const Duration(milliseconds: 5000),
      );
    });

    test('exactly on a boundary ticks almost immediately', () {
      expect(
        nextCountdownTickDelay(
          const Duration(milliseconds: 5000),
          perSecond: true,
        ),
        const Duration(milliseconds: 1),
      );
    });

    test('past zero polls at the plain period', () {
      expect(
        nextCountdownTickDelay(Duration.zero, perSecond: true),
        const Duration(milliseconds: 1000),
      );
      expect(
        nextCountdownTickDelay(const Duration(seconds: -5), perSecond: false),
        const Duration(milliseconds: 60000),
      );
    });
  });
}
