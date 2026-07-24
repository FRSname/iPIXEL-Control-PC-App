/// The Text feature surface.
///
/// Renders a message with a sprite font and sends it to the panel as an image —
/// static or scrolling. Everything goes through the shared [SpriteSender] and
/// the app-wide `activeDisplayTaskProvider`, so starting a text display stops
/// whatever was previously driving the panel.
///
/// ## Colour controls
///
/// Only a **background** colour is offered. The sprite pipeline does not recolour
/// glyphs — each glyph keeps its sheet's baked-in colour (see
/// `render/sprite_font.dart`). Glyph colour is therefore chosen by picking a
/// coloured sheet variant in the font dropdown (e.g. "Text White",
/// "Text Yellow"), not by a text-colour control that would have nothing real to
/// drive in the image path.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:ipixel_controller/ble/device_session.dart';
import 'package:ipixel_controller/ble/providers.dart';
import 'package:ipixel_controller/display/display_task.dart';
import 'package:ipixel_controller/display/providers.dart';
import 'package:ipixel_controller/display/sprite_font_registry.dart';
import 'package:ipixel_controller/display/sprite_sender.dart';
import 'package:ipixel_controller/features/text/color_field.dart';
import 'package:ipixel_controller/render/sprite_font.dart';
import 'package:ipixel_controller/ui/preview/preview_provider.dart';
import 'package:ipixel_controller/ui/widgets/panel_preview.dart';

/// How the text is driven onto the panel.
enum TextMode {
  static('Static'),
  scrollLeft('Scroll left'),
  scrollRight('Scroll right');

  const TextMode(this.label);
  final String label;

  bool get isScroll => this != TextMode.static;
}

class TextFeaturePage extends ConsumerStatefulWidget {
  const TextFeaturePage({super.key});

  @override
  ConsumerState<TextFeaturePage> createState() => _TextFeaturePageState();
}

class _TextFeaturePageState extends ConsumerState<TextFeaturePage> {
  final TextEditingController _textController = TextEditingController(
    text: 'Hello World',
  );
  String _bgColor = '#000000';
  String? _fontName;
  TextMode _mode = TextMode.static;
  int _speed = 50;
  bool _sending = false;

  @override
  void dispose() {
    _textController.dispose();
    super.dispose();
  }

  /// The effective font: the user's pick, or the first available font.
  String? _effectiveFont(List<String> names) {
    final picked = _fontName;
    if (picked != null && names.contains(picked)) return picked;
    return names.isNotEmpty ? names.first : null;
  }

  Future<void> _send(List<String> fontNames) async {
    final text = _textController.text.trim();
    if (text.isEmpty) {
      _showError('Enter some text first.');
      return;
    }
    final fonts = ref.read(spriteFontRegistryProvider).value;
    final fontName = _effectiveFont(fontNames);
    if (fonts == null || fontName == null) {
      _showError('No sprite font available.');
      return;
    }
    final status =
        ref.read(connectionStatusProvider).value ??
        BleConnectionStatus.disconnected;
    if (status != BleConnectionStatus.ready) {
      _showError('Connect to a panel first.');
      return;
    }

    final sender = SpriteSender(
      fonts: fonts,
      send: ref.read(panelImageSinkProvider),
      publishFrame: ref.read(panelPreviewProvider.notifier).setFrame,
    );
    final task = switch (_mode) {
      TextMode.static => sender.staticText(
        text: text,
        fontName: fontName,
        bgColor: _bgColor,
      ),
      TextMode.scrollLeft => sender.scrollText(
        text: text,
        fontName: fontName,
        bgColor: _bgColor,
        speed: _speed,
        reverse: false,
      ),
      TextMode.scrollRight => sender.scrollText(
        text: text,
        fontName: fontName,
        bgColor: _bgColor,
        speed: _speed,
        reverse: true,
      ),
    };

    setState(() => _sending = true);
    try {
      await ref.read(activeDisplayTaskProvider.notifier).run(task);
    } on SpriteRenderException catch (error) {
      _showError(error.message);
    } on Exception {
      _showError('Could not send to the panel.');
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  /// Updates the stored speed and, if a scroll is already driving the panel,
  /// retunes it live so the slider takes effect on the next frame instead of
  /// only on the next Send. `updateScrollSpeed` is a no-op for a static task, so
  /// it is safe to call whenever the display slot is active.
  void _onSpeedChanged(int speed) {
    setState(() => _speed = speed);
    if (ref.read(activeDisplayTaskProvider)) {
      ref.read(activeDisplayTaskProvider.notifier).updateScrollSpeed(speed);
    }
  }

  void _showError(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    // Stop the active display task when the panel drops, so a scroll loop does
    // not spin against a dead session.
    ref.listen(connectionStatusProvider, (previous, next) {
      if (next.value == BleConnectionStatus.disconnected) {
        unawaited(ref.read(activeDisplayTaskProvider.notifier).clear());
      }
    });

    final fontsAsync = ref.watch(spriteFontRegistryProvider);
    final status =
        ref.watch(connectionStatusProvider).value ??
        BleConnectionStatus.disconnected;
    final connected = status == BleConnectionStatus.ready;

    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Text', style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 16),
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 512),
              child: const PanelPreview(),
            ),
            const SizedBox(height: 24),
            _MessageCard(controller: _textController),
            const SizedBox(height: 16),
            _SectionCard(
              title: 'Background',
              child: ColorField(
                label: 'Colour',
                value: _bgColor,
                onChanged: (hex) => setState(() => _bgColor = hex),
              ),
            ),
            const SizedBox(height: 16),
            _FontCard(
              fontsAsync: fontsAsync,
              selected: _fontName,
              resolve: _effectiveFont,
              onChanged: (name) => setState(() => _fontName = name),
            ),
            const SizedBox(height: 16),
            _AnimationCard(
              mode: _mode,
              speed: _speed,
              onModeChanged: (mode) => setState(() => _mode = mode),
              onSpeedChanged: _onSpeedChanged,
            ),
            const SizedBox(height: 20),
            _SendButton(
              enabled: connected && !_sending,
              busy: _sending,
              onPressed: () => _send(fontsAsync.value?.fontNames ?? const []),
            ),
            if (!connected) ...[
              const SizedBox(height: 8),
              Text(
                'Connect to a panel to send.',
                style: Theme.of(context).textTheme.bodySmall,
                textAlign: TextAlign.center,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _SectionCard extends StatelessWidget {
  const _SectionCard({required this.title, required this.child});

  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            child,
          ],
        ),
      ),
    );
  }
}

