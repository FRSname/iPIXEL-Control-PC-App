/// Shared low-level blending / arithmetic helpers for the render core.
///
/// Pure Dart, no `dart:ui` — safe for `flutter test` VM tests and isolates.
library;

/// Fast `(a * b) / 255` with rounding, matching PIL's `MULDIV255` macro.
///
/// This is the exact integer arithmetic PIL uses inside `ImagingPaste` when
/// compositing with a mask, so ports that use it reproduce PIL's alpha blend
/// bit-for-bit (including anti-aliased / semi-transparent edges).
int mulDiv255(int a, int b) {
  final t = a * b + 128;
  return ((t >> 8) + t) >> 8;
}

/// Floored integer division, matching Python's `//` operator.
///
/// Dart's `~/` truncates toward zero, so for negative numerators it differs
/// from Python by one. The render core mirrors CPython's centering math, which
/// uses `//`, so all offset calculations go through this helper.
int floorDiv(int a, int b) => (a / b).floor();
