/// The Image feature surface.
///
/// Picks an image (or animated GIF), fits it to the 64x16 panel by letterbox or
/// crop, previews the result live, and sends it. A static image is a single
/// [DisplayTask] send; a GIF loops its frames through a timed [DisplayTask].
/// Everything routes through the shared `activeDisplayTaskProvider`, so starting
/// an image display stops whatever was previously driving the panel.
///
/// ## Fit
///
/// * **Letterbox** scales the whole image inside the panel and pads the rest
///   with the chosen background colour.
/// * **Crop** scales the image to cover the panel and centre-crops the overflow.
///
/// The background colour only shows through in letterbox mode (crop fills the
/// panel), but it is offered for both so switching modes needs no re-pick.
library;

import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image/image.dart' as img;

import 'package:ipixel_controller/ble/device_session.dart';
import 'package:ipixel_controller/ble/providers.dart';
import 'package:ipixel_controller/display/display_task.dart';
import 'package:ipixel_controller/display/providers.dart';
import 'package:ipixel_controller/features/image/gif_frames.dart';
import 'package:ipixel_controller/features/image/image_fit.dart';
import 'package:ipixel_controller/features/image/image_picker_service.dart';
import 'package:ipixel_controller/features/image/image_sender.dart';
import 'package:ipixel_controller/features/text/color_field.dart';
import 'package:ipixel_controller/render/panel_image.dart';
import 'package:ipixel_controller/ui/preview/preview_provider.dart';
import 'package:ipixel_controller/ui/widgets/panel_preview.dart';

class ImageFeaturePage extends ConsumerStatefulWidget {
  const ImageFeaturePage({super.key});

  @override
  ConsumerState<ImageFeaturePage> createState() => _ImageFeaturePageState();
}

class _ImageFeaturePageState extends ConsumerState<ImageFeaturePage> {
  String? _sourceName;
  bool _isGif = false;

  /// Cached decode of the current pick. Exactly one is non-null when an image is
  /// loaded: [_decodedFrames] for an animated GIF, [_decodedImage] for a static
  /// image (or a single-frame GIF). Decoding happens once per pick; fit and
  /// background changes only re-run the cheap fit step over these.
  List<DecodedGifFrame>? _decodedFrames;
  img.Image? _decodedImage;

  PanelFit _fit = PanelFit.letterbox;
  String _bgColor = '#000000';
  bool _picking = false;
  bool _sending = false;

  bool get _hasImage => _decodedFrames != null || _decodedImage != null;

  Future<void> _pick() async {
    setState(() => _picking = true);
    try {
      final picked = await ref.read(panelImagePickerProvider).pickImage();
      if (picked == null) return;
      _loadPicked(picked);
    } on Exception {
      _showError('Could not open that image.');
    } finally {
      if (mounted) setState(() => _picking = false);
    }
  }

  /// Decodes [picked] once, deciding static-vs-GIF, caches the raw frames, and
  /// publishes a fitted preview frame.
  void _loadPicked(PickedImage picked) {
    try {
      if (picked.name.toLowerCase().endsWith('.gif')) {
        final frames = decodeGifFrames(picked.bytes);
        if (frames.length > 1) {
          setState(() {
            _sourceName = picked.name;
            _isGif = true;
            _decodedFrames = frames;
            _decodedImage = null;
          });
          _publishPreview(
            fitGifFrames(frames, fit: _fit, bgColor: _bgColor).first.png,
          );
          return;
        }
        // A single-frame GIF is really a static image; reuse its one already
        // decoded frame instead of decoding the bytes a second time.
        _setStatic(picked.name, frames.first.image);
        return;
      }
      _setStatic(picked.name, decodePanelImage(picked.bytes));
    } on ImageDecodeException catch (error) {
      _showError(error.message);
    }
  }

  /// Caches a decoded static [image] and publishes its fitted preview.
  void _setStatic(String name, img.Image image) {
    setState(() {
      _sourceName = name;
      _isGif = false;
      _decodedFrames = null;
      _decodedImage = image;
    });
    _publishPreview(
      fitDecodedImageToPanelPng(image, fit: _fit, bgColor: _bgColor),
    );
  }

  /// Re-fits the cached decode after a fit/background change.
  ///
  /// Pure fit + encode over the already-decoded frames — no re-decode — so it
  /// cannot raise an [ImageDecodeException].
  void _recompute() {
    final frames = _decodedFrames;
    final image = _decodedImage;
    if (frames != null) {
      _publishPreview(
        fitGifFrames(frames, fit: _fit, bgColor: _bgColor).first.png,
      );
    } else if (image != null) {
      _publishPreview(
        fitDecodedImageToPanelPng(image, fit: _fit, bgColor: _bgColor),
      );
    }
  }