class _MessageCard extends StatelessWidget {
  const _MessageCard({required this.controller});

  final TextEditingController controller;

  @override
  Widget build(BuildContext context) {
    return _SectionCard(
      title: 'Message',
      child: TextField(
        controller: controller,
        minLines: 1,
        maxLines: 3,
        decoration: const InputDecoration(
          hintText: 'Hello World',
          border: OutlineInputBorder(),
        ),
      ),
    );
  }
}

class _FontCard extends StatelessWidget {
  const _FontCard({
    required this.fontsAsync,
    required this.selected,
    required this.resolve,
    required this.onChanged,
  });

  final AsyncValue<SpriteFontService> fontsAsync;
  final String? selected;
  final String? Function(List<String>) resolve;
  final ValueChanged<String?> onChanged;

  @override
  Widget build(BuildContext context) {
    return _SectionCard(
      title: 'Sprite font',
      child: fontsAsync.when(
        // A static placeholder (not an animated spinner) so a slow/absent
        // config store never blocks `pumpAndSettle` in tests or spins forever.
        loading: () => Text(
          'Loading sprite fonts…',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        error: (error, _) => Text(
          'Could not load sprite fonts.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        data: (service) {
          final names = service.fontNames;
          if (names.isEmpty) {
            return const Text('No sprite fonts installed.');
          }
          final value = resolve(names);
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              DropdownButtonFormField<String>(
                initialValue: value,
                isExpanded: true,
                decoration: const InputDecoration(border: OutlineInputBorder()),
                items: [
                  for (final name in names)
                    DropdownMenuItem<String>(value: name, child: Text(name)),
                ],
                onChanged: onChanged,
              ),
              const SizedBox(height: 8),
              Text(
                'Glyph colour comes from the sheet — pick a white or yellow '
                'variant for coloured text. Background colour is set above.',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          );
        },
      ),
    );
  }
}

class _AnimationCard extends StatelessWidget {
  const _AnimationCard({
    required this.mode,
    required this.speed,
    required this.onModeChanged,
    required this.onSpeedChanged,
  });

  final TextMode mode;
  final int speed;
  final ValueChanged<TextMode> onModeChanged;
  final ValueChanged<int> onSpeedChanged;

  @override
  Widget build(BuildContext context) {
    return _SectionCard(
      title: 'Animation',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SegmentedButton<TextMode>(
            segments: [
              for (final option in TextMode.values)
                ButtonSegment<TextMode>(
                  value: option,
                  label: Text(option.label),
                ),
            ],
            selected: <TextMode>{mode},
            onSelectionChanged: (selection) => onModeChanged(selection.first),
          ),
          if (mode.isScroll) ...[
            const SizedBox(height: 16),
            Row(
              children: [
                Text('Speed', style: Theme.of(context).textTheme.labelLarge),
                Expanded(
                  child: Slider(
                    value: speed.toDouble(),
                    min: 1,
                    max: 100,
                    divisions: 99,
                    label: '$speed',
                    onChanged: (value) => onSpeedChanged(value.round()),
                  ),
                ),
                SizedBox(
                  width: 32,
                  child: Text('$speed', textAlign: TextAlign.end),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _SendButton extends StatelessWidget {
  const _SendButton({
    required this.enabled,
    required this.busy,
    required this.onPressed,
  });

  final bool enabled;
  final bool busy;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return FilledButton.icon(
      onPressed: enabled ? onPressed : null,
      icon: busy
          ? const SizedBox(
              width: 18,
              height: 18,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          : const Icon(Icons.send),
      label: const Text('Send to panel'),
    );
  }
}
