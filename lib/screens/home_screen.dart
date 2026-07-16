import 'dart:async';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../api/settings.dart';
import '../config.dart';
import '../l10n/l10n.dart';
import '../theme.dart';
import '../widgets/artist_avatar.dart';
import '../widgets/faceless_logo.dart';
import 'artist_edit_screen.dart';
import 'artist_screen.dart';
import 'billing_screen.dart';
import 'cost_screen.dart';
import 'new_run_screen.dart';
import 'onboarding_screen.dart';
import 'run_detail_screen.dart';
import 'new_song_screen.dart';
import 'personas_screen.dart';
import 'settings_screen.dart';
import 'song_approve_screen.dart';
import 'song_detail_screen.dart';
import 'video_player_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _settings = FacelessSettings();
  late FacelessApiClient _client;
  Future<List<RunSummary>>? _runsFuture;
  String? _baseUrl;
  String? _token;
  String _filter = 'all';   // all | complete | awaiting | running | failed
  SpendSummary? _spend;
  PlanInfo? _plan;
  String _mode = 'horror';  // horror | song
  Future<List<SongSummary>>? _songsFuture;
  Future<List<Artist>>? _artistsFuture; // Artist Core: home artists row
  Future<List<TrendBrief>>? _trendsFuture; // Trend Engine: timely briefs
  bool _trendsRefreshing = false;
  String _songQuery = '';   // live search filter for the song list
  bool _llmDegraded = false; // lyric-quality alarm (primary LLM fell back)
  bool _llmBannerDismissed = false;

  @override
  void initState() {
    super.initState();
    _client = FacelessApiClient(_settings);
    _loadAndRefresh();
    _maybeShowOnboarding();
    _checkLlmStatus();
  }

  /// Lyric-quality alarm — best-effort, silent on failure. Warns when the
  /// primary writing model recently failed and lyrics degraded to the
  /// fallback provider.
  Future<void> _checkLlmStatus() async {
    try {
      final degraded = await _client.llmDegraded();
      if (mounted && degraded) setState(() => _llmDegraded = true);
    } catch (_) {/* silent */}
  }

  /// First-launch carousel. Scheduled after the frame is laid out so
  /// MaterialApp's overlay has a host context to push the route onto.
  Future<void> _maybeShowOnboarding() async {
    final seen = await OnboardingScreen.hasSeen();
    if (seen || !mounted) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => const OnboardingScreen(),
          fullscreenDialog: true,
        ),
      );
    });
  }

  Future<void> _loadAndRefresh() async {
    _baseUrl = await _settings.baseUrl();
    _token = _currentBearerToken();
    if (mounted) {
      setState(() {
        _runsFuture = _client.listRuns();
        _songsFuture = _client.listSongs();
        _artistsFuture = _client.listArtists();
      });
    }
    _fetchSpend();
    _fetchPlan();
  }

  Future<void> _fetchPlan() async {
    try {
      final p = await _client.getPlan();
      if (mounted) setState(() => _plan = p);
    } catch (_) {
      // best-effort; the Plans teaser falls back to recommending Creator
    }
  }

  /// Bearer token for embedding in `<img>`/`<video>` URLs (browsers can't
  /// attach Authorization headers to those). Mirrors the resolution order
  /// in FacelessApiClient: Supabase session JWT first, legacy dart-define
  /// token as fallback.
  String? _currentBearerToken() {
    try {
      final session = Supabase.instance.client.auth.currentSession;
      if (session != null) return session.accessToken;
    } catch (_) {
      // Supabase not initialized — fall through.
    }
    return FacelessConfig.apiToken.isNotEmpty
        ? FacelessConfig.apiToken
        : null;
  }

  Future<void> _fetchSpend() async {
    try {
      final s = await _client.getSpendSummary();
      if (mounted) setState(() => _spend = s);
    } catch (_) {
      // Spend chip is best-effort; failure shouldn't break the gallery
    }
  }

  Future<void> _refresh() async {
    // NB: setState's callback must NOT return a Future. The arrow form
    // `() => _runsFuture = _client.listRuns()` implicitly returns the
    // assigned value (which IS a Future) and newer Flutter asserts on
    // that. Use a block body so the lambda returns void.
    setState(() {
      _runsFuture = _client.listRuns();
      _songsFuture = _client.listSongs();
      _artistsFuture = _client.listArtists();
    });
    await _runsFuture;
    _fetchSpend();
  }

  Future<void> _cleanupFailed() async {
    final yes = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(ctx.l10n.homeCleanupFailedTitle),
        content: Text(ctx.l10n.homeCleanupFailedBody),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: Text(ctx.l10n.commonCancel)),
          FilledButton(
              style: FilledButton.styleFrom(
                  backgroundColor: FacelessTheme.danger,
                  foregroundColor: Colors.white),
              onPressed: () => Navigator.pop(ctx, true),
              child: Text(ctx.l10n.homeDeleteAllFailed)),
        ],
      ),
    );
    if (yes != true || !mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    try {
      final deleted = await _client.cleanupFailedRuns();
      if (!mounted) return;
      messenger.showSnackBar(SnackBar(
          content: Text(context.l10n.homeRemovedFailedRuns(deleted.length))));
      _refresh();
    } catch (e) {
      if (!mounted) return;
      messenger.showSnackBar(
          SnackBar(content: Text(context.l10n.homeCleanupError('$e'))));
    }
  }

  Future<void> _openSettings() async {
    final saved = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => const SettingsScreen()),
    );
    if (saved == true) _loadAndRefresh();
  }

  Future<void> _openNewRun({String? initialTheme}) async {
    if (_mode == 'song') {
      await _openNewSong();
      return;
    }
    final created = await Navigator.of(context).push<RunSummary?>(
      MaterialPageRoute(
        builder: (_) => NewRunScreen(
          client: _client,
          initialTheme: initialTheme,
        ),
      ),
    );
    if (created != null) {
      _refresh();
      if (mounted) {
        Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) =>
                RunDetailScreen(client: _client, runId: created.id),
          ),
        );
      }
    }
  }

  Future<void> _openNewSong() async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => NewSongScreen(client: _client),
      ),
    );
    // Refresh song list when we return (the new song was created).
    if (mounted) {
      setState(() {
        _songsFuture = _client.listSongs();
      });
    }
  }

  Future<void> _openNewSongWithSample(String theme, String presetLabel) async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => NewSongScreen(
          client: _client,
          initialTheme: theme,
          initialPresetLabel: presetLabel,
        ),
      ),
    );
    if (mounted) {
      setState(() {
        _songsFuture = _client.listSongs();
      });
    }
  }

  void _openRun(RunSummary run) {
    Navigator.of(context)
        .push(MaterialPageRoute(
          builder: (_) => RunDetailScreen(client: _client, runId: run.id),
        ))
        .then((_) => _refresh());
  }

  Future<void> _confirmDelete(RunSummary run) async {
    final yes = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(ctx.l10n.homeDeleteRunTitle),
        content: Text(ctx.l10n.homeDeleteRunBody(run.title ?? run.id)),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: Text(ctx.l10n.commonCancel)),
          FilledButton(
              style: FilledButton.styleFrom(
                  backgroundColor: FacelessTheme.danger,
                  foregroundColor: Colors.white),
              onPressed: () => Navigator.pop(ctx, true),
              child: Text(ctx.l10n.commonDelete)),
        ],
      ),
    );
    if (yes != true || !mounted) return;
    // Capture the messenger before the async gap — using
    // `ScaffoldMessenger.of(context)` after `await` is a footgun (the
    // widget can be unmounted by then; analyzer flagged this).
    final messenger = ScaffoldMessenger.of(context);
    try {
      await _client.deleteRun(run.id);
      if (!mounted) return;
      messenger.showSnackBar(
        SnackBar(content: Text(context.l10n.homeDeletedItem(run.title ?? run.id))),
      );
      _refresh();
    } catch (e) {
      if (!mounted) return;
      messenger.showSnackBar(
        SnackBar(content: Text(context.l10n.homeDeleteError('$e'))),
      );
    }
  }

  void _playRun(RunSummary run) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => VideoPlayerScreen(
          client: _client,
          runId: run.id,
          title: run.title,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      // NOTE: do NOT use `extendBodyBehindAppBar: true` here. With a transparent
      // AppBar over the body, the first sliver (_TopBar) renders BEHIND the
      // AppBar, occluding the refresh/settings icon hit-targets. Keep them
      // in separate vertical bands so the user can always tap the icons.
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
        title: Row(
          children: [
            const FacelessLogo(size: 30),
            const SizedBox(width: 10),
            Text(context.l10n.appTitle,
                style: const TextStyle(fontWeight: FontWeight.w700)),
          ],
        ),
        actions: [
          const Padding(
            padding: EdgeInsetsDirectional.only(end: 4),
            child: Center(child: _BalanceBadge()),
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: context.l10n.homeRefresh,
            onPressed: _refresh,
          ),
          // Only show the saved-voices entry when on the Song tab —
          // it's a song-mode concept, irrelevant to horror runs.
          if (_mode == 'song')
            IconButton(
              icon: const Icon(Icons.record_voice_over),
              tooltip: context.l10n.homeSavedVoices,
              onPressed: () => Navigator.of(context).push(MaterialPageRoute(
                builder: (_) => PersonasScreen(client: _client),
              )),
            ),
          IconButton(
            icon: const Icon(Icons.settings),
            tooltip: context.l10n.homeSettings,
            onPressed: _openSettings,
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: SegmentedButton<String>(
              // No selection checkmark — it steals width and wraps the
              // label ("Horror" → "Horro/r"). The segment's own icon +
              // the ink/white theme already show which is selected.
              showSelectedIcon: false,
              segments: [
                ButtonSegment(
                    value: 'horror',
                    label: Text(context.l10n.homeTabHorror, maxLines: 1),
                    icon: const Icon(Icons.movie_outlined, size: 18)),
                ButtonSegment(
                    value: 'song',
                    label: Text(context.l10n.homeTabSong, maxLines: 1),
                    icon: const Icon(Icons.music_note, size: 18)),
              ],
              selected: {_mode},
              onSelectionChanged: (s) => setState(() {
                _mode = s.first;
                if (_mode == 'song' && _songsFuture == null) {
                  _songsFuture = _client.listSongs();
                  _artistsFuture ??= _client.listArtists();
                  _trendsFuture ??= _client.trendBriefs();
                }
              }),
            ),
          ),
          if (_llmDegraded && !_llmBannerDismissed)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                decoration: BoxDecoration(
                  color: FacelessTheme.warning.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                      color: FacelessTheme.warning.withValues(alpha: 0.5)),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.warning_amber_rounded,
                        size: 18, color: FacelessTheme.warning),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        context.l10n.llmDegradedBanner,
                        style: const TextStyle(
                            fontSize: 13, color: FacelessTheme.textPrimary),
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.close, size: 16),
                      color: FacelessTheme.textSecondary,
                      onPressed: () =>
                          setState(() => _llmBannerDismissed = true),
                    ),
                  ],
                ),
              ),
            ),
          Expanded(
            child: _mode == 'song'
                ? _buildSongsList()
                : RefreshIndicator(
                    onRefresh: _refresh,
                    child: FutureBuilder<List<RunSummary>>(
          future: _runsFuture,
          builder: (context, snap) {
            if (snap.connectionState == ConnectionState.waiting) {
              return const _LoadingPlaceholder();
            }
            if (snap.hasError) {
              return _ErrorView(
                error: snap.error.toString(),
                onSettings: _openSettings,
                onRetry: _refresh,
              );
            }
            final allRuns = (snap.data ?? []).reversed.toList(); // newest first
            if (allRuns.isEmpty) {
              return _EmptyView(
                onCreate: _openNewRun,
                currentPlan: _plan?.plan,
              );
            }

            // Apply current filter chip
            final runs = _filter == 'all'
                ? allRuns
                : allRuns.where((r) {
                    return switch (_filter) {
                      'complete' => r.isComplete,
                      'awaiting' => r.isAwaitingApproval,
                      'running' => r.isRunning,
                      'failed' => r.isFailed,
                      _ => true,
                    };
                  }).toList();

            final failedCount =
                allRuns.where((r) => r.isFailed).length;

            // Series + featured come from filtered set
            final series = _groupIntoSeries(runs);
            final standalone = runs
                .where((r) =>
                    !series.any((s) => s.episodes.any((e) => e.id == r.id)))
                .toList();
            final featured =
                runs.where((r) => r.hasVideo).take(5).toList();

            return CustomScrollView(
              slivers: [
                SliverToBoxAdapter(
                  child: _HomeContent(
                    onCreate: _openNewRun,
                    showHowItWorks: false,
                    currentPlan: _plan?.plan,
                  ),
                ),
                SliverToBoxAdapter(
                  child: _TopBar(
                    spend: _spend,
                    failedCount: failedCount,
                    filter: _filter,
                    counts: {
                      'all': allRuns.length,
                      'complete':
                          allRuns.where((r) => r.isComplete).length,
                      'awaiting':
                          allRuns.where((r) => r.isAwaitingApproval).length,
                      'running':
                          allRuns.where((r) => r.isRunning).length,
                      'failed': failedCount,
                    },
                    onFilter: (f) => setState(() => _filter = f),
                    onCleanup: failedCount > 0 ? _cleanupFailed : null,
                    onSpendTap: () => Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => CostScreen(client: _client),
                      ),
                    ),
                  ),
                ),
                if (runs.isEmpty)
                  SliverFillRemaining(
                    hasScrollBody: false,
                    child: Center(
                      child: Padding(
                        padding: const EdgeInsets.all(32),
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.filter_alt_off_outlined,
                                size: 48,
                                color: FacelessTheme.textSecondary
                                    .withValues(alpha: 0.6)),
                            const SizedBox(height: 12),
                            Text(
                              context.l10n.homeNoRunsMatchFilter,
                              style: const TextStyle(
                                  color: FacelessTheme.textSecondary),
                            ),
                            const SizedBox(height: 16),
                            OutlinedButton.icon(
                              onPressed: () =>
                                  setState(() => _filter = 'all'),
                              icon: const Icon(Icons.clear),
                              label: Text(context.l10n.homeShowAll),
                            ),
                          ],
                        ),
                      ),
                    ),
                  )
                else
                  SliverToBoxAdapter(
                    child: _YourStoriesHeader(count: featured.length),
                  ),
                if (featured.isNotEmpty)
                  SliverToBoxAdapter(
                    child: _HeroCarousel(
                      featured: featured,
                      baseUrl: _baseUrl,
                      token: _token,
                      onPlay: _playRun,
                      onTap: _openRun,
                    ),
                  )
                else if (runs.isNotEmpty)
                  const SliverToBoxAdapter(
                    child: _LibraryEmptyCard(),
                  ),
                ...series.map(
                  (s) => SliverToBoxAdapter(
                    child: _SeriesRow(
                      series: s,
                      baseUrl: _baseUrl,
                      token: _token,
                      onTap: _openRun,
                      onPlay: _playRun,
                      onLongPress: _confirmDelete,
                    ),
                  ),
                ),
                if (standalone.isNotEmpty)
                  SliverToBoxAdapter(
                    child: _StandaloneRow(
                      title: context.l10n.homeAllRuns,
                      runs: standalone,
                      baseUrl: _baseUrl,
                      token: _token,
                      onTap: _openRun,
                      onLongPress: _confirmDelete,
                    ),
                  ),
                const SliverToBoxAdapter(child: SizedBox(height: 100)),
              ],
            );
          },
        ),
      ),
        ),
        ],
      ),
    );
  }

  void _openSong(SongSummary s) {
    final screen = s.status == 'awaiting_approval'
        ? SongApproveScreen(client: _client, runId: s.id)
        : SongDetailScreen(client: _client, runId: s.id);
    Navigator.of(context)
        .push(MaterialPageRoute(builder: (_) => screen));
  }

  // ─── Artist Core: home artists row ─────────────────────────────────────────

  void _refreshArtistsAndSongs() {
    if (!mounted) return;
    setState(() {
      _artistsFuture = _client.listArtists();
      _songsFuture = _client.listSongs();
    });
  }

  Future<void> _openArtist(Artist a) async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ArtistScreen(client: _client, artist: a),
      ),
    );
    _refreshArtistsAndSongs();
  }

  Future<void> _openNewArtist() async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ArtistEditScreen(client: _client),
      ),
    );
    _refreshArtistsAndSongs();
  }

  /// Compact horizontal strip of artist avatars, "+" tile first. Shown even
  /// when there are no artists yet (title + the create tile).
  Widget _artistsSection() {
    return FutureBuilder<List<Artist>>(
      future: _artistsFuture,
      builder: (context, snap) {
        final artists = snap.data ?? const <Artist>[];
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _SongSectionTitle(
              title: context.l10n.artistsSectionTitle,
              trailing: artists.isEmpty ? '' : '${artists.length}',
            ),
            SizedBox(
              height: 82,
              child: ListView(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                children: [
                  _NewArtistTile(onTap: _openNewArtist),
                  for (final a in artists)
                    Padding(
                      padding: const EdgeInsetsDirectional.only(start: 14),
                      child: _ArtistCircleTile(
                        artist: a,
                        client: _client,
                        onTap: () => _openArtist(a),
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

  Future<void> _refreshTrends() async {
    setState(() {
      _trendsRefreshing = true;
      _trendsFuture = _client.trendBriefs(refresh: true);
    });
    try {
      await _trendsFuture;
    } catch (_) {/* section hides itself */} finally {
      if (mounted) setState(() => _trendsRefreshing = false);
    }
  }

  void _createFromBrief(TrendBrief b) {
    Navigator.of(context)
        .push(MaterialPageRoute(
          builder: (_) => NewSongScreen(
            client: _client,
            initialTheme: b.theme,
            initialStyleHint: b.styleHint,
            initialLanguage: b.language,
          ),
        ))
        .then((_) => _refresh());
  }

  /// Trend Engine: "Trending now" — timely, ready-to-approve song briefs.
  /// Fire-and-forget: any fetch error hides the section entirely.
  Widget _trendsSection() {
    return FutureBuilder<List<TrendBrief>>(
      future: _trendsFuture,
      builder: (context, snap) {
        if (snap.hasError) return const SizedBox.shrink();
        final briefs = snap.data ?? const <TrendBrief>[];
        if (briefs.isEmpty && !_trendsRefreshing) {
          return const SizedBox.shrink();
        }
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 8),
              child: Row(
                children: [
                  Text('✨ ${context.l10n.trendSectionTitle}',
                      style: const TextStyle(
                          fontWeight: FontWeight.w700, fontSize: 15)),
                  const Spacer(),
                  _trendsRefreshing
                      ? const SizedBox(
                          width: 16, height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2))
                      : IconButton(
                          icon: const Icon(Icons.refresh, size: 18),
                          color: FacelessTheme.textSecondary,
                          visualDensity: VisualDensity.compact,
                          tooltip: context.l10n.trendRefreshTooltip,
                          onPressed: _refreshTrends,
                        ),
                ],
              ),
            ),
            SizedBox(
              height: 150,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                itemCount: briefs.length,
                separatorBuilder: (_, __) => const SizedBox(width: 12),
                itemBuilder: (_, i) {
                  final b = briefs[i];
                  return Container(
                    width: 250,
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: FacelessTheme.surface,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: FacelessTheme.border),
                      boxShadow: FacelessTheme.softShadow,
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(b.titleIdea.isEmpty ? b.theme : b.titleIdea,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                                fontWeight: FontWeight.w700, fontSize: 15)),
                        const SizedBox(height: 5),
                        Expanded(
                          child: Text(b.rationale.isEmpty ? b.theme : b.rationale,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                  fontSize: 12.5,
                                  color: FacelessTheme.textSecondary)),
                        ),
                        Align(
                          alignment: AlignmentDirectional.centerEnd,
                          child: FilledButton(
                            style: FilledButton.styleFrom(
                              visualDensity: VisualDensity.compact,
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 14, vertical: 8),
                            ),
                            onPressed: () => _createFromBrief(b),
                            child: Text(context.l10n.trendCreateButton,
                                style: const TextStyle(fontSize: 13)),
                          ),
                        ),
                      ],
                    ),
                  );
                },
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _buildSongsList() {
    return RefreshIndicator(
      onRefresh: _refresh,
      child: FutureBuilder<List<SongSummary>>(
        future: _songsFuture,
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return _ErrorView(
              error: snap.error.toString(),
              onSettings: _openSettings,
              onRetry: _refresh,
            );
          }
          final all = snap.data ?? [];
          if (all.isEmpty) {
            // Trend briefs + artists row stay visible above the empty
            // state — a brand-new user gets timely ideas immediately.
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _trendsSection(),
                _artistsSection(),
                Expanded(
                  child: _SongsEmptyState(
                    onCreate: _openNewSong,
                    onTrySample: (theme, presetLabel) =>
                        _openNewSongWithSample(theme, presetLabel),
                  ),
                ),
              ],
            );
          }

          final q = _songQuery.trim().toLowerCase();
          final searching = q.isNotEmpty;
          final filtered = searching
              ? all
                  .where((s) =>
                      (s.title ?? '').toLowerCase().contains(q) ||
                      (s.theme ?? '').toLowerCase().contains(q))
                  .toList()
              : all;
          // Hero = newest playable song (fall back to the newest overall).
          final SongSummary? hero = searching
              ? null
              : all.firstWhere(
                  (s) => s.status == 'complete' && s.hasVideo,
                  orElse: () => all.first,
                );
          final recent =
              searching ? const <SongSummary>[] : all.where((s) => s != hero).take(10).toList();

          return ListView(
            padding: const EdgeInsets.only(bottom: 28),
            children: [
              _trendsSection(),
              _artistsSection(),
              _SongSearchBar(
                initial: _songQuery,
                onChanged: (v) => setState(() => _songQuery = v),
              ),
              if (hero != null)
                _SongHero(
                  title: hero.title ?? hero.theme ?? context.l10n.homeUntitled,
                  status: hero.status,
                  coverUrlFuture: _client.songCoverUrl(hero.id, thumb: false),
                  onTap: () => _openSong(hero),
                ),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
                child: SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: _openNewSong,
                    icon: const Icon(Icons.add),
                    label: Text(context.l10n.homeNewSong),
                  ),
                ),
              ),
              if (recent.isNotEmpty) ...[
                _SongSectionTitle(
                    title: context.l10n.homeRecent,
                    trailing: context.l10n.homeTracksCount(all.length)),
                SizedBox(
                  height: 172,
                  child: ListView.separated(
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    itemCount: recent.length,
                    separatorBuilder: (_, _) => const SizedBox(width: 12),
                    itemBuilder: (ctx, i) {
                      final s = recent[i];
                      return _RecentTile(
                        title: s.title ?? s.theme ?? context.l10n.homeUntitled,
                        status: s.status,
                        coverUrlFuture:
                            _client.songCoverUrl(s.id, thumb: true),
                        onTap: () => _openSong(s),
                      );
                    },
                  ),
                ),
              ],
              _SongSectionTitle(
                title: searching
                    ? context.l10n.homeResults
                    : context.l10n.homeYourSongs,
                trailing: searching
                    ? '${filtered.length}'
                    : context.l10n.homeTracksCount(all.length),
              ),
              if (filtered.isEmpty)
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 24, 16, 24),
                  child: Center(
                    child: Text(context.l10n.homeNoSongsMatchSearch,
                        style: const TextStyle(
                            color: FacelessTheme.textSecondary)),
                  ),
                ),
              ...filtered.map((s) => _SongCardC(
                    title: s.title ?? s.theme ?? context.l10n.homeUntitled,
                    status: s.status,
                    released: s.released,
                    onYoutube: s.youtubeUrl != null,
                    coverUrlFuture: _client.songCoverUrl(s.id, thumb: true),
                    onTap: () => _openSong(s),
                  )),
            ],
          );
        },
      ),
    );
  }

  @override
  void dispose() {
    _client.close();
    super.dispose();
  }
}

