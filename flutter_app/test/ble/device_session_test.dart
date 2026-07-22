import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:ipixel_controller/ble/device_session.dart';

import 'fake_ble_transport.dart';

const _deviceId = 'PANEL-1';

Uint8List _png(int fill, int length) =>
    Uint8List.fromList(List<int>.filled(length, fill));

void main() {
  group('DeviceSession.connect', () {
    test(
      'sends handshake after subscribe and is ready only after its ack',
      () async {
        final fake = FakeBleTransport();
        final session = DeviceSession(transport: fake);
        addTearDown(() async {
          await session.dispose();
          await fake.dispose();
        });

        await session.connect(_deviceId);

        expect(session.currentStatus, BleConnectionStatus.ready);
        // Connect-flow order is a hard invariant.
        expect(fake.calls, <String>[
          'connect',
          'requestMtu',
          'discoverServices',
          'subscribe',
          'write',
        ]);
        // The one write during connect is the handshake ([_, _, _, 0x80]).
        expect(fake.writes.single[3], 0x80);
        // Handshake write comes strictly after subscribe.
        expect(
          fake.calls.indexOf('write'),
          greaterThan(fake.calls.indexOf('subscribe')),
        );
      },
    );

    test('is not ready when the handshake ack never arrives', () async {
      final fake = FakeBleTransport(autoAckHandshake: false);
      final session = DeviceSession(
        transport: fake,
        handshakeTimeout: const Duration(milliseconds: 50),
      );
      addTearDown(() async {
        await session.dispose();
        await fake.dispose();
      });

      await expectLater(
        session.connect(_deviceId),
        throwsA(isA<AckTimeoutException>()),
      );
      expect(session.currentStatus, BleConnectionStatus.disconnected);
    });
  });

  group('DeviceSession.sendImage MTU-adaptive chunking', () {
    Future<List<Uint8List>> chunksForMtu(int mtu) async {
      final fake = FakeBleTransport(mtu: mtu, autoAckSendImageFinal: true);
      final session = DeviceSession(transport: fake);
      addTearDown(() async {
        await session.dispose();
        await fake.dispose();
      });

      await session.connect(_deviceId);
      fake.writes.clear(); // drop the handshake write
      await session.sendImage(_png(0xAA, 500));
      return fake.writes;
    }

    test('MTU 247 yields a 244-byte chunk size', () async {
      final chunks = await chunksForMtu(247);
      expect(chunks.length, greaterThan(1));
      expect(chunks.first.length, 244);
      expect(chunks.every((c) => c.length <= 244), isTrue);
    });

    test('MTU 185 yields a 182-byte chunk size', () async {
      final chunks = await chunksForMtu(185);
      expect(chunks.length, greaterThan(1));
      expect(chunks.first.length, 182);
      expect(chunks.every((c) => c.length <= 182), isTrue);
    });
  });

  group('DeviceSession command semantics', () {
    test('final ack resolves sendImage successfully', () async {
      final fake = FakeBleTransport(autoAckSendImageFinal: true);
      final session = DeviceSession(transport: fake);
      addTearDown(() async {
        await session.dispose();
        await fake.dispose();
      });

      await session.connect(_deviceId);
      await session.sendImage(_png(0xAA, 300)); // completes without throwing
      expect(session.guard.consecutiveFailures, 0);
    });

    test('missing final ack times out with AckTimeoutException', () async {
      final fake = FakeBleTransport(autoAckSendImageFinal: false);
      final session = DeviceSession(
        transport: fake,
        sendImageTimeout: const Duration(milliseconds: 50),
      );
      addTearDown(() async {
        await session.dispose();
        await fake.dispose();
      });

      await session.connect(_deviceId);
      await expectLater(
        session.sendImage(_png(0xAA, 300)),
        throwsA(isA<AckTimeoutException>()),
      );
    });

    test('a second send waits for the first to complete', () async {
      final fake = FakeBleTransport(autoAckSendImageFinal: false);
      final session = DeviceSession(transport: fake);
      addTearDown(() async {
        await session.dispose();
        await fake.dispose();
      });

      await session.connect(_deviceId);
      fake.writes.clear();

      final first = session.sendImage(_png(0xAA, 300));
      final second = session.sendImage(_png(0xBB, 300));

      await pumpEventQueue();
      // Only the first payload's chunks have been written so far.
      expect(fake.writes.any((c) => c.contains(0xAA)), isTrue);
      expect(fake.writes.any((c) => c.contains(0xBB)), isFalse);

      fake.emit(FakeBleTransport.finalAck);
      await first;

      await pumpEventQueue();
      // Now the second command runs.
      expect(fake.writes.any((c) => c.contains(0xBB)), isTrue);

      fake.emit(FakeBleTransport.finalAck);
      await second;
    });

    test('setBrightness resolves on a generic ack', () async {
      final fake = FakeBleTransport();
      final session = DeviceSession(transport: fake);
      addTearDown(() async {
        await session.dispose();
        await fake.dispose();
      });

      await session.connect(_deviceId);
      await session.setBrightness(50);
      expect(session.guard.consecutiveFailures, 0);
    });
  });

  group('DeviceSession failure guard', () {
    test('one failure then a success resets the counter', () async {
      final fake = FakeBleTransport(autoAckSendImageFinal: false);
      final session = DeviceSession(
        transport: fake,
        sendImageTimeout: const Duration(milliseconds: 50),
      );
      addTearDown(() async {
        await session.dispose();
        await fake.dispose();
      });

      await session.connect(_deviceId);

      await expectLater(
        session.sendImage(_png(0xAA, 300)),
        throwsA(isA<AckTimeoutException>()),
      );
      expect(session.guard.consecutiveFailures, 1);

      fake.autoAckSendImageFinal = true;
      await session.sendImage(_png(0xAA, 300));
      expect(session.guard.consecutiveFailures, 0);
      expect(session.guard.isTripped, isFalse);
    });

    test('two consecutive failures disconnect the session', () async {
      final fake = FakeBleTransport(autoAckSendImageFinal: false);
      final session = DeviceSession(
        transport: fake,
        sendImageTimeout: const Duration(milliseconds: 50),
      );
      addTearDown(() async {
        await session.dispose();
        await fake.dispose();
      });

      await session.connect(_deviceId);

      await expectLater(
        session.sendImage(_png(0xAA, 300)),
        throwsA(isA<AckTimeoutException>()),
      );
      await expectLater(
        session.sendImage(_png(0xAA, 300)),
        throwsA(isA<AckTimeoutException>()),
      );

      expect(session.guard.isTripped, isTrue);
      expect(fake.calls, contains('disconnect'));
      expect(session.currentStatus, BleConnectionStatus.disconnected);
    });
  });

  group('DeviceSession races and edge cases', () {
    test(
      'disconnect mid-sendImage fails cleanly (StateError, no TypeError)',
      () async {
        final fake = FakeBleTransport(autoAckSendImageFinal: false);
        final session = DeviceSession(transport: fake);
        addTearDown(() async {
          await session.dispose();
          await fake.dispose();
        });

        await session.connect(_deviceId);

        // Tear the session down concurrently while the chunk loop is running.
        fake.afterWrite = (value) async {
          final isSendImageStart =
              value.length >= 5 &&
              value[2] == 0x02 &&
              value[3] == 0x00 &&
              value[4] == 0x00;
          if (isSendImageStart) {
            fake.afterWrite = null; // fire once
            await session.disconnect();
          }
        };

        await expectLater(
          session.sendImage(
            _png(0xAA, 500),
          ), // multi-chunk: loop re-checks status
          throwsA(isA<StateError>()),
        );
        expect(session.currentStatus, BleConnectionStatus.disconnected);
        // An intentional disconnect is not an ack-failure: the guard must be clean.
        expect(session.guard.consecutiveFailures, 0);
      },
    );

    test('a second overlapping connect() is rejected', () async {
      final fake = FakeBleTransport();
      final session = DeviceSession(transport: fake);
      addTearDown(() async {
        await session.dispose();
        await fake.dispose();
      });

      final first = session.connect(_deviceId); // status -> connecting
      await expectLater(session.connect(_deviceId), throwsA(isA<StateError>()));
      await first;
      expect(session.currentStatus, BleConnectionStatus.ready);
    });

    test('requestMtu throwing falls back to the default MTU', () async {
      final fake = FakeBleTransport(mtuThrows: true);
      final session = DeviceSession(transport: fake);
      addTearDown(() async {
        await session.dispose();
        await fake.dispose();
      });

      await session.connect(_deviceId);
      expect(session.currentStatus, BleConnectionStatus.ready);
      expect(session.mtu, 247);
    });

    test('missing fa02 write characteristic fails the connect', () async {
      final fake = FakeBleTransport(omitWriteCharacteristic: true);
      final session = DeviceSession(transport: fake);
      addTearDown(() async {
        await session.dispose();
        await fake.dispose();
      });

      await expectLater(
        session.connect(_deviceId),
        throwsA(isA<CharacteristicNotFoundException>()),
      );
      expect(session.currentStatus, BleConnectionStatus.disconnected);
    });

    test('missing fa03 notify characteristic fails the connect', () async {
      final fake = FakeBleTransport(omitNotifyCharacteristic: true);
      final session = DeviceSession(transport: fake);
      addTearDown(() async {
        await session.dispose();
        await fake.dispose();
      });

      await expectLater(
        session.connect(_deviceId),
        throwsA(isA<CharacteristicNotFoundException>()),
      );
      expect(session.currentStatus, BleConnectionStatus.disconnected);
    });

    test('a negotiated MTU below the floor is clamped to 23', () async {
      final fake = FakeBleTransport(mtu: 10, autoAckSendImageFinal: true);
      final session = DeviceSession(transport: fake);
      addTearDown(() async {
        await session.dispose();
        await fake.dispose();
      });

      await session.connect(_deviceId);
      expect(session.mtu, 23);

      fake.writes.clear();
      await session.sendImage(_png(0xAA, 100));
      // chunkSize == min(244, 23 - 3) == 20.
      expect(fake.writes.first.length, 20);
      expect(fake.writes.every((c) => c.length <= 20), isTrue);
    });

    test(
      'disconnect during setPower ack wait yields StateError, guard untouched',
      () async {
        final fake = FakeBleTransport(autoAckGeneric: false);
        final session = DeviceSession(
          transport: fake,
          ackTimeout: const Duration(milliseconds: 50),
        );
        addTearDown(() async {
          await session.dispose();
          await fake.dispose();
        });

        await session.connect(_deviceId);

        // Tear the session down while the power command awaits its ack.
        fake.afterWrite = (value) async {
          final isPower = value.length >= 3 && value[0] == 5 && value[2] == 7;
          if (isPower) {
            fake.afterWrite = null; // fire once
            await session.disconnect();
          }
        };

        await expectLater(
          session.setPower(on: true),
          throwsA(isA<StateError>()),
        );
        // An intentional disconnect must not be recorded as an ack-failure.
        expect(session.guard.consecutiveFailures, 0);
        expect(session.currentStatus, BleConnectionStatus.disconnected);
      },
    );
  });

  group('DeviceSession.statusChanges', () {
    test(
      'seeds current state then emits a same-frame transition with no drops',
      () async {
        final fake = FakeBleTransport();
        final session = DeviceSession(transport: fake);
        addTearDown(() async {
          await session.dispose();
          await fake.dispose();
        });

        final events = <BleConnectionStatus>[];
        final sub = session.statusChanges.listen(events.add);
        // Transition in the SAME synchronous frame as the subscription.
        final connecting = session.connect(_deviceId);
        await connecting;
        await pumpEventQueue();
        await sub.cancel();

        expect(events, <BleConnectionStatus>[
          BleConnectionStatus.disconnected, // seed first, no duplicate
          BleConnectionStatus.connecting,
          BleConnectionStatus.ready,
        ]);
      },
    );

    test(
      'seeds then emits a transition one microtask later with no drops',
      () async {
        final fake = FakeBleTransport();
        final session = DeviceSession(transport: fake);
        addTearDown(() async {
          await session.dispose();
          await fake.dispose();
        });

        final events = <BleConnectionStatus>[];
        final sub = session.statusChanges.listen(events.add);
        await Future<void>.microtask(() {});
        final connecting = session.connect(_deviceId);
        await connecting;
        await pumpEventQueue();
        await sub.cancel();

        expect(events, <BleConnectionStatus>[
          BleConnectionStatus.disconnected,
          BleConnectionStatus.connecting,
          BleConnectionStatus.ready,
        ]);
      },
    );
  });
}
