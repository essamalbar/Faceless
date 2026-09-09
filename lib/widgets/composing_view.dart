/// The "signature AI-magic moment": a cinematic, data-agnostic composing
/// screen shown while a song (or, currently, a legacy video run) is being
/// generated. Mirrors
/// `docs/superpowers/specs/redesign-artboards/DirectionA-Composing.dc.html`:
/// an alive [ArtistBadge] with a champagne halo, an [Eyebrow] ("now"), an
/// [EditorialHeading] with a champagne accent word, an optional
/// "artist · title" subtitle, a [LivingWaveform], a [StepList] of the
/// generation stages, a footer ETA note, and an optional quiet cancel
/// action.
///
/// Deliberately generic — it takes plain strings/[StepItem]s rather than a
/// [RunSummary]/`SongSummary`, so any screen with an in-progress generation
/// state can drop it in. See `lib/screens/run_detail_screen.dart` for the
/// current consumer and its status→[StepItem] mapping.
library;

import 'package:flutter/material.dart';

import '../l10n/l10n.dart';
import '../theme.dart';
import '../ui/primitives.dart';

class ComposingView extends StatelessWidget {
  /// Single-letter (or grapheme) monogram for the hero [ArtistBadge].
  final String monogram;

  /// Artist name shown before the title, separated by " · ". Omitted
  /// (along with the separator) when null/empty.
  final String? artistName;

  /// Song/story title shown in the subtitle line.
  final String? title;

  /// Ordered generation stages to render in the [StepList].
  final List<StepItem> steps;

  /// Called when the user taps the quiet cancel action. Null hides it.
  final VoidCallback? onCancel;

  /// Disables the cancel action while a cancel request is in flight.
  final bool busy;

  const ComposingView({
    super.key,
    required this.monogram,
    this.artistName,
    this.title,
    required this.steps,
    this.onCancel,
    this.busy = false,
  });

  @override
  Widget build(BuildContext context) {
    final l = context.l10n;
    final artist = artistName?.trim();
    final t = title?.trim();
    final subtitleParts = [
      if (artist != null && artist.isNotEmpty) artist,
      if (t != null && t.isNotEmpty) t,
    ];
    final subtitle =
        subtitleParts.isEmpty ? null : subtitleParts.join(' · ');

    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        ArtistBadge(monogram: monogram, alive: true, size: 88),
        const SizedBox(height: 22),
        Eyebrow(l.composingEyebrow),
        const SizedBox(height: 12),
        EditorialHeading(
          l.composingHeading,
          size: 28,
          accentLast: true,
          textAlign: TextAlign.center,
        ),
        if (subtitle != null) ...[
          const SizedBox(height: 8),
          Text(
            subtitle,
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: FacelessTheme.textSecondary,
              fontSize: 13.5,
            ),
          ),
        ],
        const SizedBox(height: 32),
        const LivingWaveform(animate: true, height: 56),
        const SizedBox(height: 32),
        StepList(steps),
        const SizedBox(height: 22),
        Row(
          mainAxisSize: MainAxisSize.min,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.schedule, size: 15, color: FacelessTheme.faint),
            const SizedBox(width: 8),
            Flexible(
              child: Text(
                l.composingFooterEta,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: FacelessTheme.faint,
                  fontSize: 12.5,
                ),
              ),
            ),
          ],
        ),
        if (onCancel != null) ...[
          const SizedBox(height: 16),
          TextButton.icon(
            onPressed: busy ? null : onCancel,
            style: TextButton.styleFrom(
              foregroundColor: FacelessTheme.textSecondary,
            ),
            icon: const Icon(Icons.delete_forever, size: 18),
            label: Text(l.runDetailCancelDiscard),
          ),
        ],
      ],
    );
  }
}
