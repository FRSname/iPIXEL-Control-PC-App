import 'package:flutter_test/flutter_test.dart';
import 'package:ipixel_controller/ble/session_guard.dart';

void main() {
  group('SessionGuard trip behaviour', () {
    test('trips after 2 consecutive failures', () {
      final guard = SessionGuard();
      addTearDown(guard.dispose);

      expect(guard.recordFailure('no ack'), isFalse);
      expect(guard.consecutiveFailures, 1);
      expect(guard.isTripped, isFalse);

      expect(guard.recordFailure('no ack'), isTrue);
      expect(guard.isTripped, isTrue);
    });

    test('a success resets the consecutive-failure counter', () {
      final guard = SessionGuard();
      addTearDown(guard.dispose);

      guard.recordFailure('timeout');
      guard.recordSuccess();

      expect(guard.consecutiveFailures, 0);
      expect(guard.isTripped, isFalse);
      // Next single failure must not trip again.
      expect(guard.recordFailure('timeout'), isFalse);
    });
  });

  group('SessionGuard error coalescing', () {
    test(
      'coalesces identical errors within the window, re-emits after',
      () async {
        var now = DateTime(2020);
        final guard = SessionGuard(
          maxConsecutiveFailures: 100, // don't trip during this test
          coalesceWindow: const Duration(seconds: 1),
          clock: () => now,
        );
        addTearDown(guard.dispose);

        final emitted = <String>[];
        guard.errors.listen(emitted.add);

        guard.recordFailure('no ack'); // emit
        now = now.add(const Duration(milliseconds: 500));
        guard.recordFailure('no ack'); // within window -> coalesced
        now = now.add(const Duration(seconds: 2));
        guard.recordFailure('no ack'); // outside window -> emit

        await pumpEventQueue();
        expect(emitted, <String>['no ack', 'no ack']);
      },
    );

    test(
      'a sustained identical-error burst re-emits once per window',
      () async {
        var now = DateTime(2020);
        final guard = SessionGuard(
          maxConsecutiveFailures: 1000, // don't trip during this test
          coalesceWindow: const Duration(seconds: 1),
          clock: () => now,
        );
        addTearDown(guard.dispose);

        final emitted = <String>[];
        guard.errors.listen(emitted.add);

        // Same error every 100 ms across 2.5 s.
        for (var i = 0; i < 25; i++) {
          guard.recordFailure('x');
          now = now.add(const Duration(milliseconds: 100));
        }

        await pumpEventQueue();
        // Anchored to first-of-run: emits at t=0, t=1000ms, t=2000ms.
        expect(emitted, <String>['x', 'x', 'x']);
      },
    );

    test('different error strings are each emitted', () async {
      final guard = SessionGuard(maxConsecutiveFailures: 100);
      addTearDown(guard.dispose);

      final emitted = <String>[];
      guard.errors.listen(emitted.add);

      guard.recordFailure('a');
      guard.recordFailure('b');

      await pumpEventQueue();
      expect(emitted, <String>['a', 'b']);
    });
  });
}
