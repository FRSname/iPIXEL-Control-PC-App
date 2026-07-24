import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ipixel_controller/display/display_task.dart';

/// Records its lifecycle so tests can assert start/stop ordering.
class _FakeTask implements DisplayTask {
  _FakeTask({this.startError, this.stopError});

  final Object? startError;
  final Object? stopError;
  int startCount = 0;
  int stopCount = 0;
  bool get started => startCount > 0;
  bool get stopped => stopCount > 0;

  @override
  Future<void> start() async {
    startCount++;
    if (startError != null) throw startError!;
  }

  @override
  Future<void> stop() async {
    stopCount++;
    if (stopError != null) throw stopError!;
  }
}

/// A task whose stop() blocks on an external gate — lets a test hold the slot
/// mid-teardown so later run() calls pile up behind it.
class _GatedStopTask implements DisplayTask {
  _GatedStopTask(this._gate);

  final Future<void> _gate;
  int startCount = 0;
  int stopCount = 0;
  bool get started => startCount > 0;
  bool get stopped => stopCount > 0;

  @override
  Future<void> start() async => startCount++;

  @override
  Future<void> stop() async {
    stopCount++;
    await _gate;
  }
}

void main() {
  late ProviderContainer container;
  late ActiveDisplayTaskController controller;

  setUp(() {
    container = ProviderContainer();
    controller = container.read(activeDisplayTaskProvider.notifier);
  });

  tearDown(() => container.dispose());

  test('run starts the task and marks the slot active', () async {
    final task = _FakeTask();

    await controller.run(task);

    expect(task.started, isTrue);
    expect(container.read(activeDisplayTaskProvider), isTrue);
  });

  test('starting task B stops task A (exclusivity)', () async {
    final taskA = _FakeTask();
    final taskB = _FakeTask();

    await controller.run(taskA);
    await controller.run(taskB);

    expect(taskA.stopped, isTrue, reason: 'A must be stopped when B starts');
    expect(taskB.started, isTrue);
    expect(container.read(activeDisplayTaskProvider), isTrue);
  });

  test('previous task is stopped before the new one starts', () async {
    final order = <String>[];
    final taskA = _OrderingTask('A', order);
    final taskB = _OrderingTask('B', order);

    await controller.run(taskA);
    await controller.run(taskB);

    expect(order, <String>['A.start', 'A.stop', 'B.start']);
  });

  test('overlapping run() calls never orphan a task', () async {
    // taskA's stop() is gated so two more run() calls pile up behind the first
    // restart while it is still tearing A down — the exact shape a burst of
    // clock control changes produces. Unserialized, runC would read the same
    // stale `_current` (A) as runB, so B would be installed then overwritten by
    // C without ever being stopped: a leaked, still-ticking task.
    final gate = Completer<void>();
    final taskA = _GatedStopTask(gate.future);
    final taskB = _FakeTask();
    final taskC = _FakeTask();

    await controller.run(taskA);

    final runB = controller.run(taskB);
    final runC = controller.run(taskC);

    gate.complete(); // release A's stop()
    await runB;
    await runC;

    expect(taskA.stopped, isTrue);
    expect(taskB.stopped, isTrue, reason: 'B must be stopped, not orphaned');
    expect(taskC.started, isTrue);
    expect(taskC.stopped, isFalse, reason: 'C is the final active task');
    expect(container.read(activeDisplayTaskProvider), isTrue);
  });

  test('clear stops and empties the slot', () async {
    final task = _FakeTask();
    await controller.run(task);

    await controller.clear();

    expect(task.stopped, isTrue);
    expect(container.read(activeDisplayTaskProvider), isFalse);
  });

  test('clear on an empty slot is a no-op', () async {
    await controller.clear();
    expect(container.read(activeDisplayTaskProvider), isFalse);
  });

  test('a task that fails to start leaves the slot empty', () async {
    final task = _FakeTask(startError: Exception('boom'));

    await expectLater(controller.run(task), throwsException);

    expect(container.read(activeDisplayTaskProvider), isFalse);
  });

  test('disposing the container stops the active task (onDispose)', () async {
    final localContainer = ProviderContainer();
    final localController = localContainer.read(
      activeDisplayTaskProvider.notifier,
    );
    final task = _FakeTask();
    await localController.run(task);
    expect(task.stopped, isFalse);

    localContainer.dispose();
    // onDispose fires task.stop() fire-and-forget; let the microtask drain.
    await Future<void>.delayed(Duration.zero);

    expect(task.stopCount, 1, reason: 'onDispose must stop the live task');
  });

  test('run proceeds when a previous task throws from stop()', () async {
    final bad = _FakeTask(stopError: Exception('teardown boom'));
    final next = _FakeTask();

    await controller.run(bad);
    await controller.run(next);

    expect(next.started, isTrue, reason: 'a broken stop() must not strand run');
    expect(container.read(activeDisplayTaskProvider), isTrue);
  });

  test('re-running the same task instance does not stop it', () async {
    final task = _FakeTask();
    await controller.run(task);
    await controller.run(task);

    expect(task.stopCount, 0);
    expect(task.startCount, 2);
  });

  test(
    'updateScrollSpeed forwards to a speed-controllable active task',
    () async {
      final task = _SpeedFakeTask();
      await controller.run(task);

      controller.updateScrollSpeed(80);

      expect(task.lastSpeed, 80);
    },
  );

  test(
    'updateScrollSpeed is a no-op for a task without speed control',
    () async {
      final task = _FakeTask();
      await controller.run(task);

      // Must not throw when the active task is not a ScrollSpeedControl.
      controller.updateScrollSpeed(80);

      expect(task.started, isTrue);
    },
  );

  test('updateScrollSpeed is a no-op on an empty slot', () {
    // No task installed: this must simply do nothing.
    controller.updateScrollSpeed(80);

    expect(container.read(activeDisplayTaskProvider), isFalse);
  });
}

/// A task that also exposes live speed control, to prove the controller forwards
/// [ActiveDisplayTaskController.updateScrollSpeed] to a scrolling task.
class _SpeedFakeTask implements DisplayTask, ScrollSpeedControl {
  int? lastSpeed;

  @override
  Future<void> start() async {}

  @override
  Future<void> stop() async {}

  @override
  void updateSpeed(int speed) => lastSpeed = speed;
}

class _OrderingTask implements DisplayTask {
  _OrderingTask(this.name, this.log);

  final String name;
  final List<String> log;

  @override
  Future<void> start() async => log.add('$name.start');

  @override
  Future<void> stop() async => log.add('$name.stop');
}
