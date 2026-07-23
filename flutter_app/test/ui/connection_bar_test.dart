// Connection bar reflects the live connection status provider and drives the
// scan → select → connect flow against the FakeBleTransport.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ipixel_controller/ble/device_session.dart';
import 'package:ipixel_controller/ble/providers.dart';
import 'package:ipixel_controller/ble/transport.dart';
import 'package:ipixel_controller/ui/widgets/connection_bar.dart';

import '../ble/fake_ble_transport.dart';

/// In-memory stand-in for [LastDeviceController] so a successful connect never
/// reaches the disk. Real file I/O in a `testWidgets` body runs under the fake
/// async zone and never completes, which would hang the test.
class _FakeLastDevice extends LastDeviceController {
  @override
  Future<String?> build() async => null;

  @override
  Future<void> setDeviceId(String deviceId) async {}
}

/// Pumps the bar with the status provider forced to [status] (for the static
/// display tests). Uses a real transport-backed session under the hood.
Future<void> _pumpBar(WidgetTester tester, BleConnectionStatus status) async {
  final transport = FakeBleTransport();
  addTearDown(transport.dispose);

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        bleTransportProvider.overrideWithValue(transport),
        connectionStatusProvider.overrideWith((ref) => Stream.value(status)),
      ],
      child: const MaterialApp(home: Scaffold(body: ConnectionBar())),
    ),
  );
  await tester.pump();
}

/// Pumps the bar with the real session + scanner wired to [transport] and an
/// in-memory last-device notifier (a successful connect persists the id).
Future<void> _pumpLive(WidgetTester tester, FakeBleTransport transport) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        bleTransportProvider.overrideWithValue(transport),
        lastDeviceIdProvider.overrideWith(_FakeLastDevice.new),
      ],
      child: const MaterialApp(home: Scaffold(body: ConnectionBar())),
    ),
  );
  await tester.pump();
}

/// Starts a scan and emits [result] so its chip appears.
Future<void> _scan(
  WidgetTester tester,
  FakeBleTransport transport,
  BleScanResult result,
) async {
  await tester.tap(find.text('Scan'));
  await tester.pump();

  transport.emitScan(result);
  await tester.pump();
  await tester.pump();
}

/// Drives the connect chain (microtasks + the fake's timer-delayed acks) with a
/// handful of fixed-duration pumps. [pumpAndSettle] can't be used because the
/// connecting spinner animates forever and never settles.
Future<void> _settleConnect(WidgetTester tester) async {
  for (var i = 0; i < 8; i++) {
    await tester.pump(const Duration(milliseconds: 15));
  }
}

