/// "Your songs" list row + the compact horizontal "Recent" tile. Both take
/// already-resolved data (title/status/cover future) and a tap callback from
/// `_HomeScreenState` — no fetching here.
library;

import 'package:flutter/material.dart';

import '../../l10n/l10n.dart';
import '../../theme.dart';
import '../../ui/primitives.dart';
import 'home_shared.dart';

/// Full-width row in the "Your songs" list — cover (with a living waveform
/// overlay while composing), serif title, optional artist subtitle, and a
/// trailing status indicator + Released/YouTube chips. Mirrors the
/// artboard's song rows: no decorative play icon (the old one wasn't
/// independently tappable anyway — the whole row already opens the song).
class SongRow extends StatelessWidget {
  final String title;
  final String? artistName;
  final String status;
  final bool released;
  final bool onYoutube;
  final Future<Uri> coverUrlFuture;
  final VoidCallback onTap;
  const SongRow({
    super.key,
    required this.title,
    this.artistName,
    required this.status,
    this.released = false,
    this.onYoutube = false,
    required this.coverUrlFuture,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final st = songStatusStyle(context.l10n, status);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 6, 16, 0),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(18),
          onTap: onTap,
          child: Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: st.working
                  ? FacelessTheme.accent.withValues(alpha: 0.035)
                  : FacelessTheme.glass,
              borderRadius: BorderRadius.circular(18),
              border: Border.all(
                color: st.working
                    ? FacelessTheme.borderAccent
                    : FacelessTheme.border,
              ),
            ),
            child: Row(
              children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(13),
                  child: SizedBox(
                    width: 56,
                    height: 56,
                    child: Stack(
                      fit: StackFit.expand,
                      children: [
                        SongCover(future: coverUrlFuture, fit: BoxFit.cover),
                        if (st.working)
                          ColoredBox(
                            color: FacelessTheme.bg.withValues(alpha: 0.5),
                            child: const Center(
                              child: LivingWaveform(bars: 5, height: 20),
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(width: 13),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        title,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: FacelessTheme.display(
                          size: 17,
                          weight: FontWeight.w600,
                          locale: Localizations.maybeLocaleOf(context),
                        ),
                      ),
                      if (artistName != null && artistName!.isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 2),
                          child: Text(
                            artistName!,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                                color: FacelessTheme.faint, fontSize: 11.5),
                          ),
                        ),
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 6,
                        runSpacing: 4,
                        children: [
                          SongStatusIndicator(style: st),
                          if (released) const _ReleasedBadge(),
                          if (onYoutube) const _YoutubeBadge(),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Compact horizontal card for the "Recent" row.
class RecentSongTile extends StatelessWidget {
  final String title;
  final String status;
  final Future<Uri> coverUrlFuture;
  final VoidCallback onTap;
  const RecentSongTile({
    super.key,
    required this.title,
    required this.status,
    required this.coverUrlFuture,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final st = songStatusStyle(context.l10n, status);
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 150,
        decoration: BoxDecoration(
          color: FacelessTheme.glass,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: FacelessTheme.border),
        ),
        clipBehavior: Clip.antiAlias,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(
              width: double.infinity,
              height: 110,
              child: SongCover(future: coverUrlFuture, fit: BoxFit.cover),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(10, 9, 10, 10),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                        color: FacelessTheme.textPrimary,
                        fontSize: 13,
                        fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 7),
                  SongStatusIndicator(style: st, compact: true),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Tiny "● Released" chip — mirrors the status-pill visual so it can sit
/// beside one. Shown on song rows when the user has marked the song live on
/// the stores (Distribution feature).
class _ReleasedBadge extends StatelessWidget {
  const _ReleasedBadge();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
      decoration: BoxDecoration(
        color: FacelessTheme.accent.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        '● ${context.l10n.releaseBadge}',
        style: const TextStyle(
            color: FacelessTheme.accent,
            fontSize: 11,
            fontWeight: FontWeight.w600),
      ),
    );
  }
}

/// Tiny neutral "▶ YouTube" chip — shown beside the Released badge when the
/// song is on YouTube (`youtube_url != null`). Deliberately subtle: same
/// chip shape, textSecondary instead of a loud brand red.
class _YoutubeBadge extends StatelessWidget {
  const _YoutubeBadge();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
      decoration: BoxDecoration(
        color: FacelessTheme.textSecondary.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        '▶ ${context.l10n.ytBadge}',
        style: const TextStyle(
            color: FacelessTheme.textSecondary,
            fontSize: 11,
            fontWeight: FontWeight.w600),
      ),
    );
  }
}
