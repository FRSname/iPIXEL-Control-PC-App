/// Image feature navigation entry. The real UI + logic live under
/// `features/image/` (S8); this file only wires the [PageDef] into the shared
/// registry, editing nothing else.
library;

import 'package:flutter/material.dart';

import 'package:ipixel_controller/features/image/image_page.dart';
import 'package:ipixel_controller/ui/pages/page_def.dart';

final PageDef imagePageDef = PageDef(
  id: 'image',
  label: 'Image',
  icon: Icons.image_outlined,
  selectedIcon: Icons.image,
  builder: () => const ImageFeaturePage(key: Key('page-image')),
);
