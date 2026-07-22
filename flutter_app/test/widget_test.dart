// Smoke test for the iPixel Controller placeholder app.
//
// Verifies the app boots and renders its title without errors.

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ipixel_controller/main.dart';

void main() {
  testWidgets('renders the iPixel Controller placeholder', (tester) async {
    await tester.pumpWidget(const ProviderScope(child: IPixelControllerApp()));

    // Title appears in both the AppBar and the body.
    expect(find.text('iPixel Controller'), findsNWidgets(2));
  });
}