void main() {
  group('static display', () {
    testWidgets('shows Scan when disconnected', (tester) async {
      await _pumpBar(tester, BleConnectionStatus.disconnected);

      expect(find.text('Scan'), findsOneWidget);
      expect(find.text('No panel connected'), findsOneWidget);
      expect(find.text('Disconnect'), findsNothing);
    });

    testWidgets('shows Disconnect when ready', (tester) async {
      await _pumpBar(tester, BleConnectionStatus.ready);

      expect(find.text('Disconnect'), findsOneWidget);
      expect(find.text('Panel connected'), findsOneWidget);
      expect(find.text('Scan'), findsNothing);
    });

    testWidgets('shows a spinner while connecting', (tester) async {
      await _pumpBar(tester, BleConnectionStatus.connecting);

      expect(find.text('Connecting…'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('always shows a short status word (accessible)', (
      tester,
    ) async {
      await _pumpBar(tester, BleConnectionStatus.disconnected);
      expect(find.text('Offline'), findsOneWidget);
      expect(
        find.bySemanticsLabel('Connection status: Offline'),
        findsOneWidget,
      );
    });
  });

  group('scan → select → connect', () {
    const panel = BleScanResult(id: 'PANEL-1', name: 'LED_BLE_1', rssi: -40);

    testWidgets('connects through to ready and shows the panel', (
      tester,
    ) async {
      final transport = FakeBleTransport();
      addTearDown(transport.dispose);
      await _pumpLive(tester, transport);

      expect(find.text('Scan'), findsOneWidget);
      await _scan(tester, transport, panel);

      // Tapping the chip flips the local connecting flag synchronously → the
      // spinner shows and the Scan button is gone before any await resolves.
      await tester.tap(find.text('LED_BLE_1'));
      await tester.pump();
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Scan'), findsNothing);

      // Drive the handshake through to ready.
      await _settleConnect(tester);

      expect(transport.calls, contains('connect'));
      expect(find.text('Panel connected'), findsOneWidget);
      expect(find.text('Disconnect'), findsOneWidget);
    });

    testWidgets('renders each result chip under a stable ValueKey', (
      tester,
    ) async {
      final transport = FakeBleTransport();
      addTearDown(transport.dispose);
      await _pumpLive(tester, transport);

      await tester.tap(find.text('Scan'));
      await tester.pump();
      transport.emitScan(panel);
      await tester.pump();
      await tester.pump();

      expect(find.byKey(const ValueKey<String>('PANEL-1')), findsOneWidget);
    });

    testWidgets('a failed connect shows a friendly SnackBar, not internals', (
      tester,
    ) async {
      // Omitting the write characteristic makes the connect handshake fail with
      // CharacteristicNotFoundException.
      final transport = FakeBleTransport(omitWriteCharacteristic: true);
      addTearDown(transport.dispose);
      await _pumpLive(tester, transport);

      const panel2 = BleScanResult(id: 'PANEL-2', name: 'BGLight', rssi: -55);
      await _scan(tester, transport, panel2);

      await tester.tap(find.text('BGLight'));
      await tester.pump();
      await _settleConnect(tester);

      expect(
        find.text('That device isn’t a compatible panel.'),
        findsOneWidget,
      );
      // The raw exception text must never reach the UI.
      expect(
        find.textContaining('CharacteristicNotFoundException'),
        findsNothing,
      );
      expect(find.textContaining('fa02'), findsNothing);
    });

    testWidgets('stops the scan before connecting (no scan/connect race)', (
      tester,
    ) async {
      final transport = FakeBleTransport();
      addTearDown(transport.dispose);
      await _pumpLive(tester, transport);
      await _scan(tester, transport, panel);

      await tester.tap(find.text('LED_BLE_1'));
      await tester.pump();
      await _settleConnect(tester);

      // The connect path must issue stopScan and let it settle before connect,
      // so the platform BLE stack is never asked to connect from an active scan.
      final stopIndex = transport.calls.indexOf('stopScan');
      final connectIndex = transport.calls.indexOf('connect');
      expect(stopIndex, isNonNegative, reason: 'scan was stopped');
      expect(connectIndex, isNonNegative, reason: 'connect was attempted');
      expect(
        stopIndex,
        lessThan(connectIndex),
        reason: 'stopScan must precede connect',
      );
    });

    testWidgets('proceeds to connect when stopScan never completes', (
      tester,
    ) async {
      // A platform stopScan that hangs must not strand the UI in "Connecting…":
      // the connect path time-bounds the stop and proceeds anyway.
      final transport = FakeBleTransport()..stopScanHangs = true;
      addTearDown(transport.dispose);
      await _pumpLive(tester, transport);
      await _scan(tester, transport, panel);

      await tester.tap(find.text('LED_BLE_1'));
      await tester.pump();

      // Before the 2 s timeout elapses the stop is still pending, so connect
      // has not been issued yet.
      await tester.pump(const Duration(milliseconds: 500));
      expect(transport.calls, contains('stopScan'));
      expect(transport.calls, isNot(contains('connect')));

      // Pump past the 2 s stop-scan timeout, then let the handshake settle.
      await tester.pump(const Duration(seconds: 2));
      await _settleConnect(tester);

      expect(transport.calls, contains('connect'));
      expect(find.text('Panel connected'), findsOneWidget);
      expect(find.text('Disconnect'), findsOneWidget);
    });

    testWidgets('double-tapping a chip only connects once', (tester) async {
      final transport = FakeBleTransport();
      addTearDown(transport.dispose);
      await _pumpLive(tester, transport);
      await _scan(tester, transport, panel);

      // Two taps land in the same frame, before the rebuild removes the chip
      // row. The synchronous _connecting guard must swallow the second one.
      await tester.tap(find.text('LED_BLE_1'));
      await tester.tap(find.text('LED_BLE_1'));
      await tester.pump();
      await _settleConnect(tester);

      final connects = transport.calls.where((c) => c == 'connect').length;
      expect(connects, 1);
    });
  });
}
