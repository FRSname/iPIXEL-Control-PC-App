/// Image feature placeholder. S8 replaces this body with image/GIF pick +
/// letterbox/crop + send — editing only this file, not the shared registry.
library;

import 'package:flutter/material.dart';

import 'package:ipixel_controller/ui/pages/feature_scaffold.dart';
import 'package:ipixel_controller/ui/pages/page_def.dart';

final PageDef imagePageDef = PageDef(
  id: 'image',
  label: 'Image',
  icon: Icons.image_outlined,
  selectedIcon: Icons.image,
  builder: () => const ImagePage(key: Key('page-image')),
);

class ImagePage extends StatelessWidget {
  const ImagePage({super.key});

  @override
  Widget build(BuildContext context) {
    return const FeatureScaffold(
      title: 'Image',
      children: [ComingSoonCard(feature: 'Image and GIF playback')],
    );
  }
}
