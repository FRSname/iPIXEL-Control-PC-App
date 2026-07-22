/// Owns a single connected panel: the connect handshake, the notify pump, the
/// serialized command queue and the failure guard.
///
/// This is the layer feature pages drive. It knows the iPixel protocol (via
/// `lib/protocol/`) but nothing about universal_ble — it talks only to a
/// [BleTransport], so it is fully unit-testable against a fake.
///
/// ## Connect order is a hard invariant
///
/// `connect → requestMtu → discover → resolve write(fa02)/notify(fa03) →
/// subscribe → send handshake → await ack → ready`. The panel ACKs `send_image`
/// frames even before the handshake but never *renders* them, so the handshake
/// is not optional and the session is not marked ready until its ack arrives.
///
/// ## One command in flight
///
/// `sendImage` / `setBrightness` / `setPower` are serialized through a
/// Future-chain: exactly one is ever in flight, the rest queue. This replaces
/// the Python app's thread-per-send race that could blank the panel.
///
/// ## Teardown cooperates with in-flight commands
///
/// [disconnect] intentionally runs outside the command queue (it can be called
/// from within a failing command via the guard). It never crashes a concurrent
/// command: every command snapshots the device id + service uuids into locals at
/// the start ([_requireSession]) and re-checks [currentStatus] between chunk
/// writes, so a teardown that nulls the session fields mid-flight produces a
/// clean [StateError] instead of a null-check `TypeError`.
library;

import 'dart:async';
import 'dart:typed_data';

import 'package:ipixel_controller/protocol/ack.dart';
import 'package:ipixel_controller/protocol/frames.dart';

import 'session_guard.dart';
import 'transport.dart';

/// GATT write characteristic (panel accepts commands here).
const String kWriteCharacteristicUuid = '0000fa02-0000-1000-8000-00805f9b34fb';

/// GATT notify characteristic (panel emits acks here).
const String kNotifyCharacteristicUuid = '0000fa03-0000-1000-8000-00805f9b34fb';

/// The largest GATT write chunk, matching pypixelcolor's 244-byte default
/// (MTU 247 − 3-byte ATT header).
const int kMaxChunkSize = 244;

/// Minimum sane MTU (default ATT MTU) used as a floor if negotiation returns
/// something smaller or the query fails.
const int kMinMtu = 23;

/// Lifecycle of a [DeviceSession].
enum BleConnectionStatus { disconnected, connecting, ready }

/// Raised when a command is not acknowledged within its timeout.
class AckTimeoutException implements Exception {
  const AckTimeoutException(this.message);
  final String message;
  @override
  String toString() => 'AckTimeoutException: $message';
}

/// Raised when the connect flow cannot find the write/notify characteristics.
class CharacteristicNotFoundException implements Exception {
  const CharacteristicNotFoundException(this.message);
  final String message;
  @override
  String toString() => 'CharacteristicNotFoundException: $message';
}

/// Immutable snapshot of the fields a command needs, captured atomically at the
/// start of the command so a concurrent teardown cannot null them mid-flight.
typedef _SessionContext = ({String deviceId, String writeService});

/// A connected (or connecting) panel session.
class DeviceSession {
  DeviceSession({
    required this.transport,
    SessionGuard? guard,
    this.connectTimeout = const Duration(seconds: 30),
    this.discoveryTimeout = const Duration(seconds: 10),
    this.handshakeTimeout = const Duration(seconds: 5),
    this.ackTimeout = const Duration(seconds: 5),
    this.sendImageTimeout = const Duration(seconds: 5),
    DateTime Function()? now,
  }) : _guard = guard ?? SessionGuard(clock: now);

  /// The injected BLE transport (the abstraction, never universal_ble directly).
  final BleTransport transport;

  /// Timeout for the underlying transport connect.
  final Duration connectTimeout;

  /// Timeout for service discovery and notify subscription.
  final Duration discoveryTimeout;

  /// Timeout awaiting the handshake ack during [connect].
  final Duration handshakeTimeout;

  /// Timeout awaiting a generic ack for brightness/power commands.
  final Duration ackTimeout;

  /// Timeout awaiting the send_image final ack.
  final Duration sendImageTimeout;

  final SessionGuard _guard;

  final StreamController<BleConnectionStatus> _statusController =
      StreamController<BleConnectionStatus>.broadcast();

