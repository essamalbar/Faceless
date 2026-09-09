/// The "signature AI-magic moment": a cinematic, data-agnostic composing
/// screen shown while a song (or, currently, a legacy video run) is being
/// generated. Mirrors
/// `docs/superpowers/specs/redesign-artboards/DirectionA-Composing.dc.html`:
/// a top-corner cancel link, an alive [ArtistBadge] with a champagne halo,
/// an [Eyebrow] ("now"), an [EditorialHeading] with a champagne accent
/// word, an optional "artist · title" subtitle, a [LivingWaveform], a
/// [StepList] of the generation stages, and a footer ETA note.
///
/// Deliberately generic — it takes plain strings/[StepItem]s and a caller-
/// supplied [cancelLabel] rather than any `RunSummary`/`SongSummary` model
/// or `runDetail*`-flavoured l10n, so any screen with an in-progress
/// generation state can drop it in with its own appropriate copy. See
/// `lib/screens/run_detail_screen.dart` for the current consumer and its
/// status→[StepItem] mapping.
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

  /// Label for the quiet top-corner cancel link (e.g. "Cancel & Discard" /
  /// "إلغاء الأغنية"). Caller-supplied so this widget stays data-agnostic —
  /// null hides the cancel link entirely.
  final String? cancelLabel;

  /// Called when the user taps the cancel link. Ignored when [cancelLabel]
  /// is null.
  final VoidCallback? onCancel;

  /// Disables the cancel action while a cancel request is in flight.
  final bool busy;

  const ComposingView({
    super.key,
    required this.monogram,
    this.artistName,
    this.title,
    required this.steps,
    this.cancelLabel,
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
        // Top-corner cancel link, matching the artboard's "إلغاء" — sits
        // opposite where a brand mark would go, on the directional END side
        // so it lands top-left in RTL (as in the artboard) and top-right in
        // LTR, rather than a fixed physical side.
        if (cancelLabel != null) ...[
          Align(
            alignment: AlignmentDirectional.topEnd,
            child: Opacity(
              opacity: busy ? 0.5 : 1.0,
              child: TextButton(
                onPressed: busy ? null : onCancel,
                style: TextButton.styleFrom(
                  foregroundColor: FacelessTheme.textSecondary,
                  padding: const EdgeInsets.symmetric(
                      horizontal: 4, vertical: 4),
                  minimumSize: Size.zero,
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
                child: Text(
                  cancelLabel!,
                  style: const TextStyle(fontSize: 12.5),
                ),
              ),
            ),
          ),
          const SizedBox(height: 8),
        ],
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
      ],
    );
  }
}
