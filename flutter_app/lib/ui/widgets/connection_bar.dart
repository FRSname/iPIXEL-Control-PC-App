/// Scan / connect / disconnect strip bound to the S4 BLE providers.
///
/// Reads [connectionStatusProvider] for live status and drives the
/// [PanelScanner] + [DeviceSession] for the actual operations. All error
/// surfacing is non-modal: connect failures go to a [SnackBar], the guard's
/// coalesced [lastErrorProvider] stream is surfaced by the shell.
///
/// Error handling contract: only [Exception]s are caught here. [Error]
/// subtypes (e.g. a re-entrant `connect()` [StateError]) indicate a programming
/// bug and are allowed to propagate. Known failure types from the BLE layer are
/// mapped to short, user-facing messages; anything unexpected surfaces a
/// generic message and is logged via `dart:developer`.
library;

import 'dart:async';
import 'dart:developer';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:ipixel_controller/ble/device_session.dart';
import 'package:ipixel_controller/ble/providers.dart';
import 'package:ipixel_controller/ble/scanner.dart';
import 'package:ipixel_controller/ble/transport.dart';

/// Logging channel used for unexpected BLE UI failures.
const String _logName = 'ConnectionBar';

class ConnectionBar extends ConsumerStatefulWidget {
  const ConnectionBar({super.key});

  @override
  ConsumerState<ConnectionBar> createState() => _ConnectionBarState();
}

class _ConnectionBarState extends ConsumerState<ConnectionBar> {
  bool _scanning = false;

  /// Set synchronously the instant a chip is tapped so a rapid second tap (or a
  /// rebuild) can't launch a second `connect()` before the first `await`.
  bool _connecting = false;

  /// Captured when a scan starts so [dispose] can stop it without touching
  /// `ref` — reading providers in a ConsumerState dispose is unsafe here.
  PanelScanner? _scanner;

  Future<void> _startScan() async {
    final scanner = ref.read(panelScannerProvider);
    _scanner = scanner;
    setState(() => _scanning = true);
    try {
      await scanner.start();
    } on Exception catch (error, stack) {
      log(
        'Starting scan failed',
        name: _logName,
        error: error,
        stackTrace: stack,
      );
      _showError('Could not start scanning. Check that Bluetooth is on.');
      if (mounted) setState(() => _scanning = false);
    }
  }

  /// Stops the active scan and clears the scanning UI. Bound to the Stop button.
  Future<void> _stopScan() async {
    await _stopScanQuietly();
    if (mounted) setState(() => _scanning = false);
  }

  /// Stops the transport scan without touching widget state. Uses the captured
  /// [_scanner] (set when the scan started) so it is safe to call from
  /// [dispose] — reading providers via `ref` in dispose is unsafe here.
  Future<void> _stopScanQuietly() async {
    final scanner = _scanner;
    if (scanner == null) return;
    try {
      await scanner.stop();
    } on Exception catch (error, stack) {
      // Stopping a scan that already ended is harmless, but never silent.
      log(
        'Stopping scan failed',
        name: _logName,
        error: error,
        stackTrace: stack,
      );
    }
  }

  Future<void> _connect(BleScanResult result) async {
    // Guard against a double-tap racing two connects: flip the flag and hide the
    // chip row synchronously, before the first await, rather than waiting on the
    // async stop-scan round-trip.
    if (_connecting) return;
    setState(() {
      _connecting = true;
      _scanning = false;
    });
    unawaited(_stopScanQuietly());

    final session = ref.read(deviceSessionProvider);
    var connected = false;
    try {
      await session.connect(result.id);
      connected = true;
    } on Exception catch (error, stack) {
      _showError(_friendlyConnectMessage(error, stack));
    } finally {
      if (mounted) setState(() => _connecting = false);
    }

    // Persist the last-used device best-effort: a slow/failed disk write must
    // never hold the connected UI in its "connecting" state.
    if (connected) {
      unawaited(_persistLastDevice(result.id));
    }
  }

  Future<void> _persistLastDevice(String deviceId) async {
    try {
      await ref.read(lastDeviceIdProvider.notifier).setDeviceId(deviceId);
    } on Exception catch (error, stack) {
      log(
        'Persisting last device failed',
        name: _logName,
        error: error,
        stackTrace: stack,
      );
    }
  }

  Future<void> _disconnect() async {
    try {
      await ref.read(deviceSessionProvider).disconnect();
    } on Exception catch (error, stack) {
      log('Disconnect failed', name: _logName, error: error, stackTrace: stack);
      _showError('Could not disconnect cleanly.');
    }
  }

  /// Maps a known BLE failure to a short, user-friendly message. Unexpected
  /// exceptions are logged and get a generic message so we never leak internals
  /// like "Bad state: connect() called while connecting" into the UI.
  String _friendlyConnectMessage(Object error, StackTrace stack) {
    switch (error) {
      case AckTimeoutException():
        return 'The panel didn’t respond. Move closer and try again.';
      case CharacteristicNotFoundException():
        return 'That device isn’t a compatible panel.';
      case TimeoutException():
        return 'Connecting timed out. Try again.';
      default:
        log(
          'Unexpected connect failure',
          name: _logName,
          error: error,
          stackTrace: stack,
        );
        return 'Could not connect to the panel.';
    }
  }

