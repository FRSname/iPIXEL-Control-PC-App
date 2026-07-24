/// Registration shim for the Text feature.
///
/// The real UI lives in `lib/features/text/text_page.dart`; this file only
/// exports the [PageDef] the shared registry lists, so `page_registry.dart`
/// never changes when a feature is filled in.
library;

import 'package:flutter/material.dart';

import 'package:ipixel_controller/features/text/text_page.dart';
import 'package:ipixel_controller/ui/pages/page_def.dart';

final PageDef textPageDef = PageDef(
  id: 'text',
  label: 'Text',
  icon: Icons.text_fields_outlined,
  selectedIcon: Icons.text_fields,
  builder: () => const TextFeaturePage(key: Key('page-text')),
);
