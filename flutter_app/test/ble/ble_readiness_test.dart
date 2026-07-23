// waitForAdapterReady gates a scan on the adapter reaching poweredOn, turning
// the macOS "scan-before-ready" crash into a clean wait-or-message.

import 'package:flutter_test/flutter_test.dart';

import 'package:ipixel_controller/ble/ble_readiness.dart';
import 'package:ipixel_controller/ble/transport.dart';

import 'fake_ble_transport.dart';

void main() {
  test('returns immediately when the adapter is already powered on', () async {
    final transport = FakeBleTransport(
      availabilityState: BleAvailability.poweredOn,
    );
    addTearDown(transport.dispose);

    expect(await waitForAdapterReady(transport), BleAvailability.poweredOn);
  });

  test('returns immediately when there is no adapter (unsupported)', () async {
    final transport = FakeBleTransport(
      availabilityState: BleAvailability.unsupported,
    );
    addTearDown(transport.dispose);

    expect(await waitForAdapterReady(transport), BleAvailability.unsupported);
  });

  test(
    'waits through a transient state, then resolves when powered on',
    () async {
      final transport = FakeBleTransport(
        availabilityState: BleAvailability.poweredOff,
      );
      addTearDown(transport.dispose);

      final future = waitForAdapterReady(transport);
      // Let the gate subscribe (availability() is async) before the adapter flips.
      await Future<void>.delayed(Duration.zero);
      transport.emitAvailability(BleAvailability.poweredOn);

      expect(await future, BleAvailability.poweredOn);
    },
  );

  test('times out to the last-seen state when it never powers on', () async {
    final transport = FakeBleTransport(
      availabilityState: BleAvailability.unauthorized,
    );
    addTearDown(transport.dispose);

    final result = await waitForAdapterReady(
      transport,
      timeout: const Duration(milliseconds: 30),
    );

    expect(result, BleAvailability.unauthorized);
  });
}
