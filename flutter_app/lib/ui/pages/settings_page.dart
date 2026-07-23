/// Settings placeholder. Legacy import and the sprite-font library editor land
/// here in S10.
library;

import 'package:flutter/material.dart';

import 'package:ipixel_controller/ui/pages/feature_scaffold.dart';
import 'package:ipixel_controller/ui/pages/page_def.dart';

final PageDef settingsPageDef = PageDef(
  id: 'settings',
  label: 'Settings',
  icon: Icons.settings_outlined,
  selectedIcon: Icons.settings,
  builder: () => const SettingsPage(key: Key('page-settings')),
);

class SettingsPage extends StatelessWidget {
  const SettingsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const FeatureScaffold(
      title: 'Settings',
      showPreview: false,
      children: [ComingSoonCard(feature: 'Legacy import and preferences')],
    );
  }
}