  void _showError(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  void dispose() {
    // Stop any in-progress scan so it doesn't outlive the widget, using the
    // captured [_scanner] (reading providers via `ref` in dispose is unsafe).
    if (_scanning) {
      unawaited(_stopScanQuietly());
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final statusAsync = ref.watch(connectionStatusProvider);
    final status = statusAsync.value ?? BleConnectionStatus.disconnected;

    return Material(
      color: Theme.of(context).colorScheme.surface,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Row(
          children: [
            _StatusIndicator(status: status),
            const SizedBox(width: 12),
            Expanded(
              child: _ConnectionCentre(
                scanning: _scanning,
                status: status,
                onSelected: _connect,
              ),
            ),
            const SizedBox(width: 12),
            _ConnectionAction(
              scanning: _scanning,
              connecting: _connecting,
              status: status,
              onScan: _startScan,
              onStop: _stopScan,
              onDisconnect: _disconnect,
            ),
          ],
        ),
      ),
    );
  }
}

/// Coloured dot + short status word describing the live connection state.
///
/// The word stays visible even while the scan-result chips occupy the centre,
/// and the pair is wrapped in [Semantics] so assistive tech announces state.
class _StatusIndicator extends StatelessWidget {
  const _StatusIndicator({required this.status});

  final BleConnectionStatus status;

  @override
  Widget build(BuildContext context) {
    final (color, word) = switch (status) {
      BleConnectionStatus.ready => (const Color(0xFF2DD4BF), 'Ready'),
      BleConnectionStatus.connecting => (const Color(0xFFFACC15), 'Connecting'),
      BleConnectionStatus.disconnected => (const Color(0xFF6B7280), 'Offline'),
    };
    return Semantics(
      label: 'Connection status: $word',
      container: true,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 12,
            height: 12,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 8),
          ExcludeSemantics(
            child: Text(word, style: Theme.of(context).textTheme.labelMedium),
          ),
        ],
      ),
    );
  }
}

/// Centre region: the live scan-result chips while scanning, otherwise a short
/// status sentence.
class _ConnectionCentre extends StatelessWidget {
  const _ConnectionCentre({
    required this.scanning,
    required this.status,
    required this.onSelected,
  });

  final bool scanning;
  final BleConnectionStatus status;
  final void Function(BleScanResult) onSelected;

  @override
  Widget build(BuildContext context) {
    if (scanning) {
      return _ScanResults(onSelected: onSelected);
    }
    return Text(
      switch (status) {
        BleConnectionStatus.ready => 'Panel connected',
        BleConnectionStatus.connecting => 'Connecting…',
        BleConnectionStatus.disconnected => 'No panel connected',
      },
      style: Theme.of(context).textTheme.bodyMedium,
      overflow: TextOverflow.ellipsis,
    );
  }
}

/// Trailing action button: Stop while scanning, a spinner while connecting,
/// Disconnect when ready, Scan when idle.
class _ConnectionAction extends StatelessWidget {
  const _ConnectionAction({
    required this.scanning,
    required this.connecting,
    required this.status,
    required this.onScan,
    required this.onStop,
    required this.onDisconnect,
  });

  final bool scanning;
  final bool connecting;
  final BleConnectionStatus status;
  final VoidCallback onScan;
  final VoidCallback onStop;
  final VoidCallback onDisconnect;

  @override
  Widget build(BuildContext context) {
    if (scanning) {
      return TextButton.icon(
        onPressed: onStop,
        icon: const Icon(Icons.stop),
        label: const Text('Stop'),
      );
    }
    // Cover the gap between tapping a chip and the status stream flipping to
    // `connecting`: the local flag keeps the spinner up so the Scan button can't
    // reappear mid-connect.
    if (connecting || status == BleConnectionStatus.connecting) {
      return const Padding(
        padding: EdgeInsets.symmetric(horizontal: 16),
        child: SizedBox(
          width: 18,
          height: 18,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      );
    }
    return switch (status) {
      BleConnectionStatus.ready => FilledButton.tonalIcon(
        onPressed: onDisconnect,
        icon: const Icon(Icons.bluetooth_disabled),
        label: const Text('Disconnect'),
      ),
      BleConnectionStatus.disconnected => FilledButton.icon(
        onPressed: onScan,
        icon: const Icon(Icons.bluetooth_searching),
        label: const Text('Scan'),
      ),
      // Unreachable: the connecting case is handled above, but the switch stays
      // exhaustive over the enum.
      BleConnectionStatus.connecting => const SizedBox.shrink(),
    };
  }
}

/// Live, RSSI-sorted list of discovered panels rendered as tappable chips.
class _ScanResults extends ConsumerWidget {
  const _ScanResults({required this.onSelected});

  final void Function(BleScanResult) onSelected;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final scanner = ref.watch(panelScannerProvider);
    return StreamBuilder<List<BleScanResult>>(
      stream: scanner.results,
      initialData: scanner.current,
      builder: (context, snapshot) {
        final results = snapshot.data ?? const <BleScanResult>[];
        if (results.isEmpty) {
          return Row(
            children: [
              const SizedBox(
                width: 14,
                height: 14,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
              const SizedBox(width: 8),
              Text(
                'Scanning for panels…',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ],
          );
        }
        return SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              for (final result in results)
                Padding(
                  key: ValueKey<String>(result.id),
                  padding: const EdgeInsets.only(right: 8),
                  child: ActionChip(
                    avatar: const Icon(Icons.cast, size: 18),
                    label: Text(result.name ?? result.id),
                    onPressed: () => onSelected(result),
                  ),
                ),
            ],
          ),
        );
      },
    );
  }
}
