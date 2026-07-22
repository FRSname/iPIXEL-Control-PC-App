/// Failure tracking for a [DeviceSession].
///
/// Two behaviours are load-bearing (ported from the Python app's disconnect
/// guard, see project CLAUDE.md):
///
///  * After [maxConsecutiveFailures] consecutive timeout / no-ack failures the
///    guard "trips" — [recordFailure] returns `true` — and the session must
///    disconnect. A single success resets the counter.
///  * Errors are surfaced non-modally on the [errors] stream. Identical error
///    strings within [coalesceWindow] are emitted only once, so a failing
///    playlist doesn't spam the UI with the same message.
library;

import 'dart:async';

/// Tracks consecutive command failures and coalesces duplicate error strings.
class SessionGuard {
  SessionGuard({
    this.maxConsecutiveFailures = 2,
    this.coalesceWindow = const Duration(seconds: 1),
    DateTime Function()? clock,
  }) : _clock = clock ?? DateTime.now;

  /// Consecutive failures required to trip the guard.
  final int maxConsecutiveFailures;

  /// Window within which an identical error string is emitted only once.
  final Duration coalesceWindow;

  final DateTime Function() _clock;

  final StreamController<String> _errors = StreamController<String>.broadcast();

  int _consecutiveFailures = 0;
  bool _tripped = false;
  String? _lastError;
  DateTime? _lastErrorAt;

  /// Non-modal stream of error messages (coalesced).
  Stream<String> get errors => _errors.stream;

  /// Number of failures since the last success.
  int get consecutiveFailures => _consecutiveFailures;

  /// Whether the guard has tripped (and the session should be/has been dropped).
  bool get isTripped => _tripped;

  /// Records a command failure with [message].
  ///
  /// Emits [message] on [errors] (subject to coalescing) and returns `true`
  /// when this failure trips the guard, signalling the caller to disconnect.
  bool recordFailure(String message) {
    _emit(message);
    _consecutiveFailures++;
    if (_consecutiveFailures >= maxConsecutiveFailures) {
      _tripped = true;
      return true;
    }
    return false;
  }

  /// Resets the consecutive-failure counter after a successful command.
  void recordSuccess() {
    _consecutiveFailures = 0;
    _tripped = false;
  }

  void _emit(String message) {
    final now = _clock();
    final lastAt = _lastErrorAt;
    final isDuplicate =
        message == _lastError &&
        lastAt != null &&
        now.difference(lastAt) < coalesceWindow;
    if (isDuplicate) {
      // Anchor the window to the FIRST occurrence of a duplicate run: do not
      // slide _lastErrorAt, or a sustained identical-error burst would suppress
      // itself forever. Once the window elapses the next duplicate emits again
      // and re-anchors below.
      return;
    }
    _lastError = message;
    _lastErrorAt = now;
    if (!_errors.isClosed) _errors.add(message);
  }

  /// Closes the error stream.
  Future<void> dispose() => _errors.close();
}
