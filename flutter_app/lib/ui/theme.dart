/// The app's dark theme.
///
/// Loosely follows the Qt desktop app's look: a dark neutral shell with a
/// single vivid accent (an LED-panel cyan/teal). No pixel parity intended.
library;

import 'package:flutter/material.dart';

/// Accent used across navigation selection, buttons and the connection status.
const Color _accent = Color(0xFF2DD4BF); // teal-400, "powered-on LED" vibe

/// Background of the outermost shell.
const Color _background = Color(0xFF0E1116);

/// Slightly lifted surface used for bars, rails and cards.
const Color _surface = Color(0xFF161B22);

/// Builds the single dark [ThemeData] the app runs under.
ThemeData buildDarkTheme() {
  final colorScheme = ColorScheme.fromSeed(
    seedColor: _accent,
    brightness: Brightness.dark,
  ).copyWith(surface: _surface, primary: _accent);

  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    colorScheme: colorScheme,
    scaffoldBackgroundColor: _background,
    navigationRailTheme: const NavigationRailThemeData(
      backgroundColor: _surface,
      indicatorColor: Color(0x332DD4BF),
      selectedIconTheme: IconThemeData(color: _accent),
      selectedLabelTextStyle: TextStyle(
        color: _accent,
        fontWeight: FontWeight.w600,
      ),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: _surface,
      indicatorColor: const Color(0x332DD4BF),
      labelTextStyle: WidgetStateProperty.resolveWith((states) {
        final selected = states.contains(WidgetState.selected);
        return TextStyle(
          color: selected ? _accent : Colors.white70,
          fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
          fontSize: 12,
        );
      }),
    ),
    dividerTheme: const DividerThemeData(color: Color(0xFF232A33), space: 1),
  );
}
