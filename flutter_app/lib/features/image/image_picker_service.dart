/// Picks an image file, choosing the platform-appropriate plugin.
///
/// Desktop (macOS / Windows / Linux) uses `file_selector`; mobile (Android /
/// iOS) uses `image_picker`. Both are wrapped behind [PanelImagePicker] so
/// feature code depends on a small interface and widget tests override the
/// [panelImagePickerProvider] with a fake instead of driving real file dialogs.
library;

import 'package:file_selector/file_selector.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

/// An image the user picked: its raw bytes and original file name.
///
/// The name's extension is the signal the page uses to decide whether to treat
/// the bytes as an animated GIF or a static image.
class PickedImage {
  const PickedImage({required this.bytes, required this.name});

  final Uint8List bytes;
  final String name;
}

/// Picks a single image from the user's device.
abstract interface class PanelImagePicker {
  /// Returns the picked image, or `null` if the user cancelled.
  Future<PickedImage?> pickImage();
}

/// File extensions offered in the desktop file dialog.
const List<String> _kImageExtensions = <String>[
  'png',
  'jpg',
  'jpeg',
  'gif',
  'bmp',
  'webp',
];

/// The default [PanelImagePicker]: `file_selector` on desktop, `image_picker`
/// on mobile.
class PlatformImagePicker implements PanelImagePicker {
  const PlatformImagePicker();

  bool get _isDesktop {
    if (kIsWeb) return false;
    return defaultTargetPlatform == TargetPlatform.macOS ||
        defaultTargetPlatform == TargetPlatform.windows ||
        defaultTargetPlatform == TargetPlatform.linux;
  }

  @override
  Future<PickedImage?> pickImage() async {
    if (_isDesktop) {
      final file = await openFile(
        acceptedTypeGroups: const <XTypeGroup>[
          XTypeGroup(label: 'Images', extensions: _kImageExtensions),
        ],
      );
      if (file == null) return null;
      return PickedImage(bytes: await file.readAsBytes(), name: file.name);
    }
    final file = await ImagePicker().pickImage(source: ImageSource.gallery);
    if (file == null) return null;
    return PickedImage(bytes: await file.readAsBytes(), name: file.name);
  }
}

/// The app's image picker. Overridden in tests with a fake.
final panelImagePickerProvider = Provider<PanelImagePicker>(
  (ref) => const PlatformImagePicker(),
);