  BleConnectionStatus _status = BleConnectionStatus.disconnected;
  String? _deviceId;
  String? _writeServiceUuid;
  int _mtu = 247;

  StreamSubscription<Uint8List>? _notifySub;

  // Pending ack waiters. Only one of each is ever set at a time because commands
  // are serialized. Any notify frame resolves a generic-ack wait; the send_image
  // final ack is tracked separately.
  Completer<void>? _pendingAck;
  Completer<void>? _pendingFinalAck;

  // Future-chain enforcing a single in-flight command.
  Future<void> _queue = Future<void>.value();

  /// Lifecycle stream seeded with the current value so a late subscriber sees
  /// the present state immediately rather than sitting in a loading state.
  ///
  /// Implemented with a per-listener [StreamController] rather than an `async*`
  /// generator on purpose: a generator's `yield*` delegation does not subscribe
  /// to the underlying broadcast controller until ~a full event-loop turn after
  /// `listen()`, so any transition in that window is silently dropped. Here
  /// [StreamController.onListen] runs synchronously and (1) subscribes to the
  /// source first (buffering), (2) emits the current seed, (3) flushes the
  /// buffer — so no transition can slip through the gap and the seed is never
  /// duplicated.
  Stream<BleConnectionStatus> get statusChanges {
    final controller = StreamController<BleConnectionStatus>();
    StreamSubscription<BleConnectionStatus>? source;
    final buffer = <BleConnectionStatus>[];
    var seeded = false;

    controller.onListen = () {
      // 1. Subscribe first: nothing added to the source after this instant is
      //    lost. Anything that arrives before the seed is buffered.
      source = _statusController.stream.listen(
        (status) {
          if (seeded) {
            controller.add(status);
          } else {
            buffer.add(status);
          }
        },
        onError: controller.addError,
        onDone: controller.close,
      );
      // 2. Emit the current state synchronously as the seed.
      controller.add(_status);
      seeded = true;
      // 3. Flush anything that raced in between (1) and (2).
      for (final status in buffer) {
        controller.add(status);
      }
      buffer.clear();
    };
    controller.onCancel = () async {
      await source?.cancel();
      source = null;
    };
    return controller.stream;
  }

  /// Raw (unseeded) lifecycle stream. Prefer [statusChanges] for UI binding.
  Stream<BleConnectionStatus> get status => _statusController.stream;

  /// Current lifecycle state.
  BleConnectionStatus get currentStatus => _status;

  /// Non-modal error stream from the failure guard.
  ///
  /// This is an *event* stream: it has no meaningful "current value", so late
  /// subscribers only observe errors emitted after they subscribe (the intended
  /// behaviour for a transient status strip / toast).
  Stream<String> get errors => _guard.errors;

  /// The negotiated MTU (or the requested default before/if negotiation fails).
  int get mtu => _mtu;

  /// The connected device id, or `null` when disconnected.
  String? get deviceId => _deviceId;

  /// Exposed for tests: the failure guard.
  SessionGuard get guard => _guard;

  /// Runs the full connect + handshake flow for [deviceId].
  ///
  /// Rejects re-entrant calls (throws [StateError] if not currently
  /// disconnected). Marks the session [BleConnectionStatus.ready] only after the
  /// handshake ack arrives. On any failure — [Exception] or [Error] — the
  /// session is torn down and reset to [BleConnectionStatus.disconnected] and
  /// the original error propagates.
  Future<void> connect(String deviceId) async {
    if (_status != BleConnectionStatus.disconnected) {
      throw StateError('connect() called while ${_status.name}');
    }
    _setStatus(BleConnectionStatus.connecting);

    var succeeded = false;
    try {
      await transport.connect(deviceId, timeout: connectTimeout);
      _deviceId = deviceId;

      // MTU: request 247; respect whatever the platform actually negotiates.
      // On Apple this returns the OS value; on Android it is a real request.
      int negotiated;
      try {
        negotiated = await transport.requestMtu(deviceId, 247);
      } on Exception {
        negotiated = 247; // best-effort: fall back to the protocol default
      }
      _mtu = negotiated < kMinMtu ? kMinMtu : negotiated;

      final services = await transport
          .discoverServices(deviceId)
          .timeout(discoveryTimeout);
      final resolved = _resolveCharacteristics(services);
      _writeServiceUuid = resolved.writeService;

      await transport
          .subscribeNotifications(
            deviceId,
            resolved.notifyService,
            kNotifyCharacteristicUuid,
          )
          .timeout(discoveryTimeout);
      _notifySub = transport
          .notifications(deviceId, kNotifyCharacteristicUuid)
          .listen(_onNotify);

      // Handshake must be sent AFTER subscribing so its ack is observed.
      final ack = _armAck();
      await transport.writeWithResponse(
        deviceId,
        resolved.writeService,
        kWriteCharacteristicUuid,
        buildHandshake(DateTime.now()),
      );
      await _awaitAck(ack, handshakeTimeout, 'handshake');

      _guard.recordSuccess();
      _setStatus(BleConnectionStatus.ready);
      succeeded = true;
    } finally {
      // Cleanup for BOTH Exceptions and Errors; the original throwable still
      // propagates (Errors loudly), we just never leave a half-open session.
      if (!succeeded) {
        await _teardown();
        _setStatus(BleConnectionStatus.disconnected);
      }
    }
  }

