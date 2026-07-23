import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;

import 'package:ipixel_controller/ble/device_session.dart';
import 'package:ipixel_controller/ble/providers.dart';
import 'package:ipixel_controller/display/display_task.dart';
import 'package:ipixel_controller/display/providers.dart';
import 'package:ipixel_controller/display/sprite_font_registry.dart';
import 'package:ipixel_controller/features/text/text_page.dart';
import 'package:ipixel_controller/render/panel_image.dart';
import 'package:ipixel_controller/render/sprite_font.dart';
import 'package:ipixel_controller/ui/preview/preview_provider.dart';

const String _textOrder =
    '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:!?.,+-/\$%';

SpriteFontService _fontService() {
  final bytes = File('assets/sprites/TextSprite.png').readAsBytesSync();
  final font = SpriteFont(
    name: 'Text Default',
    path: 'assets/sprites/TextSprite.png',
    order: _textOrder,
    cols: 73,
  )..loadFromBytes(bytes);
  return SpriteFontService()..registerFont(font);
}

/// Records every frame handed to the panel sink.
class _RecordingSink {
  final List<Uint8List> pngs = <Uint8List>[];
  Future<void> call(Uint8List png) async => pngs.add(png);
}

Widget _harness({
  required BleConnectionStatus status,
  required _RecordingSink sink,
}) {
  final service = _fontService();
  return ProviderScope(
    overrides: [
      spriteFontRegistryProvider.overrideWith((ref) async => service),
      connectionStatusProvider.overrideWith((ref) => Stream.value(status)),
      panelImageSinkProvider.overrideWithValue(sink.call),
    ],
    child: const MaterialApp(home: Scaffold(body: TextFeaturePage())),
  );
}

void main() {
  testWidgets('renders the message field, font dropdown and send button', (
    tester,
  ) async {
    await tester.pumpWidget(
      _harness(status: BleConnectionStatus.ready, sink: _RecordingSink()),
    );
    await tester.pumpAndSettle();

    expect(find.text('Text'), findsWidgets);
    expect(find.text('Message'), findsOneWidget);
    expect(find.text('Sprite font'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'Send to panel'), findsOneWidget);
    // Default mode is static: no speed slider.
    expect(find.byType(Slider), findsNothing);
  });

  testWidgets('switching to a scroll mode reveals the speed slider', (
    tester,
  ) async {
    await tester.pumpWidget(
      _harness(status: BleConnectionStatus.ready, sink: _RecordingSink()),
    );
    await tester.pumpAndSettle();

    expect(find.byType(Slider), findsNothing);

    await tester.ensureVisible(find.text('Scroll left'));
    await tester.tap(find.text('Scroll left'));
    await tester.pumpAndSettle();

    expect(find.byType(Slider), findsOneWidget);
  });

  testWidgets('send is disabled when the panel is not connected', (
    tester,
  ) async {
    await tester.pumpWidget(
      _harness(
        status: BleConnectionStatus.disconnected,
        sink: _RecordingSink(),
      ),
    );
    await tester.pumpAndSettle();

    final button = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'Send to panel'),
    );
    expect(button.onPressed, isNull);
    expect(find.text('Connect to a panel to send.'), findsOneWidget);
  });

  testWidgets('tapping send renders a frame to the sink and the preview', (
    tester,
  ) async {
    final sink = _RecordingSink();
    await tester.pumpWidget(
      _harness(status: BleConnectionStatus.ready, sink: sink),
    );
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
      tester.element(find.byType(TextFeaturePage)),
    );
    expect(container.read(panelPreviewProvider), equals(sink.pngs.single));
  });

  testWidgets('disconnecting mid-scroll stops the active display task', (
    tester,
  ) async {
    final sink = _RecordingSink();
    final statusController = StreamController<BleConnectionStatus>.broadcast();
    addTearDown(statusController.close);
    final service = _fontService();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          spriteFontRegistryProvider.overrideWith((ref) async => service),
          connectionStatusProvider.overrideWith(
            (ref) => statusController.stream,
          ),
          panelImageSinkProvider.overrideWithValue(sink.call),
        ],
        child: const MaterialApp(home: Scaffold(body: TextFeaturePage())),
      ),
    );
    statusController.add(BleConnectionStatus.ready);
    await tester.pumpAndSettle();

    // Switch to a scrolling mode ("Hello World" is wider than the panel).
    await tester.ensureVisible(find.text('Scroll left'));
    await tester.tap(find.text('Scroll left'));
    await tester.pumpAndSettle();

    final sendButton = find.widgetWithText(FilledButton, 'Send to panel');
    await tester.ensureVisible(sendButton);
    await tester.tap(sendButton);
    // Not pumpAndSettle: a live scroll keeps a timer pending forever.
    await tester.pump();
    await tester.pump();

    final container = ProviderScope.containerOf(
      tester.element(find.byType(TextFeaturePage)),
    );
    expect(
      container.read(activeDisplayTaskProvider),
      isTrue,
      reason: 'scroll task is active',
    );
    final framesBeforeDisconnect = sink.pngs.length;
    expect(framesBeforeDisconnect, greaterThanOrEqualTo(1));

    // Drop the connection mid-scroll: the page's ref.listen clears the slot.
    statusController.add(BleConnectionStatus.disconnected);
    await tester.pump();
    await tester.pump();

    expect(
      container.read(activeDisplayTaskProvider),
      isFalse,
      reason: 'the disconnect listener cleared the active task',
    );

    // The scroll timer is cancelled: advancing time yields no more frames.
    await tester.pump(const Duration(milliseconds: 400));
    expect(sink.pngs.length, framesBeforeDisconnect, reason: 'timer stopped');
  });

  testWidgets('shows an error and sends nothing when the message is empty', (
    tester,
  ) async {
    final sink = _RecordingSink();
    await tester.pumpWidget(
      _harness(status: BleConnectionStatus.ready, sink: sink),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField).first, '   ');
    final sendButton = find.widgetWithText(FilledButton, 'Send to panel');
    await tester.ensureVisible(sendButton);
    await tester.tap(sendButton);
    await tester.pump();

    expect(sink.pngs, isEmpty);
    expect(find.text('Enter some text first.'), findsOneWidget);
  });
}
