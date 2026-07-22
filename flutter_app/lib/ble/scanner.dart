/// Scans for iPixel LED panels and exposes a live, deduped, RSSI-sorted list.
///
/// Panels advertise under a handful of name shapes (see [matchesPanelName]).
/// universal_ble's `ScanFilter` only supports name *prefixes*, but two of the
/// brand names must be matched by *substring*, so filtering happens here in Dart
/// against the raw [BleTransport.scanResults] stream rather than in the plugin.
library;

import 'dart:async';

import 'transport.dart';

/// Name prefixes that identify a panel (exact `startsWith`).
const List<String> kPanelNamePrefixes = <String>['LED_BLE_', 'LED-BLE-'];

/// Brand-name fragments that identify a panel (`contains`).
const List<String> kPanelNameContains = <String>[
  'BGLight',
  'B.K. Light',
  'BK Light',
];

/// Returns `true` when [name] looks like an iPixel panel.
///
/// Pure and side-effect free so it can be unit-tested directly. A `null` or
/// empty name never matches — unnamed advertisements are ignored.
bool matchesPanelName(String? name) {
  if (name == null || name.isEmpty) return false;
  for (final prefix in kPanelNamePrefixes) {
    if (name.startsWith(prefix)) return true;
  }
  for (final fragment in kPanelNameContains) {
    if (name.contains(fragment)) return true;
  }
  return false;
}

/// Deduplicates [results] by [BleScanResult.id] (keeping the most recent entry
/// per id) and sorts the survivors by RSSI descending (strongest first).
///
/// A `null` RSSI sorts last. Order of equal-RSSI entries is otherwise stable.
List<BleScanResult> dedupeAndSortByRssi(Iterable<BleScanResult> results) {
  final byId = <String, BleScanResult>{};
  for (final result in results) {
    // Later entries overwrite earlier ones so the freshest RSSI wins.
    byId[result.id] = result;
  }
  final sorted = byId.values.toList();
  sorted.sort((a, b) {
    final ra = a.rssi ?? -1 << 30; // nulls sort to the bottom
    final rb = b.rssi ?? -1 << 30;
    return rb.compareTo(ra);
  });
  return List.unmodifiable(sorted);
}

/// Live panel scanner over a [BleTransport].
///
/// Call [start] to begin scanning; [results] emits an updated, deduped,
/// RSSI-sorted list on every matching advertisement. Call [stop] to end the
/// scan and [dispose] to release resources.
class PanelScanner {
  PanelScanner(this._transport);

  final BleTransport _transport;

  final Map<String, BleScanResult> _seen = <String, BleScanResult>{};
  final StreamController<List<BleScanResult>> _controller =
      StreamController<List<BleScanResult>>.broadcast();
  StreamSubscription<BleScanResult>? _subscription;

  /// Emits the current sorted, deduped list of matching panels.
  Stream<List<BleScanResult>> get results => _controller.stream;

  /// Snapshot of the panels seen so far this scan.
  List<BleScanResult> get current => dedupeAndSortByRssi(_seen.values);

  /// Begins scanning. Clears any results from a previous scan.
  Future<void> start() async {
    _seen.clear();
    _subscription ??= _transport.scanResults.listen(_onResult);
    await _transport.startScan();
  }

  /// Stops the active scan. Retains the results already collected.
  Future<void> stop() async {
    await _transport.stopScan();
  }

  void _onResult(BleScanResult result) {
    if (!matchesPanelName(result.name)) return;
    _seen[result.id] = result;
    if (!_controller.isClosed) {
      _controller.add(dedupeAndSortByRssi(_seen.values));
    }
  }

  /// Stops the scan and closes the results stream.
  Future<void> dispose() async {
    await _subscription?.cancel();
    _subscription = null;
    await _controller.close();
  }
}