// ---------------------------------------------------------------------------
// Series grouping
// ---------------------------------------------------------------------------

class _Series {
  final String name;
  final List<RunSummary> episodes;
  _Series(this.name, this.episodes);
}

/// Detect series from titles like "العقد المقدس - الحلقة 1" / "EP 1" / "Episode 2".
/// Groups episodes that share a common prefix BEFORE the episode marker.
List<_Series> _groupIntoSeries(List<RunSummary> runs) {
  final groups = <String, List<RunSummary>>{};
  final epMarker = RegExp(
      r'(?:\s*[-—]\s*الحلقة\s*\d+|\s*[-—]\s*EP\s*\d+|\s*[-—]\s*Episode\s*\d+|\s*\d+$)',
      caseSensitive: false);
  for (final r in runs) {
    final title = (r.title ?? '').trim();
    if (title.isEmpty) continue;
    final m = epMarker.firstMatch(title);
    if (m == null) continue;
    final base = title.substring(0, m.start).trim();
    if (base.length < 4) continue;
    groups.putIfAbsent(base, () => []).add(r);
  }
  return groups.entries
      .where((e) => e.value.length >= 2)
      .map((e) => _Series(e.key, e.value))
      .toList();
}

// ---------------------------------------------------------------------------
// Top bar — spend chip + filter chips + cleanup button
// ---------------------------------------------------------------------------

