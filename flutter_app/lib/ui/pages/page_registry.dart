/// The ordered list of navigable pages the shell renders.
///
/// Each entry comes from that page's own file (`<feature>_page.dart`), which
/// exports a single `PageDef`. Feature steps fill in their page body without
/// editing this file: the five slots already exist, so S8 (image) and S9
/// (clock) touch only their own files and never collide here.
library;

import 'package:ipixel_controller/ui/pages/clock_page.dart';
import 'package:ipixel_controller/ui/pages/home_page.dart';
import 'package:ipixel_controller/ui/pages/image_page.dart';
import 'package:ipixel_controller/ui/pages/page_def.dart';
import 'package:ipixel_controller/ui/pages/settings_page.dart';
import 'package:ipixel_controller/ui/pages/text_page.dart';

/// Registered pages, in navigation order.
final List<PageDef> pageRegistry = List<PageDef>.unmodifiable(<PageDef>[
  homePageDef,
  textPageDef,
  imagePageDef,
  clockPageDef,
  settingsPageDef,
]);
