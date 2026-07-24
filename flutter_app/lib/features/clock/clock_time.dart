/// Pure time maths for the Clock feature.
///
/// Everything here is a plain function of an injected [DateTime] — no wall
/// clock, no timers, no Flutter — so the three clock modes (sprite-clock,
/// custom format, countdown) are unit-testable without pumping real time.
///
/// The widget layer ([ClockFeaturePage]) and the ticking [DisplayTask]
/// ([ClockDisplayTask]) build their per-frame render string and their
/// self-rescheduling tick delay from these helpers.
library;

/// The three ways the Clock feature drives the panel.
enum ClockMode {
  /// Current time rendered with a clock-glyph sprite sheet (digits + colon).
  sprite('Sprite clock'),

  /// Current time rendered from a user strftime-like format string.
  custom('Custom'),

  /// Time remaining until a target, rendered as a countdown.
  countdown('Countdown');

  const ClockMode(this.label);
  final String label;
}

/// Countdown display shapes. Mirrors the Python `COUNTDOWN_FORMATS`.
enum CountdownFormat {
  daysHoursMins('Days Hours Mins'),
  hoursMinsSecs('Hours Mins Secs'),
  daysOnly('Days Only'),
  full('Full');

  const CountdownFormat(this.label);
  final String label;
}

/// Built-in strftime presets offered for [ClockMode.custom].
const List<String> kTimeFormats = <String>['%H:%M', '%H:%M:%S', '%I:%M %p'];

/// Shown once a countdown has reached (or passed) its target.
///
/// A short, unambiguous zero state — the text sprite sheet has the letters, so
/// it renders on the same pipeline as the running countdown.
const String kCountdownZeroText = 'NOW!';

/// Two-digit zero-padded decimal (`7` -> `07`).
String _two(int value) => value.toString().padLeft(2, '0');

/// Formats [now] with a small strftime subset.
///
/// Supported tokens: `%H` (24h, 2-digit), `%M` (minute), `%S` (second),
/// `%I` (12h, 01-12), `%p` (`AM`/`PM`), `%%` (a literal `%`). Any other `%x`
/// pair is emitted verbatim; all non-token characters pass through unchanged.
String formatCustomTime(DateTime now, String format) {
  final out = StringBuffer();
  for (var i = 0; i < format.length; i++) {
    final ch = format[i];
    if (ch != '%' || i + 1 >= format.length) {
      out.write(ch);
      continue;
    }
    final token = format[i + 1];
    i++;
    switch (token) {
      case 'H':
        out.write(_two(now.hour));
      case 'M':
        out.write(_two(now.minute));
      case 'S':
        out.write(_two(now.second));
      case 'I':
        final h12 = now.hour % 12;
        out.write(_two(h12 == 0 ? 12 : h12));
      case 'p':
        out.write(now.hour < 12 ? 'AM' : 'PM');
      case '%':
        out.write('%');
      default:
        out
          ..write('%')
          ..write(token);
    }
  }
  return out.toString();
}

/// Formats a sprite-clock time as `HH:MM`, or `HH:MM:SS` when [showSeconds].
///
/// Digits + colon only, so it renders with a clock-glyph sprite sheet.
String formatSpriteClock(DateTime now, {required bool showSeconds}) =>
    formatCustomTime(now, showSeconds ? '%H:%M:%S' : '%H:%M');

/// Formats the time from [now] to [target] as a countdown in [fmt].
///
/// Returns [kCountdownZeroText] once the target has been reached — the zero
/// state is a single stable string, never a negative or rolled-over value.
/// Matches the Python `_format_remaining` breakdown (hours/mins/secs are the
/// components *within* a day, not the running total).
String formatCountdown(DateTime now, DateTime target, CountdownFormat fmt) {
  final total = target.difference(now).inSeconds;
  if (total <= 0) return kCountdownZeroText;
  final days = total ~/ 86400;
  final hours = (total % 86400) ~/ 3600;
  final mins = (total % 3600) ~/ 60;
  final secs = total % 60;
  return switch (fmt) {
    CountdownFormat.daysHoursMins => '${days}d ${hours}h ${mins}m',
    CountdownFormat.hoursMinsSecs => '$hours:${_two(mins)}:${_two(secs)}',
    CountdownFormat.daysOnly => '$days days',
    CountdownFormat.full => '${days}d $hours:${_two(mins)}:${_two(secs)}',
  };
}

/// Whether the custom [format] renders a seconds field (`%S`).
bool customFormatShowsSeconds(String format) => format.contains('%S');

/// Whether a countdown [fmt] renders a seconds field.
bool countdownShowsSeconds(CountdownFormat fmt) =>
    fmt == CountdownFormat.hoursMinsSecs || fmt == CountdownFormat.full;

/// Delay until the next wall-clock boundary for sprite/custom modes.
///
/// [perSecond] aligns to the next whole second (formats showing seconds);
/// otherwise to the next whole minute — so a minute clock updates on the `:00`
/// tick instead of drifting up to a minute behind. Never returns a zero or
/// negative delay (which would spin the timer).
Duration nextClockTickDelay(DateTime now, {required bool perSecond}) {
  final ms = perSecond
      ? 1000 - now.millisecond
      : (60 - now.second) * 1000 - now.millisecond;
  return Duration(milliseconds: ms < 1 ? 1 : ms);
}

/// Delay until a countdown's displayed value next changes.
///
/// A countdown is phase-locked to its *target*, not the wall clock: the minute
/// field ticks down when the remaining time crosses a whole-minute boundary,
/// which lands on the target's second offset. Aligning to that boundary keeps a
/// minute-granularity countdown from lagging up to a minute behind. Past zero
/// (or exactly at zero) it polls at the plain period; the render string is
/// stable there so the dedupe guard suppresses any resend.
Duration nextCountdownTickDelay(Duration remaining, {required bool perSecond}) {
  final period = perSecond ? 1000 : 60000;
  final total = remaining.inMilliseconds;
  if (total <= 0) return Duration(milliseconds: period);
  final offset = total % period;
  return Duration(milliseconds: offset == 0 ? 1 : offset);
}
