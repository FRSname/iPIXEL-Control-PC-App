// Shell tests: the responsive shell renders and switches pages in both the
// wide (NavigationRail) and narrow (NavigationBar) layouts. Pages live in an
// IndexedStack, so offstage pages stay in the tree (state persists) while the
// default finder (skipOffstage: true) only sees the visible one.

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ipixel_controller/ble/providers.dart';
import 'package:ipixel_controller/ui/app.dart';

import '../ble/fake_ble_transport.dart';

Future<void> _pumpShell(
  WidgetTester tester,
  Size size, {
  ProviderContainer? container,
}) async {
  tester.view.devicePixelRatio = 1.0;
  tester.view.physicalSize = size;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);

  if (container != null) {
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const IPixelControllerApp(),
      ),
    );
    await tester.pump();
    return;
  }

  final transport = FakeBleTransport();
  addTearDown(transport.dispose);

  await tester.pumpWidget(
    ProviderScope(
      overrides: [bleTransportProvider.overrideWithValue(transport)],
      child: const IPixelControllerApp(),
    ),
  );
  await tester.pump();
}

void main() {
  testWidgets('wide layout uses a NavigationRail and switches pages', (
    tester,
  ) async {
    await _pumpShell(tester, const Size(1200, 800));

    expect(find.byType(NavigationRail), findsOneWidget);
    expect(find.byType(NavigationBar), findsNothing);
    expect(find.byKey(const Key('page-home')), findsOneWidget);

    await tester.tap(find.text('Text'));
    await tester.pumpAndSettle();

    // The visible page is Text; Home is now offstage (skipped by default).
    expect(find.byKey(const Key('page-text')), findsOneWidget);
    expect(find.byKey(const Key('page-home')), findsNothing);
  });

  testWidgets('narrow layout uses a NavigationBar and switches pages', (
    tester,
  ) async {
    await _pumpShell(tester, const Size(400, 800));

    expect(find.byType(NavigationBar), findsOneWidget);
    expect(find.byType(NavigationRail), findsNothing);
    expect(find.byKey(const Key('page-home')), findsOneWidget);

    await tester.tap(find.text('Image'));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('page-image')), findsOneWidget);
    expect(find.byKey(const Key('page-home')), findsNothing);
  });

  testWidgets('IndexedStack keeps every page in the tree so state persists', (
    tester,
  ) async {
    await _pumpShell(tester, const Size(1200, 800));

    await tester.tap(find.text('Text'));
    await tester.pumpAndSettle();

    // With skipOffstage: false, the offstage Home page is still mounted — its
    // element (and any future form State) survives the tab switch.
    expect(
      find.byKey(const Key('page-home'), skipOffstage: false),
      findsOneWidget,
    );
    expect(
      find.byKey(const Key('page-text'), skipOffstage: false),
      findsOneWidget,
    );
    // Every registered page is built once and held in the stack.
    expect(
      find.byKey(const Key('page-settings'), skipOffstage: false),
      findsOneWidget,
    );
  });

  testWidgets('surfaces guard errors from lastErrorProvider as a SnackBar', (
    tester,
  ) async {
    final errors = StreamController<String>.broadcast();
    addTearDown(errors.close);
    final transport = FakeBleTransport();
    addTearDown(transport.dispose);

    final container = ProviderContainer(
      overrides: [
        bleTransportProvider.overrideWithValue(transport),
        lastErrorProvider.overrideWith((ref) => errors.stream),
      ],
    );
    addTearDown(container.dispose);

    await _pumpShell(tester, const Size(1200, 800), container: container);

    errors.add('panel stopped responding');
    await tester.pump(); // deliver the stream event
    await tester.pump(); // start the SnackBar animation

    expect(find.text('panel stopped responding'), findsOneWidget);
  });
}
