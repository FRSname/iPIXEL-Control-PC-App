/// Root [MaterialApp]: applies the dark theme and hosts the responsive shell.
library;

import 'package:flutter/material.dart';

import 'package:ipixel_controller/ui/shell.dart';
import 'package:ipixel_controller/ui/theme.dart';

class IPixelControllerApp extends StatelessWidget {
  const IPixelControllerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'iPixel Controller',
      debugShowCheckedModeBanner: false,
      theme: buildDarkTheme(),
      home: const AppShell(),
    );
  }
}
