/// Clock feature placeholder. S9 replaces this body with the sprite-clock,
/// custom-format and countdown modes — editing only this file, not the shared
/// registry.
library;

import 'package:flutter/material.dart';

import 'package:ipixel_controller/ui/pages/feature_scaffold.dart';
import 'package:ipixel_controller/ui/pages/page_def.dart';

final PageDef clockPageDef = PageDef(
  id: 'clock',
  label: 'Clock',
  icon: Icons.access_time_outlined,
  selectedIcon: Icons.access_time_filled,
  builder: () => const ClockPage(key: Key('page-clock')),
);

class ClockPage extends StatelessWidget {
  const ClockPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const FeatureScaffold(
      title: 'Clock',
      children: [ComingSoonCard(feature: 'Clock and countdown modes')],
    );
  }
}
