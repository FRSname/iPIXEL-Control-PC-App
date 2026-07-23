/// The single file permitted to import `package:universal_ble`.
///
/// Every other module in `lib/ble/` and every feature page depends on the
/// [BleTransport] interface, so the app is insulated from universal_ble's API
/// churn and can be unit-tested against a hand-written fake.
library;

import 'dart:typed_data';

import 'package:universal_ble/universal_ble.dart';

import 'transport.dart';

/// [BleTransport] implemented on top of universal_ble 2.1.0.
///
/// Thin translation layer: it maps universal_ble's static API and models onto
/// the framework-agnostic types in `transport.dart`. It holds no protocol
/// knowledge — that lives in [DeviceSession].
class UniversalBleTransport implements BleTransport {
  UniversalBleTransport();

  @override
  Future<BleAvailability> availability() async {
    final state = await UniversalBle.getBluetoothAvailabilityState();
    return switch (state) {
      AvailabilityState.unknown => BleAvailability.unknown,
      AvailabilityState.resetting => BleAvailability.resetting,
      AvailabilityState.unsupported => BleAvailability.unsupported,
      AvailabilityState.unauthorized => BleAvailability.unauthorized,
      AvailabilityState.poweredOff => BleAvailability.poweredOff,
      AvailabilityState.poweredOn => BleAvailability.poweredOn,
    };
  }

  @override
  Future<bool> hasPermissions({bool withAndroidFineLocation = false}) =>
      UniversalBle.hasPermissions(
        withAndroidFineLocation: withAndroidFineLocation,
      );

  @override
  Future<void> requestPermissions({bool withAndroidFineLocation = false}) =>
      UniversalBle.requestPermissions(
        withAndroidFineLocation: withAndroidFineLocation,
      );

  @override
  Stream<BleScanResult> get scanResults => UniversalBle.scanStream.map(
    (device) => BleScanResult(
      id: device.deviceId,
      name: device.name,
      rssi: device.rssi,
    ),
  );

  @override
  Future<void> startScan() => UniversalBle.startScan();

  @override
  Future<void> stopScan() => UniversalBle.stopScan();

  @override
  Future<void> connect(String deviceId, {Duration? timeout}) =>
      UniversalBle.connect(deviceId, timeout: timeout);

  @override
  Future<void> disconnect(String deviceId) => UniversalBle.disconnect(deviceId);

  @override
  Stream<bool> connectionState(String deviceId) =>
      UniversalBle.connectionStream(deviceId);

  @override
  Future<List<BleServiceInfo>> discoverServices(String deviceId) async {
    final services = await UniversalBle.discoverServices(deviceId);
    return services
        .map(
          (service) => BleServiceInfo(
            uuid: service.uuid,
            characteristics: service.characteristics
                .map(
                  (characteristic) => BleCharacteristicInfo(
                    uuid: characteristic.uuid,
                    canNotify: characteristic.properties.contains(
                      CharacteristicProperty.notify,
                    ),
                    canWrite:
                        characteristic.properties.contains(
                          CharacteristicProperty.write,
                        ) ||
                        characteristic.properties.contains(
                          CharacteristicProperty.writeWithoutResponse,
                        ),
                  ),
                )
                .toList(growable: false),
          ),
        )
        .toList(growable: false);
  }

  @override
  Future<void> subscribeNotifications(
    String deviceId,
    String service,
    String characteristic,
  ) => UniversalBle.subscribeNotifications(deviceId, service, characteristic);

  @override
  Stream<Uint8List> notifications(String deviceId, String characteristic) =>
      UniversalBle.characteristicValueStream(deviceId, characteristic);

  @override
  Future<void> writeWithResponse(
    String deviceId,
    String service,
    String characteristic,
    Uint8List value,
  ) => UniversalBle.write(deviceId, service, characteristic, value);

  @override
  Future<int> requestMtu(String deviceId, int expectedMtu) =>
      UniversalBle.requestMtu(deviceId, expectedMtu);
}