class _TopBar extends StatelessWidget {
  final SpendSummary? spend;
  final int failedCount;
  final String filter;
  final Map<String, int> counts;
  final ValueChanged<String> onFilter;
  final VoidCallback? onCleanup;
  final VoidCallback? onSpendTap;
  const _TopBar({
    required this.spend,
    required this.failedCount,
    required this.filter,
    required this.counts,
    required this.onFilter,
    required this.onCleanup,
    this.onSpendTap,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Spend chip + cleanup button row — first row UNDER the AppBar
          Row(
            children: [
              if (spend != null)
                Material(
                  color: Colors.transparent,
                  child: InkWell(
                    onTap: onSpendTap,
                    borderRadius: BorderRadius.circular(10),
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 12, vertical: 8),
                      decoration: BoxDecoration(
                        color: FacelessTheme.surface,
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(
                            color: FacelessTheme.accent
                                .withValues(alpha: 0.3)),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.payments_outlined,
                              color: FacelessTheme.accent, size: 16),
                          const SizedBox(width: 6),
                          Text(
                            '\$${spend!.totalUsd.toStringAsFixed(2)}',
                            style: const TextStyle(
                                fontWeight: FontWeight.w700, fontSize: 13),
                          ),
                          const SizedBox(width: 6),
                          Text(context.l10n.homeRunsCount(spend!.runCount),
                              style: const TextStyle(
                                  color: FacelessTheme.textSecondary,
                                  fontSize: 11)),
                          const SizedBox(width: 4),
                          const Icon(Icons.chevron_right,
                              size: 16,
                              color: FacelessTheme.textSecondary),
                        ],
                      ),
                    ),
                  ),
                ),
              const Spacer(),
              if (onCleanup != null)
                TextButton.icon(
                  onPressed: onCleanup,
                  icon: const Icon(Icons.cleaning_services_outlined,
                      size: 16),
                  label: Text(context.l10n.homeCleanFailed(failedCount),
                      style: const TextStyle(fontSize: 12)),
                  style: TextButton.styleFrom(
                    foregroundColor: FacelessTheme.danger,
                  ),
                ),
            ],
          ),
          const SizedBox(height: 12),
          // Filter chips (separate row, can scroll horizontally)
          SizedBox(
            height: 36,
            child: ListView(
              scrollDirection: Axis.horizontal,
              children: [
                _FilterChip(
                    label: context.l10n.homeFilterAll,
                    count: counts['all'] ?? 0,
                    selected: filter == 'all',
                    onTap: () => onFilter('all')),
                _FilterChip(
                    label: context.l10n.homeFilterComplete,
                    count: counts['complete'] ?? 0,
                    selected: filter == 'complete',
                    onTap: () => onFilter('complete'),
                    color: FacelessTheme.success),
                _FilterChip(
                    label: context.l10n.homeFilterAwaiting,
                    count: counts['awaiting'] ?? 0,
                    selected: filter == 'awaiting',
                    onTap: () => onFilter('awaiting'),
                    color: FacelessTheme.warning),
                _FilterChip(
                    label: context.l10n.homeFilterRunning,
                    count: counts['running'] ?? 0,
                    selected: filter == 'running',
                    onTap: () => onFilter('running'),
                    color: FacelessTheme.info),
                _FilterChip(
                    label: context.l10n.homeFilterFailed,
                    count: counts['failed'] ?? 0,
                    selected: filter == 'failed',
                    onTap: () => onFilter('failed'),
                    color: FacelessTheme.danger),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  final String label;
  final int count;
  final bool selected;
  final VoidCallback onTap;
  final Color? color;
  const _FilterChip({
    required this.label,
    required this.count,
    required this.selected,
    required this.onTap,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    final c = color ?? FacelessTheme.accent;
    final bg = selected ? c.withValues(alpha: 0.25) : FacelessTheme.surface;
    final border = selected ? c : FacelessTheme.textSecondary.withValues(alpha: 0.25);
    return Padding(
      padding: const EdgeInsetsDirectional.only(end: 8),
      child: Material(
        color: bg,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18),
          side: BorderSide(color: border),
        ),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(18),
          child: Padding(
            padding:
                const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(label,
                    style: TextStyle(
                      color: selected ? c : Colors.white,
                      fontSize: 12,
                      fontWeight:
                          selected ? FontWeight.w700 : FontWeight.w500,
                    )),
                if (count > 0) ...[
                  const SizedBox(width: 6),
                  Text('$count',
                      style: TextStyle(
                          color: selected
                              ? c
                              : FacelessTheme.textSecondary,
                          fontSize: 11,
                          fontWeight: FontWeight.w600)),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}


// ---------------------------------------------------------------------------
// "Your stories" section — section header above hero carousel + empty card
// when the user has runs but none have a rendered video yet
// ---------------------------------------------------------------------------

class _YourStoriesHeader extends StatelessWidget {
  final int count;
  const _YourStoriesHeader({required this.count});
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
      child: Row(
        children: [
          Container(
            width: 4,
            height: 22,
            decoration: BoxDecoration(
              color: FacelessTheme.accent,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: 10),
          Text(context.l10n.homeYourStories,
              style: const TextStyle(
                color: FacelessTheme.textPrimary,
                fontWeight: FontWeight.w700,
                fontSize: 18,
              )),
          const Spacer(),
          if (count > 0)
            Text('$count',
                style: const TextStyle(
                    color: FacelessTheme.textSecondary, fontSize: 12)),
        ],
      ),
    );
  }
}

class _LibraryEmptyCard extends StatelessWidget {
  const _LibraryEmptyCard();
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 4),
      child: Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(16),
          color: FacelessTheme.surface,
          border: Border.all(
            color: FacelessTheme.textSecondary.withValues(alpha: 0.12),
          ),
        ),
        child: Row(
          children: [
            Container(
              width: 56,
              height: 56,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: FacelessTheme.accent.withValues(alpha: 0.12),
              ),
              child: const Icon(Icons.movie_filter_outlined,
                  color: FacelessTheme.accent, size: 28),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(context.l10n.homeNoRenderedVideos,
                      style: const TextStyle(
                        color: FacelessTheme.textPrimary,
                        fontWeight: FontWeight.w700,
                        fontSize: 15,
                      )),
                  const SizedBox(height: 4),
                  Text(
                    context.l10n.homeApproveScriptHint,
                    style: const TextStyle(
                      color: FacelessTheme.textSecondary,
                      fontSize: 12,
                      height: 1.35,
                    ),
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

// ---------------------------------------------------------------------------
// Hero carousel — large 9:16 poster with autoplay-ish swipe
// ---------------------------------------------------------------------------

class _HeroCarousel extends StatefulWidget {
  final List<RunSummary> featured;
  final String? baseUrl;
  final String? token;
  final void Function(RunSummary) onPlay;
  final void Function(RunSummary) onTap;
  const _HeroCarousel({
    required this.featured,
    required this.baseUrl,
    required this.token,
    required this.onPlay,
    required this.onTap,
  });

  @override
  State<_HeroCarousel> createState() => _HeroCarouselState();
}

class _HeroCarouselState extends State<_HeroCarousel> {
  final _ctrl = PageController(viewportFraction: 0.92);
  int _page = 0;
  Timer? _auto;

  @override
  void initState() {
    super.initState();
    if (widget.featured.length > 1) {
      _auto = Timer.periodic(const Duration(seconds: 6), (_) {
        if (!mounted || !_ctrl.hasClients) return;
        final next = (_page + 1) % widget.featured.length;
        _ctrl.animateToPage(next,
            duration: const Duration(milliseconds: 600), curve: Curves.easeOut);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final w = MediaQuery.of(context).size.width;
    final h = (w * 0.92) * 9 / 16 + 120; // 9:16 + room for title + buttons
    return SizedBox(
      height: h.clamp(280, 460),
      child: Column(
        children: [
          Expanded(
            child: PageView.builder(
              controller: _ctrl,
              onPageChanged: (i) => setState(() => _page = i),
              itemCount: widget.featured.length,
              itemBuilder: (_, i) =>
                  _HeroCard(
                run: widget.featured[i],
                baseUrl: widget.baseUrl,
                token: widget.token,
                onPlay: () => widget.onPlay(widget.featured[i]),
                onTap: () => widget.onTap(widget.featured[i]),
              ),
            ),
          ),
          const SizedBox(height: 8),
          if (widget.featured.length > 1)
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: List.generate(
                widget.featured.length,
                (i) => AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  margin: const EdgeInsets.symmetric(horizontal: 3),
                  width: i == _page ? 20 : 6,
                  height: 6,
                  decoration: BoxDecoration(
                    color: i == _page
                        ? FacelessTheme.accent
                        : FacelessTheme.textSecondary
                            .withValues(alpha: 0.4),
                    borderRadius: BorderRadius.circular(3),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _auto?.cancel();
    _ctrl.dispose();
    super.dispose();
  }
}

class _HeroCard extends StatelessWidget {
  final RunSummary run;
  final String? baseUrl;
  final String? token;
  final VoidCallback onPlay;
  final VoidCallback onTap;
  const _HeroCard({
    required this.run,
    required this.baseUrl,
    required this.token,
    required this.onPlay,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8),
      child: GestureDetector(
        onTap: onTap,
        child: Stack(
          fit: StackFit.expand,
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(20),
              child: _runImage(run.id, baseUrl, token, fit: BoxFit.cover),
            ),
            ClipRRect(
              borderRadius: BorderRadius.circular(20),
              child: DecoratedBox(
                decoration: BoxDecoration(gradient: FacelessTheme.heroGradient),
              ),
            ),
            Positioned(
              left: 24, right: 24, bottom: 20,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    run.title ?? context.l10n.homeUntitled,
                    textDirection: TextDirection.rtl,
                    style: const TextStyle(
                        color: Colors.white,
                        fontSize: 24,
                        fontWeight: FontWeight.w700,
                        height: 1.2,
                        shadows: [Shadow(blurRadius: 14)]),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      FilledButton.icon(
                        onPressed: onPlay,
                        icon: const Icon(Icons.play_arrow),
                        label: Text(context.l10n.homePlay,
                            style:
                                const TextStyle(fontWeight: FontWeight.w700)),
                      ),
                      const SizedBox(width: 12),
                      OutlinedButton.icon(
                        onPressed: onTap,
                        icon: const Icon(Icons.info_outline),
                        label: Text(context.l10n.homeDetails),
                      ),
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

// ---------------------------------------------------------------------------
// Series row — horizontal scroll of episodes within a series
// ---------------------------------------------------------------------------

class _SeriesRow extends StatelessWidget {
  final _Series series;
  final String? baseUrl;
  final String? token;
  final void Function(RunSummary) onTap;
  final void Function(RunSummary) onPlay;
  final void Function(RunSummary) onLongPress;
  const _SeriesRow({
    required this.series,
    required this.baseUrl,
    required this.token,
    required this.onTap,
    required this.onPlay,
    required this.onLongPress,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                Container(
                  width: 4,
                  height: 22,
                  decoration: BoxDecoration(
                    color: FacelessTheme.accent,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    series.name,
                    textDirection: TextDirection.rtl,
                    style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w700,
                        fontSize: 18),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                Text(context.l10n.homeEpisodesCount(series.episodes.length),
                    textDirection: TextDirection.rtl,
                    style: const TextStyle(
                        color: FacelessTheme.textSecondary, fontSize: 12)),
              ],
            ),
          ),
          const SizedBox(height: 10),
          SizedBox(
            height: 280,
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12),
              itemCount: series.episodes.length,
              itemBuilder: (_, i) => _PosterTile(
                run: series.episodes[i],
                baseUrl: baseUrl,
                token: token,
                onTap: () => onTap(series.episodes[i]),
                onPlay: series.episodes[i].hasVideo
                    ? () => onPlay(series.episodes[i])
                    : null,
                onLongPress: () => onLongPress(series.episodes[i]),
                episodeNumber: _extractEpNumber(series.episodes[i].title),
              ),
            ),
          ),
        ],
      ),
    );
  }

  static int? _extractEpNumber(String? title) {
    if (title == null) return null;
    final m = RegExp(r'(\d+)$').firstMatch(title.trim());
    return m == null ? null : int.tryParse(m.group(1)!);
  }
}

// ---------------------------------------------------------------------------
// Standalone row — non-series past runs
// ---------------------------------------------------------------------------

class _StandaloneRow extends StatelessWidget {
  final String title;
  final List<RunSummary> runs;
  final String? baseUrl;
  final String? token;
  final void Function(RunSummary) onTap;
  final void Function(RunSummary) onLongPress;
  const _StandaloneRow({
    required this.title,
    required this.runs,
    required this.baseUrl,
    required this.token,
    required this.onTap,
    required this.onLongPress,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                Container(
                  width: 4, height: 22,
                  decoration: BoxDecoration(
                    color: FacelessTheme.accent2,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                const SizedBox(width: 10),
                Text(title,
                    style: const TextStyle(
                        color: FacelessTheme.textPrimary,
                        fontWeight: FontWeight.w700,
                        fontSize: 18)),
                const Spacer(),
                Text('${runs.length}',
                    style: const TextStyle(
                        color: FacelessTheme.textSecondary, fontSize: 12)),
              ],
            ),
          ),
          const SizedBox(height: 10),
          SizedBox(
            height: 280,
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12),
              itemCount: runs.length,
              itemBuilder: (_, i) => _PosterTile(
                run: runs[i],
                baseUrl: baseUrl,
                token: token,
                onTap: () => onTap(runs[i]),
                onLongPress: () => onLongPress(runs[i]),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Poster tile — 9:16 thumbnail with status overlay
// ---------------------------------------------------------------------------

class _PosterTile extends StatelessWidget {
  final RunSummary run;
  final String? baseUrl;
  final String? token;
  final VoidCallback onTap;
  final VoidCallback? onPlay;
  final VoidCallback? onLongPress;
  final int? episodeNumber;
  const _PosterTile({
    required this.run,
    required this.baseUrl,
    required this.token,
    required this.onTap,
    this.onPlay,
    this.onLongPress,
    this.episodeNumber,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 6),
      child: GestureDetector(
        onTap: onTap,
        onLongPress: onLongPress,
        child: SizedBox(
          width: 130,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Stack(
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(10),
                    child: AspectRatio(
                      aspectRatio: 9 / 16,
                      child: _runImage(run.id, baseUrl, token,
                          fit: BoxFit.cover),
                    ),
                  ),
                  if (episodeNumber != null)
                    Positioned(
                      top: 6, left: 6,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: Colors.black.withValues(alpha: 0.7),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                            context.l10n.homeEpisodeAbbrev(episodeNumber!),
                            style: const TextStyle(
                                color: Colors.white,
                                fontSize: 10,
                                fontWeight: FontWeight.w700)),
                      ),
                    ),
                  Positioned(
                    bottom: 6, right: 6,
                    child: _StatusBadge(status: run.status),
                  ),
                  if (onPlay != null)
                    Positioned.fill(
                      child: Center(
                        child: Material(
                          color: Colors.black54,
                          shape: const CircleBorder(),
                          child: IconButton(
                            icon: const Icon(Icons.play_arrow,
                                color: Colors.white, size: 32),
                            onPressed: onPlay,
                          ),
                        ),
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 6),
              Flexible(
                child: Text(
                  run.title ?? context.l10n.homeUntitled,
                  textDirection: _isArabic(run.title)
                      ? TextDirection.rtl
                      : TextDirection.ltr,
                  style: const TextStyle(
                      color: Colors.white,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      height: 1.3),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  static bool _isArabic(String? s) {
    if (s == null) return false;
    for (final r in s.runes) {
      if (r >= 0x0600 && r <= 0x06FF) return true;
    }
    return false;
  }
}

class _StatusBadge extends StatelessWidget {
  final String status;
  const _StatusBadge({required this.status});

  @override
  Widget build(BuildContext context) {
    final (label, color) = switch (status) {
      RunStatus.complete => ('●', FacelessTheme.success),
      RunStatus.awaitingApproval => ('⏸', FacelessTheme.warning),
      RunStatus.runningPaid => ('●', FacelessTheme.info),
      RunStatus.creating => ('●', FacelessTheme.info),
      RunStatus.failed => ('✕', FacelessTheme.danger),
      _ => ('?', FacelessTheme.textSecondary),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.6),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(label,
          style: TextStyle(
              color: color, fontSize: 11, fontWeight: FontWeight.bold)),
    );
  }
}

// ---------------------------------------------------------------------------
// Song list row — polished card with cover, title, and a friendly status pill
// (replaces the raw `generating_song` / `complete` text in a flat ListTile).
// ---------------------------------------------------------------------------

class _SongStatusStyle {
  final String label;
  final Color color;
  final IconData icon;
  final bool working; // show a spinner instead of the icon
  const _SongStatusStyle(this.label, this.color, this.icon,
      {this.working = false});
}

_SongStatusStyle _songStatusStyle(AppLocalizations l10n, String status) {
  switch (status) {
    case 'writing_lyrics':
      return _SongStatusStyle(l10n.homeStatusWritingLyrics, FacelessTheme.info,
          Icons.edit_note,
          working: true);
    case 'awaiting_approval':
      return _SongStatusStyle(l10n.homeStatusReviewApprove,
          FacelessTheme.accent, Icons.play_circle_fill);
    case 'approved':
    case 'generating_song':
      return _SongStatusStyle(
          l10n.homeStatusComposing, FacelessTheme.info, Icons.autorenew,
          working: true);
    case 'generating_cover':
      return _SongStatusStyle(
          l10n.homeStatusDesigningCover, FacelessTheme.info, Icons.autorenew,
          working: true);
    case 'detecting_beats':
      return _SongStatusStyle(
          l10n.homeStatusSyncingBeat, FacelessTheme.info, Icons.autorenew,
          working: true);
    case 'aligning':
      return _SongStatusStyle(
          l10n.homeStatusSyncingLyrics, FacelessTheme.info, Icons.autorenew,
          working: true);
    case 'assembling':
      return _SongStatusStyle(
          l10n.homeStatusRendering, FacelessTheme.info, Icons.autorenew,
          working: true);
    case 'complete':
      return _SongStatusStyle(
          l10n.homeStatusReady, FacelessTheme.success, Icons.check_circle);
    case 'failed':
      return _SongStatusStyle(
          l10n.statusFailed, FacelessTheme.danger, Icons.error_outline);
    default:
      // Unknown codes are pretty-printed raw — they're debug text by definition.
      final pretty = status.isEmpty
          ? l10n.homeStatusPending
          : (status[0].toUpperCase() + status.substring(1)).replaceAll('_', ' ');
      return _SongStatusStyle(pretty, FacelessTheme.textSecondary, Icons.circle);
  }
}

class _SongStatusPill extends StatelessWidget {
  final _SongStatusStyle style;
  final bool compact; // smaller chip for overlay use (e.g. recent tiles)
  const _SongStatusPill({required this.style, this.compact = false});

  @override
  Widget build(BuildContext context) {
    final glyph = compact ? 11.0 : 13.0;
    final spin = compact ? 9.0 : 11.0;
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
          if (style.working)
            SizedBox(
              width: spin,
              height: spin,
              child: CircularProgressIndicator(
                  strokeWidth: 2,
                  valueColor: AlwaysStoppedAnimation<Color>(style.color)),
            )
          else
            Icon(style.icon, size: glyph, color: style.color),
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

/// Tiny "● Released" chip — mirrors the status-pill visual so it can sit
/// beside one. Shown on song cards / discography rows when the user has
/// marked the song live on the stores (Distribution feature).
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

class _SongThumbPlaceholder extends StatelessWidget {
  const _SongThumbPlaceholder();
  @override
  Widget build(BuildContext context) => Container(
        color: FacelessTheme.surface2,
        child: Icon(Icons.music_note,
            color: FacelessTheme.accent.withValues(alpha: 0.7), size: 26),
      );
}

/// Cover image loaded from the token-bearing cover-URL future, with a
/// branded placeholder while loading / on error.
class _SongCover extends StatelessWidget {
  final Future<Uri> future;
  final BoxFit fit;
  const _SongCover({required this.future, this.fit = BoxFit.cover});

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Uri>(
      future: future,
      builder: (ctx, snap) {
        if (!snap.hasData) return const _SongThumbPlaceholder();
        return CachedNetworkImage(
          imageUrl: snap.data!.toString(),
          fit: fit,
          fadeInDuration: const Duration(milliseconds: 180),
          placeholder: (_, _) => const _SongThumbPlaceholder(),
          errorWidget: (_, _, _) => const _SongThumbPlaceholder(),
        );
      },
    );
  }
}

class _PlayButton extends StatelessWidget {
  final double size;
  const _PlayButton({this.size = 44});
  @override
  Widget build(BuildContext context) => Container(
        width: size,
        height: size,
        decoration: const BoxDecoration(
          shape: BoxShape.circle,
          gradient: LinearGradient(colors: [Color(0xFFF6D27A), Color(0xFFE7B53C)]),
          boxShadow: [
            BoxShadow(
                color: Color(0x73E7B53C), blurRadius: 16, offset: Offset(0, 6))
          ],
        ),
        child: Icon(Icons.play_arrow_rounded,
            color: const Color(0xFF1A1205), size: size * 0.52),
      );
}

class _EqBars extends StatelessWidget {
  const _EqBars();
  @override
  Widget build(BuildContext context) {
    const heights = [6.0, 13.0, 8.0, 15.0, 7.0, 11.0];
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        for (final h in heights)
          Padding(
            padding: const EdgeInsetsDirectional.only(end: 3),
            child: Container(
              width: 3,
              height: h,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(2),
                gradient: const LinearGradient(
                    begin: Alignment.bottomCenter,
                    end: Alignment.topCenter,
                    colors: [Color(0xFFE7B53C), Color(0xFFF6D27A)]),
              ),
            ),
          ),
      ],
    );
  }
}

class _SongSectionTitle extends StatelessWidget {
  final String title;
  final String trailing;
  const _SongSectionTitle({required this.title, required this.trailing});
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

class _SongSearchBar extends StatefulWidget {
  final String initial;
  final ValueChanged<String> onChanged;
  const _SongSearchBar({required this.initial, required this.onChanged});
  @override
  State<_SongSearchBar> createState() => _SongSearchBarState();
}

class _SongSearchBarState extends State<_SongSearchBar> {
  late final TextEditingController _c =
      TextEditingController(text: widget.initial);
  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 10, 16, 2),
      child: TextField(
        controller: _c,
        onChanged: (v) {
          widget.onChanged(v);
          setState(() {}); // toggle the clear button
        },
        textInputAction: TextInputAction.search,
        style: const TextStyle(color: FacelessTheme.textPrimary, fontSize: 14),
        decoration: InputDecoration(
          isDense: true,
          hintText: context.l10n.homeSearchHint,
          hintStyle:
              const TextStyle(color: FacelessTheme.textSecondary, fontSize: 14),
          prefixIcon: const Icon(Icons.search,
              color: FacelessTheme.textSecondary, size: 20),
          suffixIcon: _c.text.isEmpty
              ? null
              : IconButton(
                  icon: const Icon(Icons.close,
                      size: 18, color: FacelessTheme.textSecondary),
                  onPressed: () {
                    _c.clear();
                    widget.onChanged('');
                    setState(() {});
                  },
                ),
          filled: true,
          fillColor: FacelessTheme.surface,
          contentPadding: const EdgeInsets.symmetric(vertical: 12),
          enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(14),
              borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.06))),
          focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(14),
              borderSide:
                  const BorderSide(color: FacelessTheme.accent, width: 1.5)),
        ),
      ),
    );
  }
}

class _SongHero extends StatelessWidget {
  final String title;
  final String status;
  final Future<Uri> coverUrlFuture;
  final VoidCallback onTap;
  const _SongHero({
    required this.title,
    required this.status,
    required this.coverUrlFuture,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final st = _songStatusStyle(context.l10n, status);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 2),
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          decoration: BoxDecoration(
            color: FacelessTheme.surface,
            borderRadius: BorderRadius.circular(22),
            border: Border.all(color: FacelessTheme.border),
            boxShadow: FacelessTheme.softShadow,
          ),
          clipBehavior: Clip.antiAlias,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(16),
                child: SizedBox(
                  height: 168,
                  width: double.infinity,
                  child: _SongCover(future: coverUrlFuture, fit: BoxFit.cover),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(context.l10n.homeLatestRelease,
                        style: const TextStyle(
                            color: FacelessTheme.accent,
                            fontSize: 11,
                            fontWeight: FontWeight.w800,
                            letterSpacing: 1.4)),
                    const SizedBox(height: 8),
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Text(title,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(
                                      color: FacelessTheme.textPrimary,
                                      fontSize: 24,
                                      fontWeight: FontWeight.w800)),
                              const SizedBox(height: 9),
                              _SongStatusPill(style: st),
                            ],
                          ),
                        ),
                        const SizedBox(width: 12),
                        const _PlayButton(size: 50),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _RecentTile extends StatelessWidget {
  final String title;
  final String status;
  final Future<Uri> coverUrlFuture;
  final VoidCallback onTap;
  const _RecentTile({
    required this.title,
    required this.status,
    required this.coverUrlFuture,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final st = _songStatusStyle(context.l10n, status);
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 150,
        decoration: BoxDecoration(
          color: FacelessTheme.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: FacelessTheme.border),
          boxShadow: FacelessTheme.softShadow,
        ),
        clipBehavior: Clip.antiAlias,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: SizedBox(
                width: double.infinity,
                height: 110,
                child: _SongCover(future: coverUrlFuture, fit: BoxFit.cover),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(10, 9, 10, 10),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                          color: FacelessTheme.textPrimary,
                          fontSize: 13,
                          fontWeight: FontWeight.w700)),
                  const SizedBox(height: 7),
                  _SongStatusPill(style: st, compact: true),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SongCardC extends StatelessWidget {
  final String title;
  final String status;
  final bool released;
  final bool onYoutube;
  final Future<Uri> coverUrlFuture;
  final VoidCallback onTap;
  const _SongCardC({
    required this.title,
    required this.status,
    this.released = false,
    this.onYoutube = false,
    required this.coverUrlFuture,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final st = _songStatusStyle(context.l10n, status);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 6, 16, 0),
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
            onTap: onTap,
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(13),
                    child: SizedBox(
                      width: 70,
                      height: 70,
                      child: _SongCover(future: coverUrlFuture, fit: BoxFit.cover),
                    ),
                  ),
                  const SizedBox(width: 13),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(title,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                                color: FacelessTheme.textPrimary,
                                fontSize: 15,
                                fontWeight: FontWeight.w700)),
                        const SizedBox(height: 8),
                        const _EqBars(),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 6,
                          runSpacing: 4,
                          children: [
                            _SongStatusPill(style: st),
                            if (released) const _ReleasedBadge(),
                            if (onYoutube) const _YoutubeBadge(),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 10),
                  const _PlayButton(size: 44),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Shared image widget — token in query string
// ---------------------------------------------------------------------------

Widget _runImage(String runId, String? baseUrl, String? token,
    {BoxFit fit = BoxFit.cover}) {
  if (baseUrl == null || token == null) {
    return Container(color: FacelessTheme.surface2);
  }
  final base = baseUrl.endsWith('/')
      ? baseUrl.substring(0, baseUrl.length - 1)
      : baseUrl;
  return CachedNetworkImage(
    imageUrl: '$base/runs/$runId/thumbnail?token=$token',
    fit: fit,
    placeholder: (_, _) => Container(color: FacelessTheme.surface2),
    errorWidget: (_, _, _) => Container(
      color: FacelessTheme.surface2,
      child: const Icon(Icons.movie, color: FacelessTheme.textSecondary),
    ),
  );
}

// ---------------------------------------------------------------------------
// Empty / error states
// ---------------------------------------------------------------------------

// Theme metadata — drives the home gallery + the New Run screen's chips.
// Display strings live in the ARB files; see [_themeStrings].
class _ThemeInfo {
  final String id;
  final IconData icon;
  final List<Color> gradient;
  const _ThemeInfo(this.id, this.icon, this.gradient);
}

/// Localized (title, subtitle) for a theme id. Ids are API values — never
/// shown raw except as a last-resort fallback for unknown ids.
(String, String) _themeStrings(AppLocalizations l10n, String id) =>
    switch (id) {
      'folkloric' => (l10n.homeThemeFolkloric, l10n.homeThemeFolkloricDesc),
      'urban' => (l10n.homeThemeUrban, l10n.homeThemeUrbanDesc),
      'wilderness' => (l10n.homeThemeWilderness, l10n.homeThemeWildernessDesc),
      'memory' => (l10n.homeThemeMemory, l10n.homeThemeMemoryDesc),
      'domestic' => (l10n.homeThemeDomestic, l10n.homeThemeDomesticDesc),
      'travel' => (l10n.homeThemeTravel, l10n.homeThemeTravelDesc),
      'tech' => (l10n.homeThemeTech, l10n.homeThemeTechDesc),
      'workplace' => (l10n.homeThemeWorkplace, l10n.homeThemeWorkplaceDesc),
      _ => (id, ''),
    };

const _allThemes = <_ThemeInfo>[
  _ThemeInfo('folkloric',
      Icons.account_balance_outlined,
      [Color(0xFFB07F1F), Color(0xFFE7B53C)]),
  _ThemeInfo('urban',
      Icons.location_city_outlined,
      [Color(0xFF3B82F6), Color(0xFF1E40AF)]),
  _ThemeInfo('wilderness',
      Icons.forest_outlined,
      [Color(0xFF059669), Color(0xFF064E3B)]),
  _ThemeInfo('memory',
      Icons.psychology_outlined,
      [Color(0xFF8B5CF6), Color(0xFF5B21B6)]),
  _ThemeInfo('domestic',
      Icons.home_outlined,
      [Color(0xFFEA580C), Color(0xFF9A3412)]),
  _ThemeInfo('travel',
      Icons.travel_explore_outlined,
      [Color(0xFF0D9488), Color(0xFF134E4A)]),
  _ThemeInfo('tech',
      Icons.memory_outlined,
      [Color(0xFF06B6D4), Color(0xFF155E75)]),
  _ThemeInfo('workplace',
      Icons.business_center_outlined,
      [Color(0xFF64748B), Color(0xFF334155)]),
];


class _EmptyView extends StatelessWidget {
  final void Function({String? initialTheme}) onCreate;
  final String? currentPlan;
  const _EmptyView({required this.onCreate, this.currentPlan});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      physics: const AlwaysScrollableScrollPhysics(),
      child: _HomeContent(
        onCreate: onCreate,
        showHowItWorks: true,
        currentPlan: currentPlan,
      ),
    );
  }
}


/// The new content-rich Home body. Rendered above the run list (or alone
/// when the user has no runs yet). Sections:
///   1. Brand hero with primary CTA
///   2. Theme gallery (8 tappable shortcuts that pre-fill New Run)
///   3. "How it works" 3-step card (only when [showHowItWorks])
///   4. Pricing teaser (3 plan chips → BillingScreen)
class _HomeContent extends StatelessWidget {
  final void Function({String? initialTheme}) onCreate;
  final bool showHowItWorks;
  final String? currentPlan;
  const _HomeContent({
    required this.onCreate,
    required this.showHowItWorks,
    this.currentPlan,
  });

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        // Two ambient radial glows so the bg has depth
        Positioned.fill(
          child: IgnorePointer(
            child: DecoratedBox(
              decoration: const BoxDecoration(
                gradient: RadialGradient(
                  center: Alignment(-0.6, -0.4),
                  radius: 1.1,
                  colors: [Color(0x33E7B53C), Color(0x000A0E1A)],
                ),
              ),
            ),
          ),
        ),
        Positioned.fill(
          child: IgnorePointer(
            child: DecoratedBox(
              decoration: const BoxDecoration(
                gradient: RadialGradient(
                  center: Alignment(0.7, 0.6),
                  radius: 1.0,
                  colors: [Color(0x288B5CF6), Color(0x000A0E1A)],
                ),
              ),
            ),
          ),
        ),
        Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 720),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 32, 20, 48),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _Hero(onCreate: () => onCreate()),
                  const SizedBox(height: 36),
                  _ThemeGallerySection(
                    onPick: (themeId) => onCreate(initialTheme: themeId),
                  ),
                  if (showHowItWorks) ...[
                    const SizedBox(height: 36),
                    const _HowItWorksCard(),
                  ],
                  const SizedBox(height: 36),
                  _PricingTeaser(currentPlan: currentPlan),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _Hero extends StatelessWidget {
  final VoidCallback onCreate;
  const _Hero({required this.onCreate});
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(28, 32, 28, 32),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        color: FacelessTheme.surface,
        border: Border.all(color: FacelessTheme.border),
        boxShadow: FacelessTheme.softShadow,
      ),
      child: Column(
        children: [
          // Brand mark — crescent + accent star inside a gold disc.
          Container(
            width: 72,
            height: 72,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(
                  color: FacelessTheme.accent.withValues(alpha: 0.35),
                  blurRadius: 24,
                  offset: const Offset(0, 6),
                ),
              ],
            ),
            child: const FacelessLogo(size: 72),
          ),
          const SizedBox(height: 18),
          Text(
            'Faceless',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.headlineMedium!.copyWith(
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0.5,
                ),
          ),
          const SizedBox(height: 6),
          Text(
            context.l10n.homeHeroTagline,
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: FacelessTheme.textSecondary,
              fontSize: 14,
              letterSpacing: 0.3,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            context.l10n.homeHeroSubtitle,
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: FacelessTheme.textSecondary,
              fontSize: 13,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 22),
          SizedBox(
            width: 280,
            height: 48,
            child: FilledButton.icon(
              onPressed: onCreate,
              icon: const Icon(Icons.auto_awesome),
              label: Text(
                context.l10n.homeStartCreating,
                style: const TextStyle(
                    fontSize: 15, fontWeight: FontWeight.w700),
              ),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            context.l10n.homeFreeToWrite,
            style: TextStyle(
              color: FacelessTheme.textSecondary.withValues(alpha: 0.7),
              fontSize: 11,
              letterSpacing: 0.4,
            ),
          ),
        ],
      ),
    );
  }
}

class _ThemeGallerySection extends StatelessWidget {
  final void Function(String themeId) onPick;
  const _ThemeGallerySection({required this.onPick});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _SectionTitle(
          title: context.l10n.homeChooseTheme,
          subtitle: context.l10n.homeChooseThemeSubtitle,
        ),
        const SizedBox(height: 14),
        GridView.count(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          crossAxisCount: 2,
          childAspectRatio: 2.6,
          mainAxisSpacing: 10,
          crossAxisSpacing: 10,
          children: [
            for (final t in _allThemes)
              _ThemeCard(theme: t, onTap: () => onPick(t.id)),
          ],
        ),
      ],
    );
  }
}

class _ThemeCard extends StatelessWidget {
  final _ThemeInfo theme;
  final VoidCallback onTap;
  const _ThemeCard({required this.theme, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final (title, subtitle) = _themeStrings(context.l10n, theme.id);
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                theme.gradient[0].withValues(alpha: 0.22),
                theme.gradient[1].withValues(alpha: 0.10),
              ],
            ),
            border: Border.all(
              color: theme.gradient[0].withValues(alpha: 0.45),
              width: 1,
            ),
          ),
          child: Row(
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: theme.gradient[0].withValues(alpha: 0.25),
                ),
                child: Icon(theme.icon,
                    color: theme.gradient[0], size: 22),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        color: FacelessTheme.textPrimary,
                        fontWeight: FontWeight.w700,
                        fontSize: 14,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 2),
                    Text(
                      subtitle,
                      style: const TextStyle(
                        color: FacelessTheme.textSecondary,
                        fontSize: 11,
                        height: 1.3,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final String title;
  final String? subtitle;
  const _SectionTitle({
    required this.title,
    this.subtitle,
  });
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(
              color: FacelessTheme.textPrimary,
              fontWeight: FontWeight.w700,
              fontSize: 17,
              letterSpacing: 0.3,
            ),
          ),
          if (subtitle != null) ...[
            const SizedBox(height: 3),
            Text(
              subtitle!,
              style: const TextStyle(
                color: FacelessTheme.textSecondary,
                fontSize: 12,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _HowItWorksCard extends StatelessWidget {
  const _HowItWorksCard();
  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _SectionTitle(title: context.l10n.homeHowItWorks),
        const SizedBox(height: 12),
        Container(
          decoration: BoxDecoration(
            color: FacelessTheme.surface,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: FacelessTheme.textSecondary.withValues(alpha: 0.12),
            ),
          ),
          padding:
              const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
          child: Column(
            children: [
              _Step(
                number: '1',
                title: context.l10n.homeStep1Title,
                subtitle: context.l10n.homeStep1Subtitle,
              ),
              const _StepDivider(),
              _Step(
                number: '2',
                title: context.l10n.homeStep2Title,
                subtitle: context.l10n.homeStep2Subtitle,
              ),
              const _StepDivider(),
              _Step(
                number: '3',
                title: context.l10n.homeStep3Title,
                subtitle: context.l10n.homeStep3Subtitle,
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _PricingTeaser extends StatelessWidget {
  /// User's current plan slug from /billing/plan ('free' / 'starter' /
  /// 'creator' / 'pro'). When null or 'free', we recommend Creator. When
  /// the user has a paid plan, we highlight that plan as "Your plan".
  final String? currentPlan;
  const _PricingTeaser({this.currentPlan});

  @override
  Widget build(BuildContext context) {
    final cp = currentPlan?.toLowerCase();
    final paid = cp != null && cp != 'free';

    _PlanBadge badgeFor(String slug) {
      if (paid) {
        return cp == slug ? _PlanBadge.current : _PlanBadge.none;
      }
      return slug == 'creator' ? _PlanBadge.recommended : _PlanBadge.none;
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _SectionTitle(title: context.l10n.homePlans),
        const SizedBox(height: 12),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: _PlanChip(
                name: context.l10n.homePlanStarter,
                price: r'$9',
                credits: 12,
                badge: badgeFor('starter'),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _PlanChip(
                name: context.l10n.homePlanCreator,
                price: r'$29',
                credits: 60,
                badge: badgeFor('creator'),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _PlanChip(
                name: context.l10n.homePlanPro,
                price: r'$79',
                credits: 200,
                badge: badgeFor('pro'),
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Center(
          child: TextButton.icon(
            icon: const Icon(Icons.chevron_right, size: 18),
            label: Text(context.l10n.homeSeeFullPlans),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const BillingScreen()),
            ),
          ),
        ),
      ],
    );
  }
}

enum _PlanBadge { none, recommended, current }

class _PlanChip extends StatelessWidget {
  final String name;
  final String price;
  final int credits;
  final _PlanBadge badge;
  const _PlanChip({
    required this.name,
    required this.price,
    required this.credits,
    required this.badge,
  });
  @override
  Widget build(BuildContext context) {
    // Only the user's ACTUAL current plan gets the gold border + tinted bg.
    // A "Recommended" hint on Creator (free users) is a subtle text badge
    // only — earlier this used the same highlight visuals and several
    // users read it as "you are already on Creator".
    final isCurrent = badge == _PlanBadge.current;
    return Container(
      padding: const EdgeInsets.fromLTRB(10, 12, 10, 14),
      decoration: BoxDecoration(
        color: isCurrent
            ? FacelessTheme.accent.withValues(alpha: 0.10)
            : FacelessTheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isCurrent
              ? FacelessTheme.accent.withValues(alpha: 0.6)
              : FacelessTheme.textSecondary.withValues(alpha: 0.15),
          width: isCurrent ? 1.5 : 1,
        ),
      ),
      child: Column(
        children: [
          SizedBox(
            height: 18,
            child: switch (badge) {
              _PlanBadge.none => const SizedBox.shrink(),
              _PlanBadge.current => Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: FacelessTheme.accent.withValues(alpha: 0.22),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    context.l10n.homeYourPlan,
                    style: const TextStyle(
                      color: FacelessTheme.accent,
                      fontSize: 9,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.4,
                    ),
                  ),
                ),
              _PlanBadge.recommended => Text(
                  context.l10n.homeRecommended,
                  style: TextStyle(
                    color: FacelessTheme.textSecondary.withValues(alpha: 0.85),
                    fontSize: 9,
                    fontWeight: FontWeight.w600,
                    letterSpacing: 0.4,
                  ),
                ),
            },
          ),
          const SizedBox(height: 6),
          Text(name,
              style: const TextStyle(
                color: FacelessTheme.textPrimary,
                fontWeight: FontWeight.w700,
                fontSize: 13,
              )),
          const SizedBox(height: 4),
          Text(price,
              style: const TextStyle(
                color: FacelessTheme.accent,
                fontWeight: FontWeight.w700,
                fontSize: 18,
              )),
          const SizedBox(height: 2),
          Text(context.l10n.homeCreditsCount(credits),
              style: const TextStyle(
                color: FacelessTheme.textSecondary,
                fontSize: 11,
              )),
        ],
      ),
    );
  }
}

class _Step extends StatelessWidget {
  final String number;
  final String title;
  final String subtitle;
  const _Step({
    required this.number,
    required this.title,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 14),
      child: Row(
        children: [
          Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: FacelessTheme.accent.withValues(alpha: 0.18),
              border: Border.all(
                color: FacelessTheme.accent.withValues(alpha: 0.5),
                width: 1,
              ),
            ),
            alignment: Alignment.center,
            child: Text(
              number,
              style: const TextStyle(
                color: FacelessTheme.accent,
                fontWeight: FontWeight.w700,
                fontSize: 14,
              ),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    color: FacelessTheme.textPrimary,
                    fontWeight: FontWeight.w600,
                    fontSize: 14,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: const TextStyle(
                    color: FacelessTheme.textSecondary,
                    fontSize: 12,
                    height: 1.35,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _StepDivider extends StatelessWidget {
  const _StepDivider();
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsetsDirectional.only(start: 16),
      child: Divider(
        height: 1,
        color: FacelessTheme.textSecondary.withValues(alpha: 0.08),
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  final String error;
  final VoidCallback onSettings;
  final VoidCallback onRetry;
  const _ErrorView({
    required this.error,
    required this.onSettings,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) => SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        child: SizedBox(
          height: MediaQuery.of(context).size.height,
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.error_outline,
                      size: 64,
                      color: Theme.of(context).colorScheme.error),
                  const SizedBox(height: 16),
                  Text(context.l10n.homeServerUnreachable,
                      style: const TextStyle(
                          fontSize: 18, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  Text(error,
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                          color: FacelessTheme.textSecondary)),
                  const SizedBox(height: 24),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      OutlinedButton.icon(
                          onPressed: onRetry,
                          icon: const Icon(Icons.refresh),
                          label: Text(context.l10n.commonRetry)),
                      const SizedBox(width: 12),
                      FilledButton.icon(
                          onPressed: onSettings,
                          icon: const Icon(Icons.settings),
                          label: Text(context.l10n.homeSettings)),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      );
}



class _BalanceBadge extends StatefulWidget {
  const _BalanceBadge();
  @override
  State<_BalanceBadge> createState() => _BalanceBadgeState();
}

class _BalanceBadgeState extends State<_BalanceBadge> {
  int? _balance;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    try {
      final b = await FacelessApiClient(FacelessSettings()).getBalance();
      if (mounted) setState(() => _balance = b.balance);
    } catch (_) {
      // Silent on error — non-critical UI element, don't crash the home screen.
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_balance == null) return const SizedBox.shrink();
    return GestureDetector(
      onTap: () async {
        await Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => const BillingScreen()),
        );
        // Refresh on return — user may have just topped up.
        _refresh();
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: FacelessTheme.surface2,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.monetization_on,
                       color: FacelessTheme.accent, size: 16),
            const SizedBox(width: 6),
            Text('$_balance',
                 style: const TextStyle(fontWeight: FontWeight.w600)),
          ],
        ),
      ),
    );
  }
}


/// Empty state shown on the Song tab when the user has no songs yet.
/// Offers a "Try one of these" set of one-tap samples that pre-fill
/// the new-song form with a vetted theme + style preset, so a new
/// user can hit "Generate draft" without typing anything.
class _SongsEmptyState extends StatelessWidget {
  final VoidCallback onCreate;
  final void Function(String theme, String presetLabel) onTrySample;
  const _SongsEmptyState({required this.onCreate, required this.onTrySample});

  // Samples paired with the style preset that best fits the vibe.
  // Preset labels MUST match _kStylePresets in new_song_screen.dart.
  static const _samples = <(String, String, String)>[
    // (emoji, theme prefilled, preset label)
    ('🌙', 'أغنية رومانسية عن القمر والشوق', 'Romantic Arabic (reference)'),
    ('💔', 'أغنية حزينة عن الفراق', 'Sad Arabic Ballad'),
    ('🎶', 'أغنية بحرية خليجية عن البحر والصيد', 'Khaleeji Romantic'),
    ('🎸', 'A quiet acoustic song about long drives at night',
        'Acoustic Slow'),
  ];

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(24, 48, 24, 24),
      children: [
        const Icon(Icons.music_note,
            size: 64, color: FacelessTheme.textSecondary),
        const SizedBox(height: 12),
        Text(
          context.l10n.homeMakeFirstSong,
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 8),
        Text(
          context.l10n.homePickSampleHint,
          textAlign: TextAlign.center,
          style: const TextStyle(color: FacelessTheme.textSecondary),
        ),
        const SizedBox(height: 24),
        for (final (emoji, theme, preset) in _samples)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 6),
            child: OutlinedButton(
              onPressed: () => onTrySample(theme, preset),
              style: OutlinedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 16),
                alignment: AlignmentDirectional.centerStart,
              ),
              child: Row(
                children: [
                  Text(emoji, style: const TextStyle(fontSize: 22)),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(theme,
                            textAlign: TextAlign.start,
                            style: const TextStyle(fontWeight: FontWeight.w500)),
                        const SizedBox(height: 2),
                        Text(preset,
                            style: const TextStyle(
                                fontSize: 11,
                                color: FacelessTheme.textSecondary)),
                      ],
                    ),
                  ),
                  const Icon(Icons.chevron_right,
                      color: FacelessTheme.textSecondary, size: 18),
                ],
              ),
            ),
          ),
        const SizedBox(height: 24),
        Center(
          child: FilledButton.icon(
            onPressed: onCreate,
            icon: const Icon(Icons.add),
            label: Text(context.l10n.homeNewSongFromScratch),
          ),
        ),
      ],
    );
  }
}

