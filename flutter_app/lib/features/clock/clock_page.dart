/// The Clock feature surface.
///
/// Three modes, all driven through the shared sprite pipeline and the app-wide
/// `activeDisplayTaskProvider` so starting a clock stops whatever was driving
/// the panel:
///
/// * **Sprite clock** — the current time on a clock-glyph sprite sheet.
/// * **Custom** — the current time from a strftime-like format string.
/// * **Countdown** — time remaining to a target, with a stable zero state.
///
/// The ticking itself lives in [ClockDisplayTask], which sends a frame only when
/// the rendered string changes. Glyph colour comes from the chosen sheet
/// variant; the only colour control here is the background (see the Text page
/// for the same rationale).
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
import 'package:ipixel_controller/features/clock/clock_display_task.dart';
import 'package:ipixel_controller/features/clock/clock_time.dart';
import 'package:ipixel_controller/features/text/color_field.dart';
import 'package:ipixel_controller/render/sprite_font.dart';
import 'package:ipixel_controller/ui/preview/preview_provider.dart';
import 'package:ipixel_controller/ui/widgets/panel_preview.dart';

class ClockFeaturePage extends ConsumerStatefulWidget {
  const ClockFeaturePage({super.key});

  @override
  ConsumerState<ClockFeaturePage> createState() => _ClockFeaturePageState();
}

class _ClockFeaturePageState extends ConsumerState<ClockFeaturePage> {
  ClockMode _mode = ClockMode.sprite;

  // Sprite-clock state.
  bool _showSeconds = false;

  // Custom-format state.
  String _customFormat = kTimeFormats.first;

  // Countdown state.
  final TextEditingController _eventController = TextEditingController(
    text: 'Event',
  );
  late DateTime _target = DateTime.now().add(const Duration(days: 1));
  CountdownFormat _countdownFormat = CountdownFormat.daysHoursMins;

  String _bgColor = '#000000';
  String? _fontName;
  bool _starting = false;

  @override
  void dispose() {
    _eventController.dispose();
    super.dispose();
  }

  /// Fonts whose name marks them as clock-glyph sheets (digits + colon).
  bool _isClockFont(String name) => name.toLowerCase().contains('clock');

  /// The effective font for the current mode: the user's pick if still valid,
  /// otherwise a sensible default — a clock sheet for sprite mode, a text sheet
  /// for the letter-bearing custom/countdown strings.
  String? _effectiveFont(List<String> names) {
    if (names.isEmpty) return null;
    final picked = _fontName;
    if (picked != null && names.contains(picked)) return picked;
    if (_mode == ClockMode.sprite) {
      return names.firstWhere(_isClockFont, orElse: () => names.first);
    }
    return names.firstWhere((n) => !_isClockFont(n), orElse: () => names.first);
  }

  /// Whether the active mode's rendered string changes every second.
  bool get _perSecond => switch (_mode) {
    ClockMode.sprite => _showSeconds,
    ClockMode.custom => customFormatShowsSeconds(_customFormat),
    ClockMode.countdown => countdownShowsSeconds(_countdownFormat),
  };

  String _renderText(DateTime now) => switch (_mode) {
    ClockMode.sprite => formatSpriteClock(now, showSeconds: _showSeconds),
    ClockMode.custom => formatCustomTime(now, _customFormat),
    ClockMode.countdown => formatCountdown(now, _target, _countdownFormat),
  };

  Duration _nextDelay(DateTime now) => _mode == ClockMode.countdown
      ? nextCountdownTickDelay(_target.difference(now), perSecond: _perSecond)
      : nextClockTickDelay(now, perSecond: _perSecond);

  Future<void> _start(List<String> fontNames) async {
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

    final task = ClockDisplayTask(
      fonts: fonts,
      fontName: fontName,
      bgColor: _bgColor,
      send: ref.read(panelImageSinkProvider),
      publishFrame: ref.read(panelPreviewProvider.notifier).setFrame,
      renderText: _renderText,
      nextDelay: _nextDelay,
    );

    setState(() => _starting = true);
    try {
      await ref.read(activeDisplayTaskProvider.notifier).run(task);
    } on SpriteRenderException catch (error) {
      _showError(error.message);
    } on Exception {
      _showError('Could not send to the panel.');
    } finally {
      if (mounted) setState(() => _starting = false);
    }
  }

  Future<void> _stop() => ref.read(activeDisplayTaskProvider.notifier).clear();

