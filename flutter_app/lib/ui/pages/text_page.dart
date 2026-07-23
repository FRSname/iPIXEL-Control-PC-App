/// Text feature placeholder. S7 replaces this body with the real text input,
/// colour pickers, sprite-font dropdown and scroll controls — editing only this
/// file, not the shared registry.
library;

import 'package:flutter/material.dart';

import 'package:ipixel_controller/ui/pages/feature_scaffold.dart';
import 'package:ipixel_controller/ui/pages/page_def.dart';

final PageDef textPageDef = PageDef(
  id: 'text',
  label: 'Text',
  icon: Icons.text_fields_outlined,
  selectedIcon: Icons.text_fields,
  builder: () => const TextPage(key: Key('page-text')),
);

class TextPage extends StatelessWidget {
  const TextPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const FeatureScaffold(
      title: 'Text',
      children: [ComingSoonCard(feature: 'Scrolling and static text')],
    );
  }
}
