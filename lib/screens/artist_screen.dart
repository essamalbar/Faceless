/// Artist profile — the editorial "artist comes alive" screen: header
/// (avatar with a breathing champagne halo, serif name, @handle, bio, song
/// count), actions (share public page, edit, new song as artist), and the
/// discography (existing songs filtered by artist_id, client-side).
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../l10n/l10n.dart';
import '../theme.dart';
import '../ui/brand.dart';
import '../ui/primitives.dart';
import '../widgets/artist_avatar.dart';
import '../widgets/home/song_row.dart';
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

  // Same fallback the "your artists" home row uses (artists_row.dart)
  // for artists with no uploaded/rendered avatar.
  String get _monogram {
    final name = _artist.name.trim();
    return name.isEmpty ? '?' : name.characters.first;
  }

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
          // No horizontal padding at the list level — SongRow (below) bakes
          // in its own 16px horizontal padding (matching the home screen's
          // list), so every other block wraps itself in the same 16px inset
          // individually to keep everything visually flush.
          padding: const EdgeInsets.only(top: 8, bottom: 32),
          children: [
            _Reveal(
              index: 0,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Column(
                  children: [
                    Center(
                      child: _artist.hasAvatar
                          ? _AliveHalo(
                              size: 96,
                              child: ArtistAvatar(
                                  artist: _artist,
                                  client: widget.client,
                                  size: 96),
                            )
                          : ArtistBadge(
                              monogram: _monogram,
                              alive: true,
                              size: 96,
                            ),
                    ),
                    const SizedBox(height: 18),
                    Center(child: Eyebrow(l10n.artistProfileEyebrow)),
                    const SizedBox(height: 8),
                    Center(
                      child: EditorialHeading(
                        _artist.name,
                        size: 30,
                        textAlign: TextAlign.center,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Center(
                      child: Text(
                        '@${_artist.handle}',
                        style: const TextStyle(
                            color: FacelessTheme.textSecondary, fontSize: 14),
                      ),
                    ),
                    if (_artist.bio.trim().isNotEmpty) ...[
                      const SizedBox(height: 12),
                      Center(
                        child: Text(
                          _artist.bio,
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                              color: FacelessTheme.textPrimary, fontSize: 14),
                        ),
                      ),
                    ],
                    const SizedBox(height: 10),
                    Center(
                      child: Text(
                        l10n.artistSongCount(_artist.songCount),
                        style: const TextStyle(
                            color: FacelessTheme.textSecondary,
                            fontSize: 12.5,
                            letterSpacing: 0.2),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 22),
            _Reveal(
              index: 1,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Row(
                  children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        icon: const Icon(Icons.link,
                            size: 18, color: FacelessTheme.accent2),
                        label: Text(l10n.artistShare),
                        style: OutlinedButton.styleFrom(
                            side: BorderSide(color: FacelessTheme.borderAccent)),
                        onPressed: _share,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: OutlinedButton.icon(
                        icon: const Icon(Icons.edit_outlined,
                            size: 18, color: FacelessTheme.accent2),
                        label: Text(l10n.artistEdit),
                        style: OutlinedButton.styleFrom(
                            side: BorderSide(color: FacelessTheme.borderAccent)),
                        onPressed: _openEdit,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            _Reveal(
              index: 2,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: GradientButton(
                  label: l10n.artistNewSongCta(_artist.name),
                  icon: Icons.add,
                  expand: true,
                  onPressed: _newSong,
                ),
              ),
            ),
            const SizedBox(height: 26),
            _Reveal(
              index: 3,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Hairline(),
              ),
            ),
            const SizedBox(height: 18),
            _Reveal(
              index: 4,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Eyebrow(l10n.artistDiscographyTitle),
              ),
            ),
            const SizedBox(height: 14),
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
                    padding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 16),
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
                    padding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 20),
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
                    for (final (i, s) in songs.indexed)
                      _Reveal(
                        index: 5 + i,
                        child: SongRow(
                          title: s.title ?? s.theme ?? l10n.homeUntitled,
                          status: s.status,
                          released: s.released,
                          onYoutube: s.youtubeUrl != null,
                          coverUrlFuture:
                              widget.client.songCoverUrl(s.id, thumb: true),
                          onTap: () => _openSong(s),
                        ),
                      ),
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

/// Soft breathing champagne halo behind [child] — the "artist comes alive"
/// motif from [ArtistBadge], applied here to the real avatar (photo or
/// gradient-monogram fallback, both already handled by [ArtistAvatar]) so
/// the reveal works whether or not the artist has an uploaded picture.
/// Honors `MediaQuery.disableAnimations`.
class _AliveHalo extends StatefulWidget {
  final double size;
  final Widget child;
  const _AliveHalo({required this.size, required this.child});

  @override
  State<_AliveHalo> createState() => _AliveHaloState();
}

class _AliveHaloState extends State<_AliveHalo>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 4000),
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final reduceMotion =
        MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    if (!reduceMotion) {
      if (!_controller.isAnimating) _controller.repeat(reverse: true);
    } else {
      if (_controller.isAnimating) _controller.stop();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final reduceMotion =
        MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    final haloStatic = Container(
      width: widget.size + 14,
      height: widget.size + 14,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: RadialGradient(
          colors: [
            FacelessTheme.accent2.withValues(alpha: 0.35),
            FacelessTheme.accent2.withValues(alpha: 0.0),
          ],
        ),
      ),
    );

    final halo = reduceMotion
        ? haloStatic
        : AnimatedBuilder(
            animation: _controller,
            builder: (context, child) {
              final scale = 1.0 + _controller.value * 0.08;
              final opacity = 0.55 + _controller.value * 0.35;
              return Opacity(
                opacity: opacity,
                child: Transform.scale(scale: scale, child: child),
              );
            },
            child: haloStatic,
          );

    // Keep the outer footprint exactly `size` (matching ArtistBadge's
    // convention) so this doesn't grow larger than the space callers give
    // it — the halo overflows via Clip.none instead of enlarging the box.
    return SizedBox(
      width: widget.size,
      height: widget.size,
      child: Stack(
        clipBehavior: Clip.none,
        alignment: Alignment.center,
        children: [halo, widget.child],
      ),
    );
  }
}

/// Fades + slides [child] up on first build — the staggered entrance for
/// the artist header/action/discography blocks. Every instance shares the
/// same duration but starts later for a higher [index], so the blocks
/// settle in sequence rather than all at once. Honors
/// `MediaQuery.disableAnimations` (renders [child] immediately, with no
/// animation, when reduced motion is requested).
class _Reveal extends StatelessWidget {
  final int index;
  final Widget child;
  const _Reveal({required this.index, required this.child});

  @override
  Widget build(BuildContext context) {
    final reduceMotion =
        MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    if (reduceMotion) return child;
    final delay = (index * 0.07).clamp(0.0, 0.7);
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.0, end: 1.0),
      duration: const Duration(milliseconds: 640),
      curve: Interval(delay, 1.0, curve: Curves.easeOutCubic),
      builder: (context, t, child) => Opacity(
        opacity: t,
        child: Transform.translate(
          offset: Offset(0, (1 - t) * 14),
          child: child,
        ),
      ),
      child: child,
    );
  }
}