  /// Disconnects and tears the session down.
  ///
  /// Runs outside the command queue on purpose (see class docs). Best-effort:
  /// a transport [Exception] on disconnect is swallowed, but an [Error]
  /// propagates loudly.
  Future<void> disconnect() async {
    final id = _deviceId;
    await _teardown();
    if (id != null) {
      try {
        await transport.disconnect(id);
      } on Exception {
        // Disconnect is best-effort; the session is already torn down.
      }
    }
    _setStatus(BleConnectionStatus.disconnected);
  }

  /// Sends a fully-encoded panel PNG, chunked to the negotiated MTU, and awaits
  /// the send_image FINAL ack. Queued behind any in-flight command.
  Future<void> sendImage(Uint8List png) {
    return _enqueue(() async {
      final session = _requireSession();
      final chunkSize = kMaxChunkSize < (_mtu - 3) ? kMaxChunkSize : (_mtu - 3);
      final frames = buildSendImageFrames(png, chunkSize: chunkSize);

      final finalAck = Completer<void>();
      _pendingFinalAck = finalAck;
      try {
        for (final chunk in frames) {
          // Cooperate with a concurrent teardown: bail cleanly instead of
          // writing to a dead transport (and instead of crashing on a nulled
          // service uuid — the uuid is captured in `session`).
          if (_status != BleConnectionStatus.ready) {
            throw StateError('session disconnected during sendImage');
          }
          await transport.writeWithResponse(
            session.deviceId,
            session.writeService,
            kWriteCharacteristicUuid,
            chunk,
          );
        }
        await finalAck.future.timeout(
          sendImageTimeout,
          onTimeout: () =>
              throw const AckTimeoutException('send_image final ack timed out'),
        );
        _guard.recordSuccess();
      } on Exception catch (error) {
        // Only Exceptions raised while still ready are ack-failures. A
        // concurrent teardown (e.g. disconnect during the final-ack wait, which
        // otherwise surfaces as AckTimeoutException) is surfaced as a clean
        // StateError the guard ignores, rather than being misclassified.
        if (_status != BleConnectionStatus.ready) {
          throw StateError('session disconnected during sendImage');
        }
        await _handleCommandFailure(error);
        rethrow;
      } finally {
        if (identical(_pendingFinalAck, finalAck)) _pendingFinalAck = null;
      }
    });
  }

  /// Sets panel brightness (0-100) and awaits a generic ack.
  Future<void> setBrightness(int percent) {
    return _enqueue(
      () => _writeAndAwaitAck(buildBrightness(percent), 'setBrightness'),
    );
  }

  /// Powers the panel on/off and awaits a generic ack.
  Future<void> setPower({required bool on}) {
    return _enqueue(() => _writeAndAwaitAck(buildPower(on), 'setPower'));
  }

  /// Releases the session's streams. Call once when the owner is disposed.
  Future<void> dispose() async {
    await _teardown();
    await _statusController.close();
    await _guard.dispose();
  }

  // --- internals -----------------------------------------------------------