  void _publishPreview(Uint8List png) {
    ref.read(panelPreviewProvider.notifier).setFrame(png);
  }

  void _onFitChanged(PanelFit fit) {
    setState(() => _fit = fit);
    _recompute();
  }

  void _onBgChanged(String hex) {
    setState(() => _bgColor = hex);
    _recompute();
  }

  Future<void> _send() async {
    final status =
        ref.read(connectionStatusProvider).value ??
        BleConnectionStatus.disconnected;
    if (status != BleConnectionStatus.ready) {
      _showError('Connect to a panel first.');
      return;
    }

    final sender = ImageSender(
      send: ref.read(panelImageSinkProvider),
      publishFrame: ref.read(panelPreviewProvider.notifier).setFrame,
    );
    // Fit the cached decode — no re-decode, so this cannot fail to decode.
    final DisplayTask task;
    if (_decodedFrames case final frames?) {
      task = sender.gifLoop(fitGifFrames(frames, fit: _fit, bgColor: _bgColor));
    } else if (_decodedImage case final image?) {
      task = sender.staticImage(
        fitDecodedImageToPanelPng(image, fit: _fit, bgColor: _bgColor),
      );
    } else {
      _showError('Pick an image first.');
      return;
    }

    setState(() => _sending = true);
    try {
      await ref.read(activeDisplayTaskProvider.notifier).run(task);
    } on Exception {
      _showError('Could not send to the panel.');
    } finally {
      if (mounted) setState(() => _sending = false);
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
    // Stop the active display task when the panel drops, so a GIF loop does not
    // spin against a dead session.
    ref.listen(connectionStatusProvider, (previous, next) {
      if (next.value == BleConnectionStatus.disconnected) {
        unawaited(ref.read(activeDisplayTaskProvider.notifier).clear());
      }
    });

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
            Text('Image', style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 16),
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 512),
              child: const PanelPreview(),
            ),
            const SizedBox(height: 24),
            _SourceCard(
              fileName: _sourceName,
              isGif: _isGif,
              gifFrameCount: _decodedFrames?.length ?? 0,
              picking: _picking,
              onPick: _pick,
            ),
            const SizedBox(height: 16),
            _FitCard(fit: _fit, onChanged: _onFitChanged),
            const SizedBox(height: 16),
            _SectionCard(
              title: 'Background',
              child: ColorField(
                label: 'Colour',
                value: _bgColor,
                onChanged: _onBgChanged,
              ),
            ),
            const SizedBox(height: 20),
            _SendButton(
              enabled: connected && _hasImage && !_sending,
              busy: _sending,
              onPressed: _send,
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

class _SourceCard extends StatelessWidget {
  const _SourceCard({
    required this.fileName,
    required this.isGif,
    required this.gifFrameCount,
    required this.picking,
    required this.onPick,
  });

  final String? fileName;
  final bool isGif;
  final int gifFrameCount;
  final bool picking;
  final VoidCallback onPick;

  @override
  Widget build(BuildContext context) {
    final subtitle = switch (fileName) {
      null => 'No image chosen yet.',
      final name when isGif => '$name — animated GIF, $gifFrameCount frames',
      final name => name,
    };
    return _SectionCard(
      title: 'Source',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(subtitle, style: Theme.of(context).textTheme.bodyMedium),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: picking ? null : onPick,
            icon: picking
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.folder_open),
            label: const Text('Pick image or GIF'),
          ),
        ],
      ),
    );
  }
}

class _FitCard extends StatelessWidget {
  const _FitCard({required this.fit, required this.onChanged});

  final PanelFit fit;
  final ValueChanged<PanelFit> onChanged;

  @override
  Widget build(BuildContext context) {
    return _SectionCard(
      title: 'Fit',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SegmentedButton<PanelFit>(
            segments: const <ButtonSegment<PanelFit>>[
              ButtonSegment<PanelFit>(
                value: PanelFit.letterbox,
                label: Text('Letterbox'),
                icon: Icon(Icons.fit_screen),
              ),
              ButtonSegment<PanelFit>(
                value: PanelFit.crop,
                label: Text('Crop'),
                icon: Icon(Icons.crop),
              ),
            ],
            selected: <PanelFit>{fit},
            onSelectionChanged: (selection) => onChanged(selection.first),
          ),
          const SizedBox(height: 8),
          Text(
            fit == PanelFit.letterbox
                ? 'Whole image shown, padded with the background colour.'
                : 'Image fills the panel; the overflow is centre-cropped.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
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
