// Smoke test for the iPixel Controller app shell.
//
// Verifies the app boots into the responsive shell and shows the Home page.

import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ipixel_controller/ble/providers.dart';
import 'package:ipixel_controller/ui/app.dart';

import 'ble/fake_ble_transport.dart';

void main() {
  testWidgets('boots into the shell showing the Home page', (tester) async {
    final transport = FakeBleTransport();
    addTearDown(transport.dispose);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [bleTransportProvider.overrideWithValue(transport)],
        child: const IPixelControllerApp(),
      ),
    );
    await tester.pump();

    expect(find.byKey(const Key('page-home')), findsOneWidget);
    expect(find.text('Scan'), findsOneWidget);
  });
}
