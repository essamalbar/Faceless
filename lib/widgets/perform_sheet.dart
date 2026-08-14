/// "Make me sing this" — modal bottom sheet that turns a photo into a
/// 30-second lip-synced performance video of the song's hook. Pure UI +
/// one API call (`FacelessApiClient.performSong`); the caller (song detail
/// screen) owns polling `performStatus` afterwards.
library;

import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../api/client.dart';
import '../theme.dart';
import '../ui/brand.dart';

/// Test seam: production code leaves [pickImage] null and falls back to a
/// real `ImagePicker`; widget tests inject a fake that returns bytes
/// directly (via `XFile.fromData`) so no platform channel is touched.
typedef ImagePickerFn = Future<XFile?> Function(ImageSource source);

class PerformSheet extends StatefulWidget {
  final FacelessApiClient client;
  final String runId;
  // Credits actually charged for the render (from the backend config), shown
  // on the cost card so the disclosed price can't drift from what's charged.
  final int performCredits;
  final ImagePickerFn? pickImage;

  const PerformSheet({
    super.key,
    required this.client,
    required this.runId,
    this.performCredits = 3,
    this.pickImage,
  });

  @override
  State<PerformSheet> createState() => _PerformSheetState();
}

class _PerformSheetState extends State<PerformSheet> {
  XFile? _photo;
  Uint8List? _photoBytes;
  bool _attested = false;
  bool _submitting = false;
  String? _error;

  bool get _canApprove => _photoBytes != null && _attested && !_submitting;

  Future<XFile?> _pick(ImageSource source) {
    final fn = widget.pickImage;
    if (fn != null) return fn(source);
    return ImagePicker().pickImage(
      source: source,
      maxWidth: 2000,
      imageQuality: 90,
    );
  }

  Future<void> _pickFrom(ImageSource source) async {
    try {
      final x = await _pick(source);
      if (x == null) return; // user canceled the picker
      final bytes = await x.readAsBytes();
      if (!mounted) return;
      setState(() {
        _photo = x;
        _photoBytes = bytes;
        _error = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = "Couldn't read that photo: $e");
    }
  }

  Future<void> _approve() async {
    final bytes = _photoBytes;
    if (bytes == null || !_attested) return;
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final status = await widget.client.performSong(
        runId: widget.runId,
        photoBytes: bytes,
        filename: (_photo?.name.isNotEmpty ?? false)
            ? _photo!.name
            : 'photo.jpg',
        ownershipAttested: true,
      );
      if (!mounted) return;
      Navigator.of(context).pop(status.isEmpty ? 'rendering' : status);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _error = '$e';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      // Block the scrim-tap / back-swipe dismiss while a submit is in
      // flight — performSong already charges server-side by the time this
      // sheet would pop, so an accidental dismiss must not let the parent
      // think nothing happened and re-offer the (paid) action mid-render.
      canPop: !_submitting,
      child: SafeArea(
        child: Padding(
          padding: EdgeInsets.only(
            bottom: MediaQuery.viewInsetsOf(context).bottom,
            left: 16,
            right: 16,
            top: 16,
          ),
          child: GlassCard(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        '✨ Make me sing this',
                        style: FacelessTheme.display(size: 20),
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.close),
                      onPressed: _submitting
                          ? null
                          : () => Navigator.of(context).pop(),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  "Pick a photo and we'll render a 30-second lip-synced "
                  'video of you singing the hook.',
                  style: TextStyle(
                    color: FacelessTheme.textSecondary,
                    fontSize: 13,
                    height: 1.35,
                  ),
                ),
                const SizedBox(height: 18),
                Center(
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(16),
                    child: _photoBytes != null
                        ? Image.memory(
                            _photoBytes!,
                            width: 140,
                            height: 140,
                            fit: BoxFit.cover,
                            errorBuilder: (ctx, err, stack) => Container(
                              width: 140,
                              height: 140,
                              color: FacelessTheme.surface2,
                              child: const Icon(
                                Icons.broken_image_outlined,
                                size: 40,
                                color: FacelessTheme.faint,
                              ),
                            ),
                          )
                        : Container(
                            width: 140,
                            height: 140,
                            decoration: BoxDecoration(
                              color: FacelessTheme.surface2,
                              borderRadius: BorderRadius.circular(16),
                              border: Border.all(color: FacelessTheme.border),
                            ),
                            child: const Icon(
                              Icons.face_retouching_natural,
                              size: 40,
                              color: FacelessTheme.faint,
                            ),
                          ),
                  ),
                ),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        icon: const Icon(Icons.photo_library_outlined),
                        label: const Text('Gallery'),
                        onPressed: _submitting
                            ? null
                            : () => _pickFrom(ImageSource.gallery),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: OutlinedButton.icon(
                        icon: const Icon(Icons.photo_camera_outlined),
                        label: const Text('Camera'),
                        onPressed: _submitting
                            ? null
                            : () => _pickFrom(ImageSource.camera),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  controlAffinity: ListTileControlAffinity.leading,
                  dense: true,
                  value: _attested,
                  onChanged: _submitting
                      ? null
                      : (v) => setState(() => _attested = v ?? false),
                  title: const Text(
                    'This is me / I have the right to use this face.',
                    style: TextStyle(fontSize: 13),
                  ),
                ),
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: FacelessTheme.glass,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: FacelessTheme.border),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.bolt, size: 18, color: FacelessTheme.accent),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          '30-second hook video · ${widget.performCredits} '
                          '${widget.performCredits == 1 ? "credit" : "credits"}'
                          ' · charged on approve',
                          style: const TextStyle(
                            fontSize: 12.5,
                            color: FacelessTheme.textSecondary,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                if (_error != null) ...[
                  const SizedBox(height: 10),
                  Text(
                    _error!,
                    style: const TextStyle(
                      color: FacelessTheme.danger,
                      fontSize: 12,
                    ),
                  ),
                ],
                const SizedBox(height: 18),
                GradientButton(
                  label: 'Approve & render',
                  icon: Icons.auto_awesome,
                  loading: _submitting,
                  expand: true,
                  onPressed: _canApprove ? _approve : null,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
