/// Registration shim for the Clock feature.
///
/// The real UI lives in `lib/features/clock/clock_page.dart`; this file only
/// exports the [PageDef] the shared registry lists, so `page_registry.dart`
/// never changes when the feature is filled in.
library;

import 'package:flutter/material.dart';

import 'package:ipixel_controller/features/clock/clock_page.dart';
import 'package:ipixel_controller/ui/pages/page_def.dart';

final PageDef clockPageDef = PageDef(
  id: 'clock',
  label: 'Clock',
  icon: Icons.access_time_outlined,
  selectedIcon: Icons.access_time_filled,
  builder: () => const ClockFeaturePage(key: Key('page-clock')),
);
