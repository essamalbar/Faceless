/// "Your artists" horizontal strip — a "+" tile first, then one avatar per
/// artist. Shown even with zero artists (title + the create tile). The
/// artists future/client/callbacks all come from `_HomeScreenState`; this
/// widget only builds from them.
library;

import 'package:flutter/material.dart';

import '../../api/client.dart';
import '../../api/models.dart';
import '../../l10n/l10n.dart';
import '../../theme.dart';
import '../../ui/primitives.dart';
import '../artist_avatar.dart';
import 'home_shared.dart';

class ArtistsRow extends StatelessWidget {
  final Future<List<Artist>>? artistsFuture;
  final FacelessApiClient client;
  final VoidCallback onNewArtist;
  final void Function(Artist) onOpenArtist;
  const ArtistsRow({
    super.key,
    required this.artistsFuture,
    required this.client,
    required this.onNewArtist,
    required this.onOpenArtist,
  });

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<Artist>>(
      future: artistsFuture,
      builder: (context, snap) {
        final artists = snap.data ?? const <Artist>[];
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SongSectionTitle(
              title: context.l10n.artistsSectionTitle,
              trailing: artists.isEmpty ? '' : '${artists.length}',
            ),
            SizedBox(
              height: 84,
              child: ListView(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                children: [
                  _NewArtistTile(onTap: onNewArtist),
                  for (final a in artists)
                    Padding(
                      padding: const EdgeInsetsDirectional.only(start: 14),
                      child: _ArtistTile(
                        artist: a,
                        client: client,
                        onTap: () => onOpenArtist(a),
                      ),
                    ),
                ],
              ),
            ),
          ],
        );
      },
    );
  }
}

/// Avatar circle + name, tap opens the artist screen. Real uploaded/rendered
/// avatars keep using [ArtistAvatar] (network image); artists without one
/// fall back to the redesign's serif-monogram [ArtistBadge] instead of
/// [ArtistAvatar]'s own gradient-initial fallback.
class _ArtistTile extends StatelessWidget {
  final Artist artist;
  final FacelessApiClient client;
  final VoidCallback onTap;
  const _ArtistTile({
    required this.artist,
    required this.client,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final name = artist.name.trim();
    final monogram = name.isEmpty ? '?' : name.characters.first;
    return InkWell(
      borderRadius: BorderRadius.circular(14),
      onTap: onTap,
      child: SizedBox(
        width: 64,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            artist.hasAvatar
                ? ArtistAvatar(artist: artist, client: client, size: 56)
                : ArtistBadge(monogram: monogram, size: 56),
            const SizedBox(height: 6),
            Text(
              artist.name,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.center,
              style: const TextStyle(
                  fontSize: 11, color: FacelessTheme.textSecondary),
            ),
          ],
        ),
      ),
    );
  }
}

/// Champagne-hairline "+" circle that opens the create-artist form.
class _NewArtistTile extends StatelessWidget {
  final VoidCallback onTap;
  const _NewArtistTile({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(14),
      onTap: onTap,
      child: SizedBox(
        width: 64,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 56,
              height: 56,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: FacelessTheme.accent.withValues(alpha: 0.04),
                border: Border.all(color: FacelessTheme.borderAccent, width: 1.2),
              ),
              child: const Icon(Icons.add,
                  color: FacelessTheme.accent, size: 24),
            ),
            const SizedBox(height: 6),
            Text(
              context.l10n.artistNewTile,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                  fontSize: 11, color: FacelessTheme.textSecondary),
            ),
          ],
        ),
      ),
    );
  }
}
