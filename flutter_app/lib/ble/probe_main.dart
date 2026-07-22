// A standalone verification entrypoint for the BLE transport.
//
// Run with:  flutter run -d macos -t lib/ble/probe_main.dart
//
// On launch it scans ~10 s for a matching panel. If one is found it connects,
// runs the handshake, sends a hard-coded 64x16 test PNG, and logs every NOTIFY
// frame as hex to the console. If no panel is found (e.g. it is powered off)
// that is reported and is NOT treated as a failure. A denied Bluetooth
// permission IS a loud failure (means the macOS entitlements are wrong).
//
// ignore_for_file: avoid_print
library;

import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:image/image.dart' as img;
import 'package:ipixel_controller/render/panel_image.dart';

import 'device_session.dart';
import 'scanner.dart';
import 'transport.dart';
import 'universal_ble_transport.dart';

void main() {
  runApp(const ProbeApp());
}

String _hex(Uint8List bytes) =>
    bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join(' ');

/// Builds a simple, visually obvious 64x16 test frame: teal background with a
/// white border and a magenta diagonal.
Uint8List _buildTestPng() {
  final canvas = newCanvas(bgColor: '#004d4d');
  final white = img.ColorRgb8(255, 255, 255);
  final magenta = img.ColorRgb8(255, 0, 255);
  img.drawRect(
    canvas,
    x1: 0,
    y1: 0,
    x2: panelWidth - 1,
    y2: panelHeight - 1,
    color: white,
  );
  for (var i = 0; i < panelHeight; i++) {
    canvas.setPixel(i, i, magenta);
    canvas.setPixel(panelWidth - 1 - i, i, magenta);
  }
  return encodePanelPng(canvas);
}

class ProbeApp extends StatefulWidget {
  const ProbeApp({super.key});

  @override
  State<ProbeApp> createState() => _ProbeAppState();
}

class _ProbeAppState extends State<ProbeApp> {
  final List<String> _log = <String>[];
  String _status = 'starting…';
  DeviceSession? _session;
  PanelScanner? _scanner;
  StreamSubscription<Uint8List>? _notifyTap;

  @override
  void initState() {
    super.initState();
    unawaited(_run());
  }

  void _report(String message) {
    print('[probe] $message');
    if (!mounted) return;
    setState(() {
      _status = message;
      _log.add(message);
    });
  }

  Future<void> _run() async {
    final transport = UniversalBleTransport();

    // Never hang silently: on macOS the first BLE call blocks until the system
    // Bluetooth permission dialog is answered, so cap the wait and report.
    final availability = await transport.availability().timeout(
      const Duration(seconds: 8),
      onTimeout: () => BleAvailability.unknown,
    );
    _report('adapter: ${availability.name}');
    if (availability == BleAvailability.unknown) {
      _report(
        'adapter state undetermined — likely waiting on the macOS Bluetooth '
        'permission prompt (grant it, then relaunch)',
      );
    }
    if (availability == BleAvailability.unauthorized ||
        availability == BleAvailability.unsupported) {
      _report(
        'FATAL: Bluetooth ${availability.name} — check macOS entitlements '
        '(com.apple.security.device.bluetooth) and NSBluetoothAlwaysUsageDescription',
      );
      return;
    }

    final scanner = PanelScanner(transport);
    _scanner = scanner;
    final found = Completer<BleScanResult>();
    final sub = scanner.results.listen((results) {
      if (results.isNotEmpty && !found.isCompleted) {
        found.complete(results.first);
      }
    });

    _report('scanning up to 10 s…');
    try {
      await scanner.start();
    } on Object catch (error) {
      _report('FATAL: startScan failed: $error — likely a permission problem');
      await sub.cancel();
      return;
    }

    BleScanResult? panel;
    try {
      panel = await found.future.timeout(const Duration(seconds: 10));
    } on TimeoutException {
      panel = null;
    }
    await sub.cancel();
    await scanner.stop();

    if (panel == null) {
      _report('no panel found during scan (panel may be off) — this is OK');
      return;
    }
    _report('found ${panel.name} (${panel.id}) rssi=${panel.rssi}');

    final session = DeviceSession(transport: transport);
    _session = session;

    // Tap the raw notify stream so we log every frame, including acks the
    // session consumes internally.
    _notifyTap = transport
        .notifications(panel.id, kNotifyCharacteristicUuid)
        .listen((frame) => _report('notify <- ${_hex(frame)}'));

    try {
      _report('connecting + handshake…');
      await session.connect(panel.id);
      _report('ready (mtu=${session.mtu})');

      _report('sending test PNG…');
      await session.sendImage(_buildTestPng());
      _report('test PNG acked — panel should show the pattern');
    } on Object catch (error) {
      _report('connect/send failed: $error');
    }
  }

  @override
  void dispose() {
    unawaited(_notifyTap?.cancel());
    unawaited(_scanner?.dispose());
    unawaited(_session?.dispose());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'BLE Probe',
      theme: ThemeData.dark(useMaterial3: true),
      home: Scaffold(
        appBar: AppBar(title: const Text('iPixel BLE Probe')),
        body: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(_status, style: Theme.of(context).textTheme.titleMedium),
              const Divider(),
              Expanded(
                child: ListView.builder(
                  itemCount: _log.length,
                  itemBuilder: (context, i) => Text(
                    _log[i],
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 12,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
