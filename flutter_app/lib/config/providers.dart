import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'config_store.dart';

/// Provides the production [ConfigStore], rooted at the OS application-support
/// directory.
///
/// Override this in tests with a store rooted at a temp directory, e.g.:
///
/// ```dart
/// ProviderScope(
///   overrides: [
///     configStoreProvider.overrideWith((ref) async => ConfigStore(tempDir)),
///   ],
///   child: ...,
/// );
/// ```
final configStoreProvider = FutureProvider<ConfigStore>((ref) {
  return ConfigStore.forApplicationSupport();
});
