/// The app-wide "one active display task" slot.
///
/// Anything that drives the panel over time — a scrolling sprite (S7), a GIF
/// loop (S8), a ticking clock (S9) — is modelled as a [DisplayTask]. At most one
/// task is ever active app-wide: handing a new task to
/// [ActiveDisplayTaskController.run] stops the previous one first, so two loops
/// can never race the BLE command queue. This is the structural version of the
/// Python app's `_stop_active_display_tasks`.
library;

import 'dart:async';
import 'dart:developer';

import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Logging channel for display-slot lifecycle failures.
const String _logName = 'ActiveDisplayTask';

/// A unit of panel output with a lifecycle: [start] begins driving the panel,
/// [stop] halts it and releases any timers.
///
/// Implementations must make [stop] idempotent — the slot may call it after the
/// task already finished (a static single-shot send) or after a failure.
abstract interface class DisplayTask {
  /// Begins driving the panel. For an animated task this arms an internal timer
  /// and returns once the first frame has been dispatched; for a one-shot task
  /// it sends a single frame and completes.
  ///
  /// May throw to surface a render/setup failure to the caller (the page shows
  /// it); a throw leaves the slot empty (see [ActiveDisplayTaskController.run]).
  Future<void> start();

  /// Halts the task and releases its resources.
  ///
  /// Contract:
  ///  * Safe to call more than once (idempotent).
  ///  * Completes only after any in-flight send resolves — once stop() returns,
  ///    the task guarantees no further frame will be delivered to the panel.
  ///  * Must never throw. A recoverable send failure encountered while stopping
  ///    is logged and swallowed; implementations must not surface it.
  Future<void> stop();
}

/// A capability mixed into [DisplayTask]s whose playback rate can be retuned
/// live, without a restart.
///
/// The scrolling sprite task implements this so the Text page's speed slider can
/// take effect mid-scroll: the controller forwards the new speed to the active
/// task (see [ActiveDisplayTaskController.updateScrollSpeed]) instead of tearing
/// the scroll down and restarting it from the first column.
abstract interface class ScrollSpeedControl {
  /// Retunes the per-frame scroll rate from a UI speed (1..100). The next
  /// scheduled frame uses the new rate; the current scroll offset is preserved.
  void updateSpeed(int speed);
}

/// Owns the single active [DisplayTask]. Assigning a new task disposes the old.
///
/// The watched state is a plain `bool` "is a task active" flag rather than the
/// raw [DisplayTask]: consumers may need to know *that* the panel is being
/// driven, but they must not be handed a live task whose [DisplayTask.stop]
/// they could call out of band. Lifecycle mutations stay on this notifier
/// ([run] / [clear]); the task instance is private.
class ActiveDisplayTaskController extends Notifier<bool> {
  /// The live task. Held separately from [state] because Riverpod forbids
  /// touching `state` inside `onDispose`, and because the task itself is never
  /// exposed to watchers.
  DisplayTask? _current;

  @override
  bool build() {
    ref.onDispose(() {
      final task = _current;
      if (task != null) unawaited(task.stop());
    });
    return false;
  }

  /// Stops the current task (if any), installs [task], then starts it.
  ///
  /// The previous task is stopped BEFORE the new one starts, so exclusivity
  /// holds even while [DisplayTask.start] is still running. If [start] throws,
  /// the slot is left empty and the error propagates to the caller.
  Future<void> run(DisplayTask task) async {
    final previous = _current;
    if (previous != null && !identical(previous, task)) {
      // stop() must never throw (see DisplayTask.stop contract), but guard
      // against a misbehaving impl so a broken teardown can't strand the slot.
      try {
        await previous.stop();
      } on Exception catch (error, stack) {
        log(
          'Previous display task threw from stop(); proceeding',
          name: _logName,
          error: error,
          stackTrace: stack,
        );
      }
    }
    _current = task;
    state = true;
    try {
      await task.start();
    } on Object {
      // A task that fails to start never becomes the active output.
      if (identical(_current, task)) {
        _current = null;
        state = false;
      }
      rethrow;
    }
  }

  /// Retunes the active task's scroll rate in place from a UI speed (1..100).
  ///
  /// A no-op when the slot is empty or the active task does not support live
  /// speed control (e.g. a static send). Keeps the task instance private — the
  /// page pushes a speed, it never touches the task — so the encapsulation the
  /// slot enforces elsewhere still holds.
  void updateScrollSpeed(int speed) {
    if (_current case final ScrollSpeedControl control) {
      control.updateSpeed(speed);
    }
  }

  /// Stops and clears the active task. No-op when the slot is already empty.
  Future<void> clear() async {
    final previous = _current;
    if (previous == null) return;
    _current = null;
    state = false;
    await previous.stop();
  }
}

/// The single active-display-task slot for the app. The exposed value is a
/// `bool` "active" flag; lifecycle changes go through the notifier's
/// [ActiveDisplayTaskController.run] / [ActiveDisplayTaskController.clear].
final activeDisplayTaskProvider =
    NotifierProvider<ActiveDisplayTaskController, bool>(
      ActiveDisplayTaskController.new,
    );
