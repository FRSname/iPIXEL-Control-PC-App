/// Riverpod wiring for the BLE layer.
///
/// Exposes the transport, the device session, its connection state and error
/// stream, and the persisted last-device id. Nothing here imports
/// `package:universal_ble` — the transport is injected via [bleTransportProvider]
/// so tests (and future platform swaps) override a single provider.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:ipixel_controller/config/config_store.dart';
import 'package:ipixel_controller/config/providers.dart';

import 'device_session.dart';
import 'scanner.dart';
import 'transport.dart';
import 'universal_ble_transport.dart';

/// The BLE transport. Overridden in tests with a fake.
final bleTransportProvider = Provider<BleTransport>((ref) {
  return UniversalBleTransport();
});

/// The single [PanelScanner], bound to the same transport as the session.
///
/// Wiring only — [PanelScanner] is the S4 scanner; this just exposes it to the
/// UI so the connection bar can drive scans without importing the transport.
final panelScannerProvider = Provider<PanelScanner>((ref) {
  final scanner = PanelScanner(ref.watch(bleTransportProvider));
  ref.onDispose(scanner.dispose);
  return scanner;
});

/// The single [DeviceSession] for the app, disposed with the container.
final deviceSessionProvider = Provider<DeviceSession>((ref) {
  final transport = ref.watch(bleTransportProvider);
  final session = DeviceSession(transport: transport);
  ref.onDispose(session.dispose);
  return session;
});

/// Live connection lifecycle (`disconnected` / `connecting` / `ready`).
///
/// Uses [DeviceSession.statusChanges], which is seeded with the current value,
/// so a late subscriber resolves immediately instead of hanging in
/// [AsyncLoading].
final connectionStatusProvider = StreamProvider<BleConnectionStatus>((ref) {
  final session = ref.watch(deviceSessionProvider);
  return session.statusChanges;
});

/// Non-modal, coalesced error stream to render as a status strip.
///
/// This is an event stream with no seeded value: until an error occurs the
/// provider stays in [AsyncLoading] (there is no "current error" to replay).
/// Render that loading state as "no error", i.e. an empty status strip.
final lastErrorProvider = StreamProvider<String>((ref) {
  final session = ref.watch(deviceSessionProvider);
  return session.errors;
});

/// The last successfully-used device id, persisted under
/// [ConfigStore.lastDeviceKey].
///
/// On Apple platforms this is a CoreBluetooth UUID, on Android/Windows/Linux a
/// MAC. It is stored and compared as an opaque string — never validated as a
/// MAC.
class LastDeviceController extends AsyncNotifier<String?> {
  @override
  Future<String?> build() async {
    final store = await ref.watch(configStoreProvider.future);
    final settings = await store.loadSettings();
    final value = settings[ConfigStore.lastDeviceKey];
    return value is String ? value : null;
  }

  /// Persists [deviceId] as the last-used device.
  Future<void> setDeviceId(String deviceId) async {
    final store = await ref.read(configStoreProvider.future);
    await store.updateSettings((settings) {
      settings[ConfigStore.lastDeviceKey] = deviceId;
      return settings;
    });
    state = AsyncData<String?>(deviceId);
  }
}

final lastDeviceIdProvider =
    AsyncNotifierProvider<LastDeviceController, String?>(
      LastDeviceController.new,
    );