  Future<void> _pickTarget() async {
    final date = await showDatePicker(
      context: context,
      initialDate: _target,
      firstDate: DateTime(2000),
      lastDate: DateTime(2100),
    );
    if (date == null || !mounted) return;
    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(_target),
    );
    if (!mounted) return;
    final t = time ?? TimeOfDay.fromDateTime(_target);
    setState(() {
      _target = DateTime(date.year, date.month, date.day, t.hour, t.minute);
    });
  }

  void _showError(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    // Stop the active task when the panel drops, so a tick loop does not spin
    // against a dead session.
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
            Text('Clock', style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 16),
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 512),
              child: const PanelPreview(),
            ),
            const SizedBox(height: 24),
            _ModeCard(
              mode: _mode,
              onModeChanged: (mode) => setState(() => _mode = mode),
            ),
            const SizedBox(height: 16),
            _modeCard(),
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
            const SizedBox(height: 20),
            _ActionRow(
              enabled: connected && !_starting,
              busy: _starting,
              onStart: () =>
                  _start(fontsAsync.value?.fontNames ?? const <String>[]),
              onStop: () => unawaited(_stop()),
            ),
            if (!connected) ...[
              const SizedBox(height: 8),
              Text(
                'Connect to a panel to show the clock.',
                style: Theme.of(context).textTheme.bodySmall,
                textAlign: TextAlign.center,
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _modeCard() => switch (_mode) {
    ClockMode.sprite => _SpriteCard(
      showSeconds: _showSeconds,
      onChanged: (value) => setState(() => _showSeconds = value),
    ),
    ClockMode.custom => _CustomCard(
      format: _customFormat,
      onChanged: (value) => setState(() => _customFormat = value),
    ),
    ClockMode.countdown => _CountdownCard(
      eventController: _eventController,
      target: _target,
      format: _countdownFormat,
      onPickTarget: _pickTarget,
      onFormatChanged: (value) => setState(() => _countdownFormat = value),
    ),
  };
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

class _ModeCard extends StatelessWidget {
  const _ModeCard({required this.mode, required this.onModeChanged});

  final ClockMode mode;
  final ValueChanged<ClockMode> onModeChanged;

  @override
  Widget build(BuildContext context) {
    return _SectionCard(
      title: 'Mode',
      child: SegmentedButton<ClockMode>(
        segments: [
          for (final option in ClockMode.values)
            ButtonSegment<ClockMode>(value: option, label: Text(option.label)),
        ],
        selected: <ClockMode>{mode},
        onSelectionChanged: (selection) => onModeChanged(selection.first),
      ),
    );
  }
}

class _SpriteCard extends StatelessWidget {
  const _SpriteCard({required this.showSeconds, required this.onChanged});

  final bool showSeconds;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    return _SectionCard(
      title: 'Sprite clock',
      child: SwitchListTile(
        contentPadding: EdgeInsets.zero,
        title: const Text('Show seconds'),
        subtitle: const Text('HH:MM:SS instead of HH:MM'),
        value: showSeconds,
        onChanged: onChanged,
      ),
    );
  }
}

class _CustomCard extends StatelessWidget {
  const _CustomCard({required this.format, required this.onChanged});

  final String format;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return _SectionCard(
      title: 'Custom',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Time format', style: Theme.of(context).textTheme.labelLarge),
          const SizedBox(height: 8),
          DropdownButtonFormField<String>(
            initialValue: format,
            isExpanded: true,
            decoration: const InputDecoration(border: OutlineInputBorder()),
            items: [
              for (final f in kTimeFormats)
                DropdownMenuItem<String>(value: f, child: Text(f)),
            ],
            onChanged: (value) {
              if (value != null) onChanged(value);
            },
          ),
          const SizedBox(height: 8),
          Text(
            'Formats showing seconds (%S) update every second; the rest tick '
            'on the minute.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

class _CountdownCard extends StatelessWidget {
  const _CountdownCard({
    required this.eventController,
    required this.target,
    required this.format,
    required this.onPickTarget,
    required this.onFormatChanged,
  });

  final TextEditingController eventController;
  final DateTime target;
  final CountdownFormat format;
  final VoidCallback onPickTarget;
  final ValueChanged<CountdownFormat> onFormatChanged;

  String get _targetLabel {
    final d = target;
    String two(int v) => v.toString().padLeft(2, '0');
    return '${d.year}-${two(d.month)}-${two(d.day)} '
        '${two(d.hour)}:${two(d.minute)}';
  }

  @override
  Widget build(BuildContext context) {
    return _SectionCard(
      title: 'Countdown',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          TextField(
            controller: eventController,
            decoration: const InputDecoration(
              labelText: 'Event',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: Text(
                  'Target: $_targetLabel',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ),
              OutlinedButton.icon(
                onPressed: onPickTarget,
                icon: const Icon(Icons.event),
                label: const Text('Pick'),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text('Display', style: Theme.of(context).textTheme.labelLarge),
          const SizedBox(height: 8),
          DropdownButtonFormField<CountdownFormat>(
            initialValue: format,
            isExpanded: true,
            decoration: const InputDecoration(border: OutlineInputBorder()),
            items: [
              for (final f in CountdownFormat.values)
                DropdownMenuItem<CountdownFormat>(
                  value: f,
                  child: Text(f.label),
                ),
            ],
            onChanged: (value) {
              if (value != null) onFormatChanged(value);
            },
          ),
        ],
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
                'Sprite-clock needs a clock sheet (digits + colon); custom and '
                'countdown need a text sheet for their letters.',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          );
        },
      ),
    );
  }
}

class _ActionRow extends StatelessWidget {
  const _ActionRow({
    required this.enabled,
    required this.busy,
    required this.onStart,
    required this.onStop,
  });

  final bool enabled;
  final bool busy;
  final VoidCallback onStart;
  final VoidCallback onStop;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: FilledButton.icon(
            onPressed: enabled ? onStart : null,
            icon: busy
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.play_arrow),
            label: const Text('Show clock'),
          ),
        ),
        const SizedBox(width: 12),
        OutlinedButton.icon(
          onPressed: enabled ? onStop : null,
          icon: const Icon(Icons.stop),
          label: const Text('Stop'),
        ),
      ],
    );
  }
}
