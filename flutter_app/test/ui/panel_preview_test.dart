// The panel preview renders whatever frame the provider holds.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ipixel_controller/render/panel_image.dart';
import 'package:ipixel_controller/ui/preview/preview_provider.dart';
import 'package:ipixel_controller/ui/widgets/panel_preview.dart';

void main() {
  testWidgets('renders the seeded placeholder frame', (tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(home: Scaffold(body: PanelPreview())),
      ),
    );
    await tester.pump();

    expect(find.byType(Image), findsOneWidget);
  });

  testWidgets('renders a published frame with nearest-neighbour filtering', (
    tester,
  ) async {
    final container = ProviderContainer();
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: Scaffold(body: PanelPreview())),
      ),
    );

    final frame = encodePanelPng(newCanvas(bgColor: '#112233'));
    container.read(panelPreviewProvider.notifier).setFrame(frame);
    await tester.pump();

    final image = tester.widget<Image>(find.byType(Image));
    expect(image.filterQuality, FilterQuality.none);
  });
}
