/// "Latest release" hero card — jewel cover art with a living waveform
/// breathing over it, a play glyph, the serif title, artist name, and a
/// status pill. Replaces the pre-redesign `_SongHero`. Data (title/status/
/// cover future) is handed down already-resolved from `_HomeScreenState`;
/// this widget only renders it.
library;

import 'package:flutter/material.dart';

import '../../l10n/l10n.dart';
import '../../theme.dart';
import '../../ui/brand.dart';
import '../../ui/primitives.dart';
import 'home_shared.dart';

class LatestReleaseCard extends StatelessWidget {
  final String title;
  final String? artistName;
  final String status;
  final Future<Uri> coverUrlFuture;
  final VoidCallback onTap;
  const LatestReleaseCard({
    super.key,
    required this.title,
    this.artistName,
    required this.status,
    required this.coverUrlFuture,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final st = songStatusStyle(context.l10n, status);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 2),
      child: GlassCard(
        padding: EdgeInsets.zero,
        radius: 22,
        onTap: onTap,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(
              height: 166,
              width: double.infinity,
              child: Stack(
                fit: StackFit.expand,
                children: [
                  SongCover(future: coverUrlFuture, fit: BoxFit.cover),
                  // "Sound made visible" — a living waveform breathing over
                  // the cover art, independent of status (purely decorative).
                  // LivingWaveform sizes to its own content (Row with
                  // mainAxisSize.min) rather than stretching to fill, so
                  // centering it explicitly here is what keeps it in the
                  // middle of the cover instead of hugging the start edge.
                  PositionedDirectional(
                    start: 0,
                    end: 0,
                    bottom: 16,
                    child: Align(
                      alignment: Alignment.center,
                      child: Opacity(
                        opacity: 0.8,
                        child: LivingWaveform(bars: 22, height: 34),
                      ),
                    ),
                  ),
                  PositionedDirectional(
                    top: 14,
                    end: 16,
                    child: _PlayGlyph(size: 46),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(19, 16, 19, 18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Eyebrow(context.l10n.homeLatestRelease),
                  const SizedBox(height: 8),
                  Text(
                    title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: FacelessTheme.display(
                      size: 23,
                      weight: FontWeight.w600,
                      locale: Localizations.maybeLocaleOf(context),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      if (artistName != null && artistName!.isNotEmpty)
                        Expanded(
                          child: Text(
                            artistName!,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              color: FacelessTheme.textSecondary,
                              fontSize: 12.5,
                            ),
                          ),
                        )
                      else
                        const Spacer(),
                      SongStatusIndicator(style: st),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Hollow champagne play ring over the cover art — replaces the old solid
/// gold play disc so the glyph reads as a hairline accent, not a filled
/// brand-color block.
class _PlayGlyph extends StatelessWidget {
  final double size;
  const _PlayGlyph({this.size = 46});

  @override
  Widget build(BuildContext context) => Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: FacelessTheme.bg.withValues(alpha: 0.35),
          border: Border.all(color: FacelessTheme.accent2, width: 1.5),
        ),
        child: Icon(Icons.play_arrow_rounded,
            color: FacelessTheme.accent2, size: size * 0.4),
      );
}
