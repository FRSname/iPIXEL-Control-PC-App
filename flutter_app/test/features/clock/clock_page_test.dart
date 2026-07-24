import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;

import 'package:ipixel_controller/ble/device_session.dart';
import 'package:ipixel_controller/ble/providers.dart';
import 'package:ipixel_controller/display/providers.dart';
import 'package:ipixel_controller/display/sprite_font_registry.dart';
import 'package:ipixel_controller/features/clock/clock_page.dart';
import 'package:ipixel_controller/render/panel_image.dart';
import 'package:ipixel_controller/render/sprite_font.dart';
import 'package:ipixel_controller/ui/preview/preview_provider.dart';

const String _textOrder =
    '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:!?.,+-/\$%';

/// A service with both a text sheet (letters) and a clock sheet (digits+colon)
/// so both the sprite-clock and custom/countdown modes resolve a real font.
SpriteFontService _fontService() {
  final textBytes = File('assets/sprites/TextSprite.png').readAsBytesSync();
  final text = SpriteFont(
    name: 'Text Default',
    path: 'assets/sprites/TextSprite.png',
    order: _textOrder,
    cols: 73,
  )..loadFromBytes(textBytes);

  final clockBytes = File(
    'assets/sprites/SmallerClocksSprite-transp.png',
  ).readAsBytesSync();
  final clock = SpriteFont(
    name: 'Clock Default',
    path: 'assets/sprites/SmallerClocksSprite-transp.png',
    order: '0123456789:',
    cols: 11,
  )..loadFromBytes(clockBytes);

  return SpriteFontService()
    ..registerFont(text)
    ..registerFont(clock);
}

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
    child: const MaterialApp(home: Scaffold(body: ClockFeaturePage())),
  );
}

void main() {
  testWidgets('renders the mode picker and show button', (tester) async {
    await tester.pumpWidget(
      _harness(status: BleConnectionStatus.ready, sink: _RecordingSink()),
    );
    await tester.pumpAndSettle();

    expect(find.text('Clock'), findsWidgets);
    expect(find.text('Mode'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, 'Show clock'), findsOneWidget);
    // Sprite mode is the default: its "Show seconds" toggle is visible.
    expect(find.text('Show seconds'), findsOneWidget);
  });

  testWidgets('switching modes swaps the mode-specific card', (tester) async {
    await tester.pumpWidget(
      _harness(status: BleConnectionStatus.ready, sink: _RecordingSink()),
    );
    await tester.pumpAndSettle();

    // Sprite -> Custom reveals the time-format dropdown.
    await tester.ensureVisible(find.text('Custom'));
    await tester.tap(find.text('Custom'));
    await tester.pumpAndSettle();
    expect(find.text('Time format'), findsOneWidget);
    expect(find.text('Show seconds'), findsNothing);

    // Custom -> Countdown reveals the target picker and display dropdown.
    await tester.ensureVisible(find.text('Countdown'));
    await tester.tap(find.text('Countdown'));
    await tester.pumpAndSettle();
    expect(find.text('Time format'), findsNothing);
    expect(find.textContaining('Target:'), findsOneWidget);
    expect(find.text('Display'), findsOneWidget);
  });

  testWidgets('show is disabled when the panel is not connected', (
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
      find.widgetWithText(FilledButton, 'Show clock'),
    );
    expect(button.onPressed, isNull);
    expect(find.text('Connect to a panel to show the clock.'), findsOneWidget);
  });

  testWidgets('tapping show renders a clock frame to sink and preview', (
    tester,
  ) async {
    final sink = _RecordingSink();
    await tester.pumpWidget(
      _harness(status: BleConnectionStatus.ready, sink: sink),
    );
    await tester.pumpAndSettle();

    final showButton = find.widgetWithText(FilledButton, 'Show clock');
    await tester.ensureVisible(showButton);
    await tester.tap(showButton);
    // Not pumpAndSettle: a live clock keeps a timer pending forever.
    await tester.pump();
    await tester.pump();

    expect(sink.pngs, hasLength(1), reason: 'first frame sent on show');
    final decoded = img.decodePng(sink.pngs.single)!;
    expect(decoded.width, panelWidth);
    expect(decoded.height, panelHeight);

    final container = ProviderScope.containerOf(
      tester.element(find.byType(ClockFeaturePage)),
    );
    expect(container.read(panelPreviewProvider), equals(sink.pngs.single));

    // Stop the loop so the test's pending timer does not leak.
    await tester.tap(find.widgetWithText(OutlinedButton, 'Stop'));
    await tester.pump();
  });
}
