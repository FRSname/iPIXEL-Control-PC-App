/// Runtime BLE-permission gate with an Android rationale dialog.
///
/// Android 12+ requires the user to grant `BLUETOOTH_SCAN` / `BLUETOOTH_CONNECT`
/// at runtime; older Android needs location. This shows a short rationale first
/// (why the app needs Bluetooth, and that it is not used for location), then
/// asks the transport to request the OS permissions. Desktop and Apple platforms
/// have no runtime BLE permission to request from a scan trigger, so the gate
/// passes through immediately.
///
/// All permission work goes through [BleTransport.requestPermissions], keeping
/// the "no feature imports universal_ble" invariant intact.
library;

import 'dart:async';
import 'dart:developer';
import 'dart:io' show Platform;

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';

import 'transport.dart';

const String _logName = 'BlePermissions';

/// Whether the current host is Android (and not the web build).
///
/// Extracted so widget tests can force the Android branch on a macOS/Linux test
/// host — the `dart:io` `Platform` check is otherwise untestable off-device.
bool defaultIsAndroidHost() => !kIsWeb && Platform.isAndroid;

/// Ensures BLE permissions before a scan. Returns `true` when scanning may
/// proceed, `false` when the user declined the rationale or the OS denied.
///
/// On non-Android platforms this returns `true` without prompting. On Android it
/// first asks the transport whether permission is already granted; if so it
/// skips straight to a (no-op) [BleTransport.requestPermissions] without showing
/// the rationale again. Otherwise it shows a rationale (unless [showRationale]
/// is `false`) and then requests permissions; a denial surfaces a [SnackBar] and
/// returns `false`.
///
/// [isAndroid] overrides the host check for testing; production callers omit it.
Future<bool> ensureBlePermissions(
  BuildContext context,
  BleTransport transport, {
  bool showRationale = true,
  bool Function()? isAndroid,
}) async {
  final onAndroid = (isAndroid ?? defaultIsAndroidHost)();
  if (!onAndroid) return true;

  // Skip the rationale when the OS already granted access — re-explaining every
  // scan is noise. requestPermissions below is a no-op in that case.
  final alreadyGranted = await transport.hasPermissions();
  if (!alreadyGranted && showRationale) {
    // The permission query is async; bail if the host went away meanwhile.
    if (!context.mounted) return false;
    final proceed = await _showRationale(context);
    if (proceed != true) return false;
  }

  try {
    await transport.requestPermissions();
    return true;
  } on Exception catch (error, stack) {
    log(
      'BLE permission request denied',
      name: _logName,
      error: error,
      stackTrace: stack,
    );
    if (context.mounted) {
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(
          const SnackBar(
            content: Text(
              'Bluetooth permission is needed to find your panel. '
              'Enable it in Settings and try again.',
            ),
          ),
        );
    }
    return false;
  }
}

Future<bool?> _showRationale(BuildContext context) {
  return showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      icon: const Icon(Icons.bluetooth_searching),
      title: const Text('Allow Bluetooth'),
      content: const Text(
        'iPixel Controller uses Bluetooth to find and control your LED panel. '
        'It never uses Bluetooth to determine your location.',
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: const Text('Not now'),
        ),
        FilledButton(
          onPressed: () => Navigator.of(context).pop(true),
          child: const Text('Continue'),
        ),
      ],
    ),
  );
}
