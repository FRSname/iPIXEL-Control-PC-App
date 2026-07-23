/// Riverpod wiring for the display layer.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:ipixel_controller/ble/providers.dart';

import 'sprite_sender.dart';

/// The sink every [SpriteSender] writes frames to: the connected device
/// session's `sendImage`.
///
/// A one-line seam so feature pages depend on an [ImageSink] typedef rather than
/// the concrete [DeviceSession], and widget tests override it with a recorder
/// instead of standing up the whole BLE stack.
final panelImageSinkProvider = Provider<ImageSink>((ref) {
  final session = ref.watch(deviceSessionProvider);
  return session.sendImage;
});
