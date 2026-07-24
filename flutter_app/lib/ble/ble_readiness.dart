/// Waits for the BLE adapter to become ready before a scan.
///
/// Calling [BleTransport.startScan] before the adapter is powered on crashes on
/// macOS/iOS — CoreBluetooth is still initialising and the first-launch
/// permission prompt is unresolved. Callers therefore gate a scan on
/// [waitForAdapterReady] returning [BleAvailability.poweredOn]; subscribing to
/// [BleTransport.availabilityChanges] is also what triggers the system prompt in
/// the first place, so this both arms permissions and eliminates the crash.
library;

import 'dart:async';

import 'transport.dart';

/// How long [waitForAdapterReady] waits for [BleAvailability.poweredOn].
///
/// Generous because on first launch this spans the macOS/iOS system permission
/// prompt — the user has to respond before the adapter reports powered on. Once
/// authorised, readiness resolves in well under a second, so the timeout only
/// bites when Bluetooth is off or access was denied.
const Duration kAdapterReadyTimeout = Duration(seconds: 20);

/// Resolves once the adapter is [BleAvailability.poweredOn], or with the last
/// observed state if it settles on a terminal non-ready state or the wait times
/// out.
///
/// Returns immediately when the adapter is already powered on (or definitively
/// [BleAvailability.unsupported] — there is no adapter to wait for). Otherwise it
/// watches [BleTransport.availabilityChanges]: [BleAvailability.poweredOn] wins,
/// [BleAvailability.unsupported] is terminal, and every other state
/// (unknown/resetting/unauthorized/poweredOff) is waited through up to [timeout]
/// — on macOS/iOS the first-launch prompt passes through such transient states
/// before reaching `poweredOn`, and a user may flip Bluetooth on mid-wait. On
/// timeout the most recent state is returned so the caller can show a precise
/// message. Never throws: a stream error resolves with the last seen state.
Future<BleAvailability> waitForAdapterReady(
  BleTransport transport, {
  Duration timeout = kAdapterReadyTimeout,
}) async {
  // Never throw (see the doc contract): a failed one-shot read degrades to
  // `unknown` and falls through to the stream wait, which has its own onError.
  var current = BleAvailability.unknown;
  try {
    current = await transport.availability();
  } on Exception {
    current = BleAvailability.unknown;
  }
  if (current == BleAvailability.poweredOn ||
      current == BleAvailability.unsupported) {
    return current;
  }

  final completer = Completer<BleAvailability>();
  StreamSubscription<BleAvailability>? sub;
  Timer? timer;

  void finish(BleAvailability state) {
    if (completer.isCompleted) return;
    timer?.cancel();
    unawaited(sub?.cancel());
    completer.complete(state);
  }

  sub = transport.availabilityChanges.listen((state) {
    current = state;
    if (state == BleAvailability.poweredOn ||
        state == BleAvailability.unsupported) {
      finish(state);
    }
  }, onError: (_) => finish(current));

  timer = Timer(timeout, () => finish(current));
  return completer.future;
}
