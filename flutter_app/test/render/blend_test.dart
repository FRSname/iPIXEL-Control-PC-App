// Tests for lib/render/blend.dart — the shared MULDIV255 blend and Python-
// matching floored integer division.
import 'package:ipixel_controller/render/blend.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('mulDiv255', () {
    // Hand-computed against PIL's MULDIV255: t = a*b + 128; ((t>>8)+t)>>8.
    test('endpoints and known values', () {
      expect(mulDiv255(0, 128), 0); // anything * 0-ish channel
      expect(mulDiv255(255, 0), 0);
      expect(mulDiv255(255, 255), 255);
      expect(mulDiv255(255, 127), 127); // ~ 255*127/255
      expect(mulDiv255(255, 128), 128);
      expect(mulDiv255(128, 128), 64); // ~ 128*128/255 = 64.25
      expect(mulDiv255(200, 100), 78); // ~ 200*100/255 = 78.4
    });
  });

  group('floorDiv', () {
    test(
      'matches Python // for positive and negative non-exact remainders',
      () {
        expect(floorDiv(29, 2), 14); // exact-ish positive
        expect(floorDiv(7, 2), 3);
        // Negative numerators: floor differs from Dart ~/ (which truncates).
        expect(floorDiv(-5, 2), -3); // floor(-2.5) == -3, not -2
        expect(floorDiv(-1, 2), -1); // floor(-0.5) == -1, not 0
        expect(floorDiv(-4, 2), -2); // exact negative
      },
    );
  });
}
