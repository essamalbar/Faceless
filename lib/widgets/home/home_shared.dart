/// Cross-section helpers for the home screen's song widgets — small pieces
/// used by 2+ of `lib/widgets/home/*` (status styling, cover art, section
/// titles). Kept PUBLIC (unlike the old `_Foo` privates in home_screen.dart)
/// so every section file can import them; nothing here fetches data or owns
/// state — it's pure presentation, mirroring the data already handed down
/// from `_HomeScreenState`.
library;

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../../l10n/l10n.dart';
import '../../theme.dart';
import '../../ui/primitives.dart';

/// Presentation-only description of a song/run status: the label (from the
/// existing `homeStatus*` / `statusFailed` l10n keys — unchanged) plus a
/// [StatusKind] for the three states the shared [StatusPill] primitive can
/// render. `failed` and unknown codes have no [StatusKind] (the primitive
/// only models ready/composing/review) — those fall back to [color]/[icon]
/// via [SongStatusIndicator] so a failure is never mistaken for "composing"
/// or "ready".
class SongStatusStyle {
  final String label;
  final Color color;
  final IconData icon;
  final bool working; // true for every in-flight ("composing") state
  final StatusKind? kind;
  const SongStatusStyle(
    this.label,
    this.color,
    this.icon, {
    this.working = false,
    this.kind,
  });
}

/// Same status → style mapping as the pre-redesign `_songStatusStyle` —
/// labels/logic unchanged, only the [kind] tag is new (drives which visual
/// primitive [SongStatusIndicator] picks).
SongStatusStyle songStatusStyle(AppLocalizations l10n, String status) {
  switch (status) {
    case 'writing_lyrics':
      return SongStatusStyle(
          l10n.homeStatusWritingLyrics, FacelessTheme.info, Icons.edit_note,
          working: true, kind: StatusKind.composing);
    case 'awaiting_approval':
      return SongStatusStyle(l10n.homeStatusReviewApprove,
          FacelessTheme.accent, Icons.play_circle_fill,
          kind: StatusKind.review);
    case 'approved':
    case 'generating_song':
      return SongStatusStyle(
          l10n.homeStatusComposing, FacelessTheme.info, Icons.autorenew,
          working: true, kind: StatusKind.composing);
    case 'generating_cover':
      return SongStatusStyle(
          l10n.homeStatusDesigningCover, FacelessTheme.info, Icons.autorenew,
          working: true, kind: StatusKind.composing);
    case 'detecting_beats':
      return SongStatusStyle(
          l10n.homeStatusSyncingBeat, FacelessTheme.info, Icons.autorenew,
          working: true, kind: StatusKind.composing);
    case 'aligning':
      return SongStatusStyle(
          l10n.homeStatusSyncingLyrics, FacelessTheme.info, Icons.autorenew,
          working: true, kind: StatusKind.composing);
    case 'assembling':
      return SongStatusStyle(
          l10n.homeStatusRendering, FacelessTheme.info, Icons.autorenew,
          working: true, kind: StatusKind.composing);
    case 'complete':
      return SongStatusStyle(
          l10n.homeStatusReady, FacelessTheme.success, Icons.check_circle,
          kind: StatusKind.ready);
    case 'failed':
      return SongStatusStyle(
          l10n.statusFailed, FacelessTheme.danger, Icons.error_outline);
    default:
      // Unknown codes are pretty-printed raw — they're debug text by definition.
      final pretty = status.isEmpty
          ? l10n.homeStatusPending
          : (status[0].toUpperCase() + status.substring(1)).replaceAll('_', ' ');
      return SongStatusStyle(pretty, FacelessTheme.textSecondary, Icons.circle);
  }
}

/// Status indicator for a song row/card: ready/composing/review map onto the
/// shared [StatusPill] primitive; failed/unknown (no [StatusKind]) fall back
/// to a small color+icon chip.
class SongStatusIndicator extends StatelessWidget {
  final SongStatusStyle style;
  final bool compact; // smaller chip for overlay use (e.g. recent tiles)
  const SongStatusIndicator({super.key, required this.style, this.compact = false});

  @override
  Widget build(BuildContext context) {
    final kind = style.kind;
    if (kind != null) {
      return StatusPill(label: style.label, kind: kind);
    }
    return Container(
      padding: EdgeInsets.symmetric(
          horizontal: compact ? 7 : 9, vertical: compact ? 3 : 4),
      decoration: BoxDecoration(
        color: style.color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(style.icon, size: compact ? 11 : 13, color: style.color),
          SizedBox(width: compact ? 4 : 6),
          Text(style.label,
              style: TextStyle(
                  color: style.color,
                  fontSize: compact ? 11 : 12,
                  fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}

/// Section header used above the Artists / Recent / Your songs rows.
class SongSectionTitle extends StatelessWidget {
  final String title;
  final String trailing;
  const SongSectionTitle({super.key, required this.title, required this.trailing});
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(18, 18, 18, 10),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(title,
                style: const TextStyle(
                    color: FacelessTheme.textPrimary,
                    fontSize: 17,
                    fontWeight: FontWeight.w700)),
            Text(trailing,
                style: const TextStyle(
                    color: FacelessTheme.textSecondary, fontSize: 13)),
          ],
        ),
      );
}

class SongThumbPlaceholder extends StatelessWidget {
  const SongThumbPlaceholder({super.key});
  @override
  Widget build(BuildContext context) => Container(
        color: FacelessTheme.surface2,
        child: Icon(Icons.music_note,
            color: FacelessTheme.accent.withValues(alpha: 0.7), size: 26),
      );
}

/// Cover image loaded from the token-bearing cover-URL future, with a
/// branded placeholder while loading / on error.
class SongCover extends StatelessWidget {
  final Future<Uri> future;
  final BoxFit fit;
  const SongCover({super.key, required this.future, this.fit = BoxFit.cover});

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Uri>(
      future: future,
      builder: (ctx, snap) {
        if (!snap.hasData) return const SongThumbPlaceholder();
        return CachedNetworkImage(
          imageUrl: snap.data!.toString(),
          fit: fit,
          fadeInDuration: const Duration(milliseconds: 180),
          placeholder: (_, _) => const SongThumbPlaceholder(),
          errorWidget: (_, _, _) => const SongThumbPlaceholder(),
        );
      },
    );
  }
}
