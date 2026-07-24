/// A compact, dependency-free colour picker for panel background colours.
///
/// Shows a labelled row of preset swatches plus a hex field. Values are the
/// `#RRGGBB` strings the render core expects. Kept intentionally small — the
/// panel only ever needs a solid background fill, and glyph colour comes from
/// the chosen sprite-sheet variant, not from a colour control here.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'package:ipixel_controller/render/sprite_font.dart'
    show tryParseHexColor;

/// Common panel background colours offered as one-tap swatches.
const List<String> kPresetColors = <String>[
  '#000000',
  '#FFFFFF',
  '#FF0000',
  '#00FF00',
  '#0000FF',
  '#FFFF00',
  '#00FFFF',
  '#FF00FF',
  '#FF7F00',
];

/// Parses a `#RRGGBB` string to a Flutter [Color], defaulting to black on a
/// malformed value so the swatch preview never crashes mid-edit.
Color colorFromHex(String hex) {
  final parsed = tryParseHexColor(hex);
  if (parsed == null) return const Color(0xFF000000);
  return Color.fromARGB(
    255,
    parsed.r.toInt(),
    parsed.g.toInt(),
    parsed.b.toInt(),
  );
}

class ColorField extends StatefulWidget {
  const ColorField({
    required this.label,
    required this.value,
    required this.onChanged,
    super.key,
  });

  final String label;

  /// Current `#RRGGBB` value.
  final String value;

  /// Called with a normalised `#RRGGBB` string whenever the user picks a valid
  /// colour (swatch tap or a complete hex entry).
  final ValueChanged<String> onChanged;

  @override
  State<ColorField> createState() => _ColorFieldState();
}

class _ColorFieldState extends State<ColorField> {
  late final TextEditingController _hexController = TextEditingController(
    text: widget.value.replaceFirst('#', ''),
  );

  @override
  void didUpdateWidget(ColorField oldWidget) {
    super.didUpdateWidget(oldWidget);
    final normalised = widget.value.replaceFirst('#', '');
    if (normalised.toUpperCase() != _hexController.text.toUpperCase()) {
      _hexController.text = normalised;
    }
  }

  @override
  void dispose() {
    _hexController.dispose();
    super.dispose();
  }

  void _select(String hex) {
    final parsed = tryParseHexColor(hex);
    if (parsed == null) return;
    final normalised =
        '#${((parsed.r.toInt() << 16) | (parsed.g.toInt() << 8) | parsed.b.toInt()).toRadixString(16).padLeft(6, '0').toUpperCase()}';
    widget.onChanged(normalised);
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(widget.label, style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(width: 12),
            _CurrentSwatch(value: widget.value),
            const SizedBox(width: 12),
            SizedBox(
              width: 110,
              child: TextField(
                controller: _hexController,
                decoration: const InputDecoration(
                  prefixText: '#',
                  isDense: true,
                  border: OutlineInputBorder(),
                ),
                textCapitalization: TextCapitalization.characters,
                inputFormatters: [
                  LengthLimitingTextInputFormatter(6),
                  FilteringTextInputFormatter.allow(RegExp('[0-9a-fA-F]')),
                ],
                onChanged: (text) {
                  if (text.length == 6 || text.length == 3) _select('#$text');
                },
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final preset in kPresetColors)
              _SwatchButton(
                hex: preset,
                selected: preset.toUpperCase() == widget.value.toUpperCase(),
                onTap: () => _select(preset),
              ),
          ],
        ),
      ],
    );
  }
}

class _CurrentSwatch extends StatelessWidget {
  const _CurrentSwatch({required this.value});

  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 28,
      height: 28,
      decoration: BoxDecoration(
        color: colorFromHex(value),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: Theme.of(context).colorScheme.outline),
      ),
    );
  }
}

class _SwatchButton extends StatelessWidget {
  const _SwatchButton({
    required this.hex,
    required this.selected,
    required this.onTap,
  });

  final String hex;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    // The visible swatch stays compact, but the InkWell fills a 48x48 box so the
    // touch target meets the accessibility minimum.
    return Semantics(
      label: 'Colour $hex',
      selected: selected,
      button: true,
      child: SizedBox(
        width: 48,
        height: 48,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(6),
          child: Center(
            child: Container(
              width: 30,
              height: 30,
              decoration: BoxDecoration(
                color: colorFromHex(hex),
                borderRadius: BorderRadius.circular(6),
                border: Border.all(
                  color: selected
                      ? Theme.of(context).colorScheme.primary
                      : Theme.of(context).colorScheme.outline,
                  width: selected ? 3 : 1,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
