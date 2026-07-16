/// Artist profile — header (avatar, name, @handle, bio, song count),
/// actions (share public page, edit, new song as artist), and the
/// discography (existing songs filtered by artist_id, client-side).
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../l10n/l10n.dart';
import '../theme.dart';
import '../ui/brand.dart';
import '../widgets/artist_avatar.dart';
import 'artist_edit_screen.dart';
import 'new_song_screen.dart';
import 'song_detail_screen.dart';

class ArtistScreen extends StatefulWidget {
  final FacelessApiClient client;
  final Artist artist;
  const ArtistScreen({super.key, required this.client, required this.artist});

  @override
  State<ArtistScreen> createState() => _ArtistScreenState();
}

class _ArtistScreenState extends State<ArtistScreen> {
  late Artist _artist;
  Future<List<SongSummary>>? _songsFuture;

  @override
  void initState() {
    super.initState();
    _artist = widget.artist;
    _songsFuture = widget.client.listSongs();
  }

  Future<void> _share() async {
    final messenger = ScaffoldMessenger.of(context);
    final l10n = context.l10n;
    try {
      final uri = await widget.client.publicArtistUrl(_artist.handle);
      await Clipboard.setData(ClipboardData(text: uri.toString()));
      messenger.showSnackBar(SnackBar(content: Text(l10n.artistLinkCopied)));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('$e')));
    }
  }

  Future<void> _openEdit() async {
    // ArtistEditScreen pops with the updated Artist, or 'deleted'.
    final result = await Navigator.of(context).push<Object?>(
      MaterialPageRoute(
        builder: (_) =>
            ArtistEditScreen(client: widget.client, artist: _artist),
      ),
    );
    if (!mounted) return;
    if (result == 'deleted') {
      Navigator.of(context).pop();
      return;
    }
    setState(() {
      if (result is Artist) _artist = result;
      _songsFuture = widget.client.listSongs();
    });
  }

  Future<void> _newSong() async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) =>
            NewSongScreen(client: widget.client, initialArtist: _artist),
      ),
    );
    if (mounted) {
      setState(() => _songsFuture = widget.client.listSongs());
    }
  }

  void _openSong(SongSummary s) {
    Navigator.of(context)
        .push(MaterialPageRoute(
          builder: (_) =>
              SongDetailScreen(client: widget.client, runId: s.id),
        ))
        .then((_) {
      if (mounted) {
        setState(() => _songsFuture = widget.client.listSongs());
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Scaffold(
      appBar: AppBar(),
      body: RefreshIndicator(
        onRefresh: () async {
          setState(() => _songsFuture = widget.client.listSongs());
          await _songsFuture;
        },
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
          children: [
            Center(
              child: ArtistAvatar(
                  artist: _artist, client: widget.client, size: 96),
            ),
            const SizedBox(height: 14),
            Center(
              child: Text(
                _artist.name,
                textAlign: TextAlign.center,
                style: FacelessTheme.display(size: 28),
              ),
            ),
            const SizedBox(height: 4),
            Center(
              child: Text(
                '@${_artist.handle}',
                style: const TextStyle(
                    color: FacelessTheme.textSecondary, fontSize: 14),
              ),
            ),
            if (_artist.bio.trim().isNotEmpty) ...[
              const SizedBox(height: 10),
              Center(
                child: Text(
                  _artist.bio,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                      color: FacelessTheme.textPrimary, fontSize: 14),
                ),
              ),
            ],
            const SizedBox(height: 8),
            Center(
              child: Text(
                l10n.artistSongCount(_artist.songCount),
                style: const TextStyle(
                    color: FacelessTheme.textSecondary, fontSize: 13),
              ),
            ),
            const SizedBox(height: 18),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.link, size: 18),
                    label: Text(l10n.artistShare),
                    onPressed: _share,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.edit_outlined, size: 18),
                    label: Text(l10n.artistEdit),
                    onPressed: _openEdit,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            GradientButton(
              label: l10n.artistNewSongCta(_artist.name),
              icon: Icons.add,
              expand: true,
              onPressed: _newSong,
            ),
            const SizedBox(height: 24),
            Text(
              l10n.artistDiscographyTitle,
              style: const TextStyle(
                  color: FacelessTheme.textPrimary,
                  fontSize: 17,
                  fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 10),
            FutureBuilder<List<SongSummary>>(
              future: _songsFuture,
              builder: (context, snap) {
                if (snap.connectionState == ConnectionState.waiting) {
                  return const Padding(
                    padding: EdgeInsets.symmetric(vertical: 32),
                    child: Center(child: CircularProgressIndicator()),
                  );
                }
                if (snap.hasError) {
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    child: Text(
                      '${snap.error}',
                      style: TextStyle(
                          color: Theme.of(context).colorScheme.error),
                    ),
                  );
                }
                final songs = (snap.data ?? const <SongSummary>[])
                    .where((s) => s.artistId == _artist.id)
                    .toList();
                if (songs.isEmpty) {
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 20),
                    child: Column(
                      children: [
                        Text(
                          l10n.artistNoSongsYet(_artist.name),
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                              color: FacelessTheme.textSecondary),
                        ),
                        const SizedBox(height: 14),
                        GradientButton(
                          label: l10n.artistNewSongCta(_artist.name),
                          icon: Icons.add,
                          onPressed: _newSong,
                        ),
                      ],
                    ),
                  );
                }
                return Column(
                  children: [
                    for (final s in songs) _SongRow(song: s, onTap: _openSong),
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}

/// Simple white discography card: pastel cover placeholder + title + status
/// pill. Taps open the existing SongDetailScreen.
class _SongRow extends StatelessWidget {
  final SongSummary song;
  final void Function(SongSummary) onTap;
  const _SongRow({required this.song, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final title = song.title ?? song.theme ?? l10n.homeUntitled;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Container(
        decoration: BoxDecoration(
          color: FacelessTheme.surface,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: FacelessTheme.border),
          boxShadow: FacelessTheme.softShadow,
        ),
        clipBehavior: Clip.antiAlias,
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            onTap: () => onTap(song),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  Container(
                    width: 56,
                    height: 56,
                    decoration: BoxDecoration(
                      gradient: coverGradient(title),
                      borderRadius: BorderRadius.circular(13),
                    ),
                    child: const Icon(Icons.music_note,
                        color: Colors.white, size: 24),
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
                          style:
                              const TextStyle(fontWeight: FontWeight.w600),
                        ),
                        const SizedBox(height: 6),
                        Wrap(
                          spacing: 6,
                          runSpacing: 4,
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 10, vertical: 4),
                              decoration: BoxDecoration(
                                color: FacelessTheme.surface2,
                                borderRadius: BorderRadius.circular(999),
                                border:
                                    Border.all(color: FacelessTheme.border),
                              ),
                              child: Text(
                                statusLabel(l10n, song.status),
                                style: const TextStyle(
                                    fontSize: 11.5,
                                    color: FacelessTheme.textSecondary,
                                    fontWeight: FontWeight.w600),
                              ),
                            ),
                            // Distribution: green "● Released" chip once the
                            // song is marked live on the stores.
                            if (song.released)
                              Container(
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 10, vertical: 4),
                                decoration: BoxDecoration(
                                  color: FacelessTheme.accent
                                      .withValues(alpha: 0.14),
                                  borderRadius: BorderRadius.circular(999),
                                ),
                                child: Text(
                                  '● ${l10n.releaseBadge}',
                                  style: const TextStyle(
                                      fontSize: 11.5,
                                      color: FacelessTheme.accent,
                                      fontWeight: FontWeight.w600),
                                ),
                              ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const Icon(Icons.chevron_right,
                      color: FacelessTheme.faint),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