  Future<void> _writeAndAwaitAck(Uint8List payload, String label) async {
    final session = _requireSession();
    final ack = _armAck();
    try {
      await transport.writeWithResponse(
        session.deviceId,
        session.writeService,
        kWriteCharacteristicUuid,
        payload,
      );
      await _awaitAck(ack, ackTimeout, label);
      _guard.recordSuccess();
    } on Exception catch (error) {
      // A concurrent teardown is not an ack-failure: surface it as a clean
      // StateError the guard ignores, rather than misclassifying the timeout
      // that results from the ack completer being cleared by _teardown.
      if (_status != BleConnectionStatus.ready) {
        throw StateError('session disconnected during $label');
      }
      await _handleCommandFailure(error);
      rethrow;
    }
  }

  /// Records a command failure with the guard and disconnects if it trips.
  Future<void> _handleCommandFailure(Object error) async {
    final tripped = _guard.recordFailure(error.toString());
    if (tripped) {
      await disconnect();
    }
  }

  Completer<void> _armAck() {
    final completer = Completer<void>();
    _pendingAck = completer;
    return completer;
  }

  Future<void> _awaitAck(
    Completer<void> ack,
    Duration timeout,
    String label,
  ) async {
    try {
      await ack.future.timeout(
        timeout,
        onTimeout: () => throw AckTimeoutException('$label ack timed out'),
      );
    } finally {
      if (identical(_pendingAck, ack)) _pendingAck = null;
    }
  }

  void _onNotify(Uint8List frame) {
    if (frame.isEmpty) return;
    final finalAck = _pendingFinalAck;
    if (finalAck != null &&
        !finalAck.isCompleted &&
        isSendImageFinalAck(frame)) {
      finalAck.complete();
    }
    final ack = _pendingAck;
    if (ack != null && !ack.isCompleted && isAck(frame)) {
      ack.complete();
    }
  }

  /// Resolves the service uuids that own the write (fa02) and notify (fa03)
  /// characteristics. Throws [CharacteristicNotFoundException] if either is
  /// absent. Returns the resolved pair so callers avoid `!` on the fields.
  ({String writeService, String notifyService}) _resolveCharacteristics(
    List<BleServiceInfo> services,
  ) {
    String? writeService;
    String? notifyService;
    for (final service in services) {
      for (final characteristic in service.characteristics) {
        if (_uuidEquals(characteristic.uuid, kWriteCharacteristicUuid)) {
          writeService = service.uuid;
        }
        if (_uuidEquals(characteristic.uuid, kNotifyCharacteristicUuid)) {
          notifyService = service.uuid;
        }
      }
    }
    if (writeService == null) {
      throw const CharacteristicNotFoundException(
        'write characteristic 0000fa02 not found',
      );
    }
    if (notifyService == null) {
      throw const CharacteristicNotFoundException(
        'notify characteristic 0000fa03 not found',
      );
    }
    return (writeService: writeService, notifyService: notifyService);
  }

  /// Case-insensitive UUID comparison; tolerates 16-bit vs 128-bit forms by
  /// comparing the significant `0000XXXX` segment.
  bool _uuidEquals(String a, String b) {
    final na = a.toLowerCase();
    final nb = b.toLowerCase();
    return na == nb || na.endsWith(nb) || nb.endsWith(na);
  }

  /// Snapshots the fields a command needs, atomically, at command start.
  ///
  /// Throws [StateError] if the session is not ready — including the case where
  /// a concurrent teardown has nulled the fields — so commands fail cleanly
  /// rather than dereferencing null.
  _SessionContext _requireSession() {
    final id = _deviceId;
    final writeService = _writeServiceUuid;
    if (_status != BleConnectionStatus.ready ||
        id == null ||
        writeService == null) {
      throw StateError('Session is not ready (status: ${_status.name})');
    }
    return (deviceId: id, writeService: writeService);
  }

  Future<T> _enqueue<T>(Future<T> Function() action) {
    final completer = Completer<T>();
    // Forward ANY throwable (Exception or Error) from the queued action to this
    // command's own future; the queue itself must never break.
    _queue = _queue.then((_) async {
      try {
        completer.complete(await action());
      } on Object catch (error, stack) {
        completer.completeError(error, stack);
      }
    });
    return completer.future;
  }

  void _setStatus(BleConnectionStatus status) {
    _status = status;
    if (!_statusController.isClosed) _statusController.add(status);
  }

  Future<void> _teardown() async {
    await _notifySub?.cancel();
    _notifySub = null;
    _pendingAck = null;
    _pendingFinalAck = null;
    _deviceId = null;
    _writeServiceUuid = null;
  }
}
