import 'package:flutter_test/flutter_test.dart';
import 'package:ipixel_controller/ble/scanner.dart';
import 'package:ipixel_controller/ble/transport.dart';

import 'fake_ble_transport.dart';

void main() {
  group('matchesPanelName', () {
    test('matches LED_BLE_ and LED-BLE- prefixes', () {
      expect(matchesPanelName('LED_BLE_1234'), isTrue);
      expect(matchesPanelName('LED-BLE-ABCD'), isTrue);
    });

    test('matches BGLight / B.K. Light / BK Light substrings', () {
      expect(matchesPanelName('My BGLight panel'), isTrue);
      expect(matchesPanelName('B.K. Light 01'), isTrue);
      expect(matchesPanelName('room BK Light'), isTrue);
    });

    test('rejects null, empty and unrelated names', () {
      expect(matchesPanelName(null), isFalse);
      expect(matchesPanelName(''), isFalse);
      expect(matchesPanelName('AirPods'), isFalse);
      expect(matchesPanelName('led_ble_lowercase'), isFalse);
    });
  });

  group('dedupeAndSortByRssi', () {
    test('sorts by RSSI descending', () {
      final sorted = dedupeAndSortByRssi(const <BleScanResult>[
        BleScanResult(id: 'a', name: 'A', rssi: -80),
        BleScanResult(id: 'b', name: 'B', rssi: -40),
        BleScanResult(id: 'c', name: 'C', rssi: -60),
      ]);
      expect(sorted.map((r) => r.id), <String>['b', 'c', 'a']);
    });

    test('dedupes by id keeping the latest entry', () {
      final sorted = dedupeAndSortByRssi(const <BleScanResult>[
        BleScanResult(id: 'a', name: 'A', rssi: -80),
        BleScanResult(id: 'a', name: 'A', rssi: -30),
      ]);
      expect(sorted.length, 1);
      expect(sorted.single.rssi, -30);
    });

    test('sorts null RSSI last', () {
      final sorted = dedupeAndSortByRssi(const <BleScanResult>[
        BleScanResult(id: 'a', name: 'A', rssi: null),
        BleScanResult(id: 'b', name: 'B', rssi: -70),
      ]);
      expect(sorted.map((r) => r.id), <String>['b', 'a']);
    });
  });

  group('PanelScanner', () {
    test('filters, dedupes and sorts live advertisements', () async {
      final fake = FakeBleTransport();
      final scanner = PanelScanner(fake);
      addTearDown(() async {
        await scanner.dispose();
        await fake.dispose();
      });

      final emissions = <List<BleScanResult>>[];
      scanner.results.listen(emissions.add);

      await scanner.start();
      expect(fake.calls, contains('startScan'));

      fake.emitScan(
        const BleScanResult(id: 'x', name: 'AirPods', rssi: -20),
      ); // filtered out
      fake.emitScan(const BleScanResult(id: 'a', name: 'LED_BLE_1', rssi: -70));
      fake.emitScan(const BleScanResult(id: 'b', name: 'BGLight 2', rssi: -40));
      fake.emitScan(
        const BleScanResult(id: 'a', name: 'LED_BLE_1', rssi: -30),
      ); // dedupe/update

      await pumpEventQueue();

      final latest = emissions.last;
      expect(latest.map((r) => r.id), <String>['a', 'b']); // -30 beats -40
      expect(latest.firstWhere((r) => r.id == 'a').rssi, -30);
    });
  });
}
