/// Home surface: panel preview + a short orientation blurb. Presets and the
/// brightness/power controls land here in S10.
library;

import 'package:flutter/material.dart';

import 'package:ipixel_controller/ui/pages/feature_scaffold.dart';
import 'package:ipixel_controller/ui/pages/page_def.dart';

final PageDef homePageDef = PageDef(
  id: 'home',
  label: 'Home',
  icon: Icons.home_outlined,
  selectedIcon: Icons.home,
  builder: () => const HomePage(key: Key('page-home')),
);

class HomePage extends StatelessWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context) {
    return const FeatureScaffold(
      title: 'iPixel Controller',
      children: [ComingSoonCard(feature: 'Presets, brightness and power')],
    );
  }
}
