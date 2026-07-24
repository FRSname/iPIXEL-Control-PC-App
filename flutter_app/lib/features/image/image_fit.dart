/// Decodes an arbitrary picked image and fits it onto the 64x16 panel canvas.
///
/// Pure Dart on top of the `image` package and the shared [fitImage] /
/// [encodePanelPng] helpers in `render/panel_image.dart`. No `dart:ui`, so it
/// runs in plain `flutter test` VM tests and inside isolates.
library;

import 'dart:typed_data';

import 'package:image/image.dart' as img;

import 'package:ipixel_controller/render/panel_image.dart';

/// Raised when picked image bytes cannot be decoded into a usable image.
class ImageDecodeException implements Exception {
  const ImageDecodeException(this.message);
  final String message;
  @override
  String toString() => 'ImageDecodeException: $message';
}

/// Decodes [bytes], fits the image onto a [panelWidth]x[panelHeight] canvas
/// using [fit], and encodes the result to PNG.
///
/// * [PanelFit.letterbox] scales the whole image inside the panel and pads the
///   remaining space with [bgColor].
/// * [PanelFit.crop] scales the image to cover the panel and centre-crops.
///
/// Throws [ImageDecodeException] when the bytes are not a decodable image.
Uint8List fitImageToPanelPng(
  Uint8List bytes, {
  PanelFit fit = PanelFit.letterbox,
  String bgColor = '#000000',
}) {
  final decoded = _decode(bytes);
  final fitted = fitImage(decoded, fit: fit, bgColor: bgColor);
  return encodePanelPng(fitted);
}

/// Decodes [bytes] into an image, normalising every failure mode into an
/// [ImageDecodeException].
///
/// This is a trust boundary: the bytes come from an arbitrary user-picked file.
/// The `image` package's format decoders do not fully validate their input —
/// a truncated or garbled file makes them throw a raw `RangeError` mid-parse
/// rather than returning `null`. Converting both the `null` result and any
/// thrown decoder failure into one domain exception lets the page surface a
/// clean "could not read that image" message instead of crashing.
img.Image _decode(Uint8List bytes) {
  final img.Image? decoded;
  try {
    decoded = img.decodeImage(bytes);
  } on Object {
    throw const ImageDecodeException('Could not read that image file.');
  }
  if (decoded == null) {
    throw const ImageDecodeException('Could not read that image file.');
  }
  return decoded;
}
