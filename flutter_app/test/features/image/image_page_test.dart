import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;

import 'package:ipixel_controller/ble/device_session.dart';
import 'package:ipixel_controller/ble/providers.dart';
import 'package:ipixel_controller/display/providers.dart';
import 'package:ipixel_controller/features/image/image_page.dart';
import 'package:ipixel_controller/features/image/image_picker_service.dart';
import 'package:ipixel_controller/render/panel_image.dart';
import 'package:ipixel_controller/ui/preview/preview_provider.dart';

/// A picker that returns a fixed image (or `null` to simulate cancel).
class _FakePicker implements PanelImagePicker {
  _FakePicker(this._result);
  final PickedImage? _result;
  int calls = 0;

  @override
  Future<PickedImage?> pickImage() async {
    calls++;
    return _result;
  }
}

/// Records every frame handed to the panel sink.
class _RecordingSink {
  final List<Uint8List> pngs = <Uint8List>[];
  Future<void> call(Uint8List png) async => pngs.add(png);
}

Uint8List _solidPng(int w, int h) {
  final image = img.Image(width: w, height: h, numChannels: 3);
  img.fill(image, color: img.ColorRgb8(0, 200, 0));
  return img.encodePng(image);
}

PickedImage _staticPicked() =>
    PickedImage(bytes: _solidPng(32, 32), name: 'photo.png');

Widget _harness({
  required BleConnectionStatus status,
  required _RecordingSink sink,
  required PanelImagePicker picker,
}) {
  return ProviderScope(
    overrides: [
      connectionStatusProvider.overrideWith((ref) => Stream.value(status)),
      panelImageSinkProvider.overrideWithValue(sink.call),
      panelImagePickerProvider.overrideWithValue(picker),
    ],
    child: const MaterialApp(home: Scaffold(body: ImageFeaturePage())),
  );
}

void main() {
  testWidgets('renders the source, fit and send controls', (tester) async {
    await tester.pumpWidget(
      _harness(
        status: BleConnectionStatus.ready,
        sink: _RecordingSink(),
        picker: _FakePicker(null),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Image'), findsWidgets);
    expect(find.text('Source'), findsOneWidget);
    expect(find.text('Fit'), findsOneWidget);
    expect(find.text('Letterbox'), findsOneWidget);
    expect(find.text('Crop'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'Send to panel'), findsOneWidget);
  });

  testWidgets('send is disabled when the panel is not connected', (
    tester,
  ) async {
    await tester.pumpWidget(
      _harness(
        status: BleConnectionStatus.disconnected,
        sink: _RecordingSink(),
        picker: _FakePicker(_staticPicked()),
      ),
    );
    await tester.pumpAndSettle();

    final button = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'Send to panel'),
    );
    expect(button.onPressed, isNull);
    expect(find.text('Connect to a panel to send.'), findsOneWidget);
  });

  testWidgets('send stays disabled until an image is picked', (tester) async {
    final picker = _FakePicker(_staticPicked());
    await tester.pumpWidget(
      _harness(
        status: BleConnectionStatus.ready,
        sink: _RecordingSink(),
        picker: picker,
      ),
    );
    await tester.pumpAndSettle();

    // Connected but no image yet → still disabled.
    var button = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'Send to panel'),
    );
    expect(button.onPressed, isNull);

    await tester.tap(find.widgetWithText(OutlinedButton, 'Pick image or GIF'));
    await tester.pumpAndSettle();
    expect(picker.calls, 1);

    button = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'Send to panel'),
    );
    expect(button.onPressed, isNotNull, reason: 'enabled once an image loads');
    expect(find.text('photo.png'), findsOneWidget);
  });

  testWidgets('picking then sending routes a frame to the sink and preview', (
    tester,
  ) async {
    final sink = _RecordingSink();
    await tester.pumpWidget(
      _harness(
        status: BleConnectionStatus.ready,
        sink: sink,
        picker: _FakePicker(_staticPicked()),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.widgetWithText(OutlinedButton, 'Pick image or GIF'));
    await tester.pumpAndSettle();

    final sendButton = find.widgetWithText(FilledButton, 'Send to panel');
    await tester.ensureVisible(sendButton);
    await tester.tap(sendButton);
    await tester.pumpAndSettle();

    expect(sink.pngs, hasLength(1));
    final decoded = img.decodePng(sink.pngs.single)!;
    expect(decoded.width, panelWidth);
    expect(decoded.height, panelHeight);

    // The live preview shows the exact frame that was sent.
    final container = ProviderScope.containerOf(
      tester.element(find.byType(ImageFeaturePage)),
    );
    expect(container.read(panelPreviewProvider), equals(sink.pngs.single));
  });

  testWidgets('switching to crop re-fits and updates the preview', (
    tester,
  ) async {
    await tester.pumpWidget(
      _harness(
        status: BleConnectionStatus.ready,
        sink: _RecordingSink(),
        picker: _FakePicker(_staticPicked()),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.widgetWithText(OutlinedButton, 'Pick image or GIF'));
    await tester.pumpAndSettle();

    final container = ProviderScope.containerOf(
      tester.element(find.byType(ImageFeaturePage)),
    );
    final letterboxPreview = container.read(panelPreviewProvider);

    await tester.tap(find.text('Crop'));
    await tester.pumpAndSettle();

    final cropPreview = container.read(panelPreviewProvider);
    // A 32x32 square letterboxes with padding but crops to a full fill, so the
    // two preview frames differ.
    expect(cropPreview, isNot(equals(letterboxPreview)));
  });
}
