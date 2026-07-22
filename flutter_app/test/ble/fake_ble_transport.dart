import 'dart:async';
import 'dart:typed_data';

import 'package:ipixel_controller/ble/device_session.dart';
import 'package:ipixel_controller/ble/transport.dart';

/// Hand-written [BleTransport] fake with scripted NOTIFY frames.
///
/// It records the order of every operation in [calls] and every written payload
/// in [writes], and can auto-emit protocol acks so [DeviceSession] tests run
/// without a real panel. Frames can also be pushed manually via [emit].
class FakeBleTransport implements BleTransport {
  FakeBleTransport({
    this.mtu = 247,
    this.availabilityState = BleAvailability.poweredOn,
    this.autoAckHandshake = true,
    this.autoAckGeneric = true,
    this.autoAckSendImageFinal = false,
    this.responseDelay = Duration.zero,
    this.mtuThrows = false,
    this.omitWriteCharacteristic = false,
    this.omitNotifyCharacteristic = false,
  });

  int mtu;
  BleAvailability availabilityState;

  /// Emit a generic ack in response to the handshake write.
  bool autoAckHandshake;

  /// Emit a generic ack in response to brightness/power writes.
  bool autoAckGeneric;

  /// Emit a send_image final ack in response to the first send_image chunk.
  bool autoAckSendImageFinal;

  Duration responseDelay;

  /// When true, [requestMtu] throws (exercises the connect fallback path).
  bool mtuThrows;

  /// When true, [discoverServices] omits the fa02 write characteristic.
  bool omitWriteCharacteristic;

  /// When true, [discoverServices] omits the fa03 notify characteristic.
  bool omitNotifyCharacteristic;

  /// Optional hook awaited inside [writeWithResponse] after the write is
  /// recorded. Lets a test inject a concurrent teardown mid-send.
  Future<void> Function(Uint8List value)? afterWrite;

  final List<String> calls = <String>[];
  final List<Uint8List> writes = <Uint8List>[];

  final StreamController<BleScanResult> _scan =
      StreamController<BleScanResult>.broadcast();
  final StreamController<Uint8List> _notify =
      StreamController<Uint8List>.broadcast();
  final StreamController<bool> _conn = StreamController<bool>.broadcast();

  /// Ack shapes.
  static final Uint8List handshakeAck = Uint8List.fromList(<int>[
    0x0b,
    0x00,
    0x01,
    0x80,
    0x00,
    0x00,
    0x00,
    0x00,
  ]);
  static final Uint8List genericAck = Uint8List.fromList(<int>[
    0x05,
    0x00,
    0x07,
    0x00,
    0x01,
  ]);
  static final Uint8List finalAck = Uint8List.fromList(<int>[
    0x05,
    0x00,
    0x07,
    0x00,
    0x03,
  ]);

  /// Push a NOTIFY frame to subscribers.
  void emit(List<int> frame) => _notify.add(Uint8List.fromList(frame));

  /// Push a scan advertisement to subscribers.
  void emitScan(BleScanResult result) => _scan.add(result);

  @override
  Future<BleAvailability> availability() async => availabilityState;

  @override
  Stream<BleScanResult> get scanResults => _scan.stream;

  @override
  Future<void> startScan() async => calls.add('startScan');

  @override
  Future<void> stopScan() async => calls.add('stopScan');

  @override
  Future<void> connect(String deviceId, {Duration? timeout}) async =>
      calls.add('connect');

  @override
  Future<void> disconnect(String deviceId) async => calls.add('disconnect');

  @override
  Stream<bool> connectionState(String deviceId) => _conn.stream;

  @override
  Future<List<BleServiceInfo>> discoverServices(String deviceId) async {
    calls.add('discoverServices');
    return <BleServiceInfo>[
      BleServiceInfo(
        uuid: '0000fa00-0000-1000-8000-00805f9b34fb',
        characteristics: <BleCharacteristicInfo>[
          if (!omitWriteCharacteristic)
            const BleCharacteristicInfo(
              uuid: kWriteCharacteristicUuid,
              canNotify: false,
              canWrite: true,
            ),
          if (!omitNotifyCharacteristic)
            const BleCharacteristicInfo(
              uuid: kNotifyCharacteristicUuid,
              canNotify: true,
              canWrite: false,
            ),
        ],
      ),
    ];
  }

  @override
  Future<void> subscribeNotifications(
    String deviceId,
    String service,
    String characteristic,
  ) async => calls.add('subscribe');

  @override
  Stream<Uint8List> notifications(String deviceId, String characteristic) =>
      _notify.stream;

  @override
  Future<void> writeWithResponse(
    String deviceId,
    String service,
    String characteristic,
    Uint8List value,
  ) async {
    calls.add('write');
    writes.add(value);

    final isHandshake = value.length >= 4 && value[0] == 8 && value[3] == 0x80;
    final isSendImageStart =
        value.length >= 5 &&
        value[2] == 0x02 &&
        value[3] == 0x00 &&
        value[4] == 0x00;
    final isBrightness = value.length >= 3 && value[0] == 5 && value[2] == 4;
    final isPower = value.length >= 3 && value[0] == 5 && value[2] == 7;

    if (isHandshake && autoAckHandshake) {
      _scheduleEmit(handshakeAck);
    } else if (isSendImageStart && autoAckSendImageFinal) {
      _scheduleEmit(finalAck);
    } else if ((isBrightness || isPower) && autoAckGeneric) {
      _scheduleEmit(genericAck);
    }

    final hook = afterWrite;
    if (hook != null) await hook(value);
  }

  void _scheduleEmit(Uint8List frame) {
    Future<void>.delayed(responseDelay, () {
      if (!_notify.isClosed) _notify.add(frame);
    });
  }

  @override
  Future<int> requestMtu(String deviceId, int expectedMtu) async {
    calls.add('requestMtu');
    if (mtuThrows) {
      throw Exception('requestMtu not supported');
    }
    return mtu;
  }

  Future<void> dispose() async {
    await _scan.close();
    await _notify.close();
    await _conn.close();
  }
}
