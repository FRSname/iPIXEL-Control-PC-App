import 'dart:io' show Platform;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ipixel_controller/ble/ble_permissions.dart';

import 'fake_ble_transport.dart';

/// Pumps a bare host and hands back the [BuildContext] the gate runs against.
/// The host sits under [MaterialApp] + [Scaffold] so the rationale dialog
/// (Navigator) and the denial [SnackBar] (which needs a descendant Scaffold to
/// present into) both have their ancestors.
Future<BuildContext> _pumpHost(WidgetTester tester) async {
  late BuildContext captured;
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: Builder(
          builder: (context) {
            captured = context;
            return const SizedBox();
          },
        ),
      ),
    ),
  );
  return captured;
}

void main() {
  testWidgets(
    'passes through without prompting or requesting on non-Android hosts',
    (tester) async {
      // The test host is macOS/Linux; the Android rationale + request path is
      // forced explicitly in the tests below.
      if (Platform.isAndroid) return;

      final transport = FakeBleTransport();
      final context = await _pumpHost(tester);

      final granted = await ensureBlePermissions(context, transport);

      expect(granted, isTrue);
      expect(
        transport.calls,
        isNot(contains('requestPermissions')),
        reason: 'desktop/Apple have no runtime BLE permission to request',
      );
      expect(transport.calls, isNot(contains('hasPermissions')));

      await transport.dispose();
    },
  );

  group('Android branch (forced via isAndroid predicate)', () {
    testWidgets('declining the rationale returns false and never requests', (
      tester,
    ) async {
      final transport = FakeBleTransport(); // permissionsGranted == false
      final context = await _pumpHost(tester);

      final future = ensureBlePermissions(
        context,
        transport,
        isAndroid: () => true,
      );
      await tester.pumpAndSettle();
      expect(find.text('Allow Bluetooth'), findsOneWidget);

      await tester.tap(find.text('Not now'));
      await tester.pumpAndSettle();

      expect(await future, isFalse);
      expect(transport.calls, contains('hasPermissions'));
      expect(
        transport.calls,
        isNot(contains('requestPermissions')),
        reason: 'a declined rationale must not reach the OS request',
      );

      await transport.dispose();
    });

    testWidgets(
      'accepting the rationale requests permissions and returns true',
      (tester) async {
        final transport = FakeBleTransport();
        final context = await _pumpHost(tester);

        final future = ensureBlePermissions(
          context,
          transport,
          isAndroid: () => true,
        );
        await tester.pumpAndSettle();

        await tester.tap(find.text('Continue'));
        await tester.pumpAndSettle();

        expect(await future, isTrue);
        expect(transport.calls, contains('requestPermissions'));

        await transport.dispose();
      },
    );

    testWidgets('a denied OS request surfaces a SnackBar and returns false', (
      tester,
    ) async {
      final transport = FakeBleTransport()..permissionsThrow = true;
      final context = await _pumpHost(tester);

      final future = ensureBlePermissions(
        context,
        transport,
        isAndroid: () => true,
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Continue'));
      await tester.pumpAndSettle();

      expect(await future, isFalse);
      expect(find.byType(SnackBar), findsOneWidget);
      expect(
        find.textContaining('Bluetooth permission is needed'),
        findsOneWidget,
      );

      await transport.dispose();
    });

    testWidgets(
      'already-granted skips the rationale but still requests (no-op) and '
      'returns true',
      (tester) async {
        final transport = FakeBleTransport()..permissionsGranted = true;
        final context = await _pumpHost(tester);

        final future = ensureBlePermissions(
          context,
          transport,
          isAndroid: () => true,
        );
        await tester.pumpAndSettle();

        expect(
          find.text('Allow Bluetooth'),
          findsNothing,
          reason: 'no rationale when the OS already granted access',
        );
        expect(await future, isTrue);
        expect(transport.calls, contains('hasPermissions'));
        expect(transport.calls, contains('requestPermissions'));

        await transport.dispose();
      },
    );
  });
}
