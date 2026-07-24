/// Framework-agnostic BLE transport contract.
///
/// This is the ONLY surface feature code and the [DeviceSession] talk to. No
/// file outside `universal_ble_transport.dart` imports `package:universal_ble`
/// directly — the whole point of this layer is that swapping the BLE backend
/// (or faking it in tests) touches exactly one implementation file.
///
/// The shape is deliberately thin and modelled on what universal_ble 2.1.0
/// actually offers (see `universal_ble_transport.dart`). In particular there is
/// a single [requestMtu] rather than separate query/request calls: universal_ble
/// unifies those — on Android it negotiates, on Apple/Windows/Linux it returns
/// the OS-negotiated value.
library;

import 'dart:typed_data';

/// Bluetooth adapter availability, mirroring universal_ble's `AvailabilityState`
/// without leaking the plugin type across the abstraction boundary.
enum BleAvailability {
  unknown,
  resetting,
  unsupported,

  /// The app lacks Bluetooth permission. On macOS this means the entitlement
  /// or `NSBluetoothAlwaysUsageDescription` is missing/denied.
  unauthorized,
  poweredOff,
  poweredOn,
}

/// A single advertising result observed during a scan.
///
/// [id] is an opaque platform identifier: a MAC on Android/Windows/Linux and a
/// CoreBluetooth UUID on Apple platforms. Never parse or validate it as a MAC.
class BleScanResult {
  const BleScanResult({
    required this.id,
    required this.name,
    required this.rssi,
  });

  final String id;

  /// Advertised device name, or `null` when the peripheral advertised none.
  final String? name;

  /// Received signal strength in dBm, or `null` when unavailable.
  final int? rssi;

  @override
  String toString() => 'BleScanResult(id: $id, name: $name, rssi: $rssi)';
}

/// A GATT characteristic discovered on a peripheral.
class BleCharacteristicInfo {
  const BleCharacteristicInfo({
    required this.uuid,
    required this.canNotify,
    required this.canWrite,
  });

  final String uuid;
  final bool canNotify;
  final bool canWrite;
}

/// A GATT service discovered on a peripheral, with its characteristics.
class BleServiceInfo {
  const BleServiceInfo({required this.uuid, required this.characteristics});

  final String uuid;
  final List<BleCharacteristicInfo> characteristics;
}

/// The minimal BLE operations the panel protocol needs.
///
/// Implementations must:
///  * deliver every scan advertisement to [scanResults] (a broadcast stream);
///  * deliver every NOTIFY frame for a subscribed characteristic to the stream
///    returned by [notifications];
///  * perform writes with response and complete the returned future only once
///    the peer has acknowledged the GATT write.
abstract interface class BleTransport {
  /// Current adapter availability. Used to surface permission failures clearly.
  Future<BleAvailability> availability();

  /// Broadcast stream of adapter-availability transitions.
  ///
  /// Used to wait for the adapter to reach [BleAvailability.poweredOn] before a
  /// scan. On macOS/iOS the first subscription initialises CoreBluetooth and
  /// triggers the system Bluetooth-permission prompt; calling [startScan] before
  /// the adapter is powered on there crashes the app, so callers gate on this
  /// first (see `ble_readiness.dart`).
  Stream<BleAvailability> get availabilityChanges;

  /// Whether the runtime BLE permissions are already granted.
  ///
  /// Lets callers skip a "why we need Bluetooth" rationale when the OS has
  /// already granted access. On Android this queries the live grant state; on
  /// Windows, Linux and Web there is no runtime BLE permission so it returns
  /// `true`. [withAndroidFineLocation] mirrors [requestPermissions].
  Future<bool> hasPermissions({bool withAndroidFineLocation = false});

  /// Requests the runtime BLE permissions the platform needs before scanning.
  ///
  /// On Android 12+ this prompts for `BLUETOOTH_SCAN`/`BLUETOOTH_CONNECT`; on
  /// Android ≤11 for location. Completes when permissions are granted and throws
  /// on denial. On Windows, Linux, macOS and Web there are no runtime BLE
  /// permissions and this completes immediately. If permissions are already
  /// granted it completes as a no-op.
  ///
  /// [withAndroidFineLocation] requests `ACCESS_FINE_LOCATION` on Android 12+
  /// (only needed if scan results are used to derive location — this app does
  /// not, so callers pass `false`).
  Future<void> requestPermissions({bool withAndroidFineLocation = false});

  /// Broadcast stream of scan advertisements. Emits only while a scan is active.
  Stream<BleScanResult> get scanResults;

  Future<void> startScan();
  Future<void> stopScan();

  /// Connects to [deviceId]. Completes once connected; throws on failure.
  Future<void> connect(String deviceId, {Duration? timeout});

  Future<void> disconnect(String deviceId);

  /// Broadcast stream of connection-state transitions for [deviceId]
  /// (`true` == connected).
  Stream<bool> connectionState(String deviceId);

  /// Discovers services + characteristics on a connected [deviceId].
  Future<List<BleServiceInfo>> discoverServices(String deviceId);

  /// Enables NOTIFY updates for [characteristic] on [service].
  Future<void> subscribeNotifications(
    String deviceId,
    String service,
    String characteristic,
  );

  /// Broadcast stream of NOTIFY payloads for [characteristic] on [deviceId].
  Stream<Uint8List> notifications(String deviceId, String characteristic);

  /// Writes [value] to [characteristic] with response, completing on ack.
  Future<void> writeWithResponse(
    String deviceId,
    String service,
    String characteristic,
    Uint8List value,
  );

  /// Requests/queries the connection MTU, returning the effective value.
  ///
  /// On Android this is a genuine request (best-effort, OS-capped). On Apple,
  /// Windows and Linux the MTU is OS-managed and this returns the negotiated
  /// value. Callers must treat the return value as authoritative and derive the
  /// GATT write chunk size from it (`mtu - 3`).
  Future<int> requestMtu(String deviceId, int expectedMtu);
}
