/// Responsive app shell.
///
/// Wide (desktop/tablet) → [NavigationRail] on the left; narrow (phone) →
/// [NavigationBar] at the bottom. The connection bar pins to the top in both
/// layouts, and the guard's coalesced error stream is surfaced as a
/// non-modal [SnackBar].
///
/// Pages are held in an [IndexedStack] built once, so each page instance
/// persists across tab switches — in-progress form state on the S7-S9 feature
/// pages survives navigation instead of being torn down and rebuilt.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:ipixel_controller/ble/providers.dart';
import 'package:ipixel_controller/ui/pages/page_def.dart';
import 'package:ipixel_controller/ui/pages/page_registry.dart';
import 'package:ipixel_controller/ui/widgets/connection_bar.dart';

/// Width at or above which the rail layout is used instead of the bottom bar.
const double kWideLayoutBreakpoint = 720;

class AppShell extends ConsumerStatefulWidget {
  const AppShell({super.key});

  @override
  ConsumerState<AppShell> createState() => _AppShellState();
}

class _AppShellState extends ConsumerState<AppShell> {
  int _index = 0;

  /// Built once so each page's [State] persists across tab switches.
  late final List<Widget> _pages = <Widget>[
    for (final page in pageRegistry) page.builder(),
  ];

  void _select(int index) => setState(() => _index = index);

  @override
  Widget build(BuildContext context) {
    // Surface the guard's coalesced errors non-modally.
    ref.listen(lastErrorProvider, (previous, next) {
      final message = next.value;
      if (message == null) return;
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(message)));
    });

    return LayoutBuilder(
      builder: (context, constraints) {
        final isWide = constraints.maxWidth >= kWideLayoutBreakpoint;
        final body = IndexedStack(index: _index, children: _pages);
        return Scaffold(
          body: SafeArea(
            bottom: false,
            child: Column(
              children: [
                const ConnectionBar(),
                const Divider(height: 1),
                Expanded(
                  child: isWide
                      ? Row(
                          children: [
                            _NavRail(
                              pages: pageRegistry,
                              selectedIndex: _index,
                              onSelected: _select,
                            ),
                            const VerticalDivider(width: 1),
                            Expanded(child: body),
                          ],
                        )
                      : body,
                ),
              ],
            ),
          ),
          bottomNavigationBar: isWide
              ? null
              : _NavBottomBar(
                  pages: pageRegistry,
                  selectedIndex: _index,
                  onSelected: _select,
                ),
        );
      },
    );
  }
}

/// Vertical navigation rail for the wide layout.
class _NavRail extends StatelessWidget {
  const _NavRail({
    required this.pages,
    required this.selectedIndex,
    required this.onSelected,
  });

  final List<PageDef> pages;
  final int selectedIndex;
  final ValueChanged<int> onSelected;

  @override
  Widget build(BuildContext context) {
    return NavigationRail(
      selectedIndex: selectedIndex,
      onDestinationSelected: onSelected,
      labelType: NavigationRailLabelType.all,
      destinations: [
        for (final page in pages)
          NavigationRailDestination(
            icon: Icon(page.icon),
            selectedIcon: Icon(page.selectedIcon),
            label: Text(page.label),
          ),
      ],
    );
  }
}

/// Bottom navigation bar for the narrow layout.
class _NavBottomBar extends StatelessWidget {
  const _NavBottomBar({
    required this.pages,
    required this.selectedIndex,
    required this.onSelected,
  });

  final List<PageDef> pages;
  final int selectedIndex;
  final ValueChanged<int> onSelected;

  @override
  Widget build(BuildContext context) {
    return NavigationBar(
      selectedIndex: selectedIndex,
      onDestinationSelected: onSelected,
      destinations: [
        for (final page in pages)
          NavigationDestination(
            icon: Icon(page.icon),
            selectedIcon: Icon(page.selectedIcon),
            label: page.label,
          ),
      ],
    );
  }
}