/// Branded loading state — three skeleton run cards with a slow shimmer.
/// Replaces a bare CircularProgressIndicator() because cold-loads of
/// the runs/songs lists take ~1–3 seconds over a custom domain and
/// showing the page's shape (vs an empty spinner) feels faster.
class _LoadingPlaceholder extends StatefulWidget {
  const _LoadingPlaceholder();

  @override
  State<_LoadingPlaceholder> createState() => _LoadingPlaceholderState();
}

class _LoadingPlaceholderState extends State<_LoadingPlaceholder>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(16, 24, 16, 24),
      physics: const NeverScrollableScrollPhysics(),
      itemCount: 3,
      itemBuilder: (ctx, i) => Padding(
        padding: const EdgeInsets.only(bottom: 14),
        child: AnimatedBuilder(
          animation: _ctrl,
          builder: (_, __) {
            final t = 0.35 + 0.25 * _ctrl.value; // 0.35 → 0.60 → 0.35
            return Container(
              height: 96,
              decoration: BoxDecoration(
                color: FacelessTheme.surface.withValues(alpha: t),
                borderRadius: BorderRadius.circular(14),
              ),
              child: Row(
                children: [
                  Container(
                    width: 96,
                    height: 96,
                    decoration: BoxDecoration(
                      color: FacelessTheme.surface2.withValues(alpha: t),
                      borderRadius: const BorderRadius.only(
                        topLeft: Radius.circular(14),
                        bottomLeft: Radius.circular(14),
                      ),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Container(
                          width: 180,
                          height: 14,
                          decoration: BoxDecoration(
                            color: FacelessTheme.surface2
                                .withValues(alpha: t * 1.4),
                            borderRadius: BorderRadius.circular(4),
                          ),
                        ),
                        const SizedBox(height: 10),
                        Container(
                          width: 110,
                          height: 10,
                          decoration: BoxDecoration(
                            color: FacelessTheme.surface2
                                .withValues(alpha: t),
                            borderRadius: BorderRadius.circular(4),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Artist Core — home artists row tiles
// ---------------------------------------------------------------------------

/// Avatar circle + name, tap opens the artist screen.
class _ArtistCircleTile extends StatelessWidget {
  final Artist artist;
  final FacelessApiClient client;
  final VoidCallback onTap;
  const _ArtistCircleTile({
    required this.artist,
    required this.client,
    required this.onTap,
  });

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
            ArtistAvatar(artist: artist, client: client, size: 56),
            const SizedBox(height: 4),
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

/// Soft "＋" circle that opens the create-artist form.
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
                color: FacelessTheme.surface,
                shape: BoxShape.circle,
                border: Border.all(color: FacelessTheme.border, width: 1.4),
              ),
              child: const Icon(Icons.add,
                  color: FacelessTheme.textSecondary, size: 26),
            ),
            const SizedBox(height: 4),
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
