import 'dart:async';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../api/settings.dart';
import '../config.dart';
import '../theme.dart';
import '../widgets/faceless_logo.dart';
import 'billing_screen.dart';
import 'cost_screen.dart';
import 'new_run_screen.dart';
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

  @override
  void initState() {
    super.initState();
    _client = FacelessApiClient(_settings);
    _loadAndRefresh();
  }

  Future<void> _loadAndRefresh() async {
    _baseUrl = await _settings.baseUrl();
    _token = _currentBearerToken();
    if (mounted) {
      setState(() {
        _runsFuture = _client.listRuns();
        _songsFuture = _client.listSongs();
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
    });
    await _runsFuture;
    _fetchSpend();
  }

  Future<void> _cleanupFailed() async {
    final yes = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Clean up failed runs?'),
        content: const Text(
          'This permanently deletes every run currently in Failed status. '
          'Running and complete runs are not touched.',
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          FilledButton(
              style: FilledButton.styleFrom(
                  backgroundColor: FacelessTheme.danger,
                  foregroundColor: Colors.white),
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Delete all failed')),
        ],
      ),
    );
    if (yes != true || !mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    try {
      final deleted = await _client.cleanupFailedRuns();
      if (!mounted) return;
      messenger.showSnackBar(SnackBar(
          content: Text('Removed ${deleted.length} failed run(s)')));
      _refresh();
    } catch (e) {
      if (!mounted) return;
      messenger.showSnackBar(SnackBar(content: Text('Cleanup failed: $e')));
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
        title: const Text('Delete this run?'),
        content: Text(
          'This permanently removes the run dir, including any generated '
          'clips and final.mp4. ${run.title ?? run.id}',
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          FilledButton(
              style: FilledButton.styleFrom(
                  backgroundColor: FacelessTheme.danger,
                  foregroundColor: Colors.white),
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Delete')),
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
        SnackBar(content: Text('Deleted ${run.title ?? run.id}')),
      );
      _refresh();
    } catch (e) {
      if (!mounted) return;
      messenger.showSnackBar(
        SnackBar(content: Text('Delete failed: $e')),
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
        backgroundColor: FacelessTheme.bg,
        elevation: 0,
        scrolledUnderElevation: 0,
        title: Row(
          children: [
            const FacelessLogo(size: 30),
            const SizedBox(width: 10),
            const Text('Faceless',
                style: TextStyle(fontWeight: FontWeight.w700)),
          ],
        ),
        actions: [
          const Padding(
            padding: EdgeInsets.only(right: 4),
            child: Center(child: _BalanceBadge()),
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh',
            onPressed: _refresh,
          ),
          // Only show the saved-voices entry when on the Song tab —
          // it's a song-mode concept, irrelevant to horror runs.
          if (_mode == 'song')
            IconButton(
              icon: const Icon(Icons.record_voice_over),
              tooltip: 'Saved voices',
              onPressed: () => Navigator.of(context).push(MaterialPageRoute(
                builder: (_) => PersonasScreen(client: _client),
              )),
            ),
          IconButton(
            icon: const Icon(Icons.settings),
            tooltip: 'Settings',
            onPressed: _openSettings,
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: SegmentedButton<String>(
              segments: const [
                ButtonSegment(
                    value: 'horror',
                    label: Text('Horror'),
                    icon: Icon(Icons.movie)),
                ButtonSegment(
                    value: 'song',
                    label: Text('Song'),
                    icon: Icon(Icons.music_note)),
              ],
              selected: {_mode},
              onSelectionChanged: (s) => setState(() {
                _mode = s.first;
                if (_mode == 'song' && _songsFuture == null) {
                  _songsFuture = _client.listSongs();
                }
              }),
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
              return const Center(child: CircularProgressIndicator());
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
                  const SliverFillRemaining(
                    hasScrollBody: false,
                    child: Center(
                      child: Padding(
                        padding: EdgeInsets.all(32),
                        child: Text(
                          'No runs match this filter.',
                          style: TextStyle(
                              color: FacelessTheme.textSecondary),
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
                      title: 'All Runs',
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
          final songs = snap.data ?? [];
          if (songs.isEmpty) {
            return _SongsEmptyState(
              onCreate: _openNewSong,
              onTrySample: (theme, presetLabel) =>
                  _openNewSongWithSample(theme, presetLabel),
            );
          }
          // itemCount = songs + 1 header row that holds the "New song"
          // button. Without this row the user is stuck after their first
          // run (the empty-state CTA disappears once songs.isNotEmpty).
          return ListView.builder(
            itemCount: songs.length + 1,
            itemBuilder: (context, i) {
              if (i == 0) {
                return Padding(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
                  child: SizedBox(
                    width: double.infinity,
                    child: FilledButton.icon(
                      onPressed: _openNewSong,
                      icon: const Icon(Icons.add),
                      label: const Text('New song'),
                    ),
                  ),
                );
              }
              final s = songs[i - 1];
              return ListTile(
                leading: s.hasVideo
                    ? FutureBuilder<Uri>(
                        future: _client.songCoverUrl(s.id),
                        builder: (ctx, snap) => snap.hasData
                            ? Image.network(
                                snap.data!.toString(),
                                width: 56,
                                height: 56,
                                fit: BoxFit.cover,
                                errorBuilder: (_, e, stack) =>
                                    const Icon(Icons.music_note, size: 32),
                              )
                            : const Icon(Icons.music_note, size: 32),
                      )
                    : const Icon(Icons.music_note, size: 32),
                title: Text(s.title ?? s.theme ?? '(untitled)'),
                subtitle: Text(s.status),
                onTap: () {
                  if (s.status == 'awaiting_approval') {
                    Navigator.of(context).push(MaterialPageRoute(
                      builder: (_) =>
                          SongApproveScreen(client: _client, runId: s.id),
                    ));
                  } else {
                    Navigator.of(context).push(MaterialPageRoute(
                      builder: (_) =>
                          SongDetailScreen(client: _client, runId: s.id),
                    ));
                  }
                },
              );
            },
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
                          Text('(${spend!.runCount} runs)',
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
                  label: Text('Clean $failedCount failed',
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
                    label: 'All',
                    count: counts['all'] ?? 0,
                    selected: filter == 'all',
                    onTap: () => onFilter('all')),
                _FilterChip(
                    label: 'Complete',
                    count: counts['complete'] ?? 0,
                    selected: filter == 'complete',
                    onTap: () => onFilter('complete'),
                    color: FacelessTheme.success),
                _FilterChip(
                    label: 'Awaiting',
                    count: counts['awaiting'] ?? 0,
                    selected: filter == 'awaiting',
                    onTap: () => onFilter('awaiting'),
                    color: FacelessTheme.warning),
                _FilterChip(
                    label: 'Running',
                    count: counts['running'] ?? 0,
                    selected: filter == 'running',
                    onTap: () => onFilter('running'),
                    color: FacelessTheme.info),
                _FilterChip(
                    label: 'Failed',
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
      padding: const EdgeInsets.only(right: 8),
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
          const Text('Your stories',
              style: TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w700,
                fontSize: 18,
              )),
          const SizedBox(width: 8),
          Text('قصصك',
              style: TextStyle(
                color: FacelessTheme.textSecondary.withValues(alpha: 0.7),
                fontSize: 13,
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
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('No rendered videos yet',
                      style: TextStyle(
                        color: FacelessTheme.textPrimary,
                        fontWeight: FontWeight.w700,
                        fontSize: 15,
                      )),
                  SizedBox(height: 4),
                  Text(
                    'Approve a script and your video will show up here.',
                    style: TextStyle(
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
                    run.title ?? '(بلا عنوان)',
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
                        label: const Text('Play',
                            style: TextStyle(fontWeight: FontWeight.w700)),
                      ),
                      const SizedBox(width: 12),
                      OutlinedButton.icon(
                        onPressed: onTap,
                        icon: const Icon(Icons.info_outline),
                        label: const Text('Details'),
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
                Text('${series.episodes.length} حلقات',
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
                        color: Colors.white,
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
                        child: Text('EP $episodeNumber',
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
                  run.title ?? '(بلا عنوان)',
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
class _ThemeInfo {
  final String id;
  final String titleEn;
  final String titleAr;
  final String subtitle;
  final IconData icon;
  final List<Color> gradient;
  const _ThemeInfo(this.id, this.titleEn, this.titleAr, this.subtitle,
      this.icon, this.gradient);
}

const _allThemes = <_ThemeInfo>[
  _ThemeInfo('folkloric', 'Folkloric', 'فلكلوري',
      'Ancestral tales, jinn, old wells',
      Icons.account_balance_outlined,
      [Color(0xFFB07F1F), Color(0xFFE7B53C)]),
  _ThemeInfo('urban', 'Urban', 'مدني',
      'City legends, late-night streets',
      Icons.location_city_outlined,
      [Color(0xFF3B82F6), Color(0xFF1E40AF)]),
  _ThemeInfo('wilderness', 'Wilderness', 'البرية',
      'Forests, deserts, the unknown',
      Icons.forest_outlined,
      [Color(0xFF059669), Color(0xFF064E3B)]),
  _ThemeInfo('memory', 'Memory', 'الذاكرة',
      'Psychological, half-remembered',
      Icons.psychology_outlined,
      [Color(0xFF8B5CF6), Color(0xFF5B21B6)]),
  _ThemeInfo('domestic', 'Domestic', 'منزلي',
      'Home, family, the everyday turned',
      Icons.home_outlined,
      [Color(0xFFEA580C), Color(0xFF9A3412)]),
  _ThemeInfo('travel', 'Travel', 'سفر',
      'On the road, far from home',
      Icons.travel_explore_outlined,
      [Color(0xFF0D9488), Color(0xFF134E4A)]),
  _ThemeInfo('tech', 'Tech', 'تقني',
      'Screens, signals, machines',
      Icons.memory_outlined,
      [Color(0xFF06B6D4), Color(0xFF155E75)]),
  _ThemeInfo('workplace', 'Workplace', 'العمل',
      'Offices, shops, after-hours',
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
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF1A2238), Color(0xFF0A0E1A)],
        ),
        border: Border.all(
          color: FacelessTheme.accent.withValues(alpha: 0.20),
        ),
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
          const Text(
            'AI-powered Arabic horror shorts',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: FacelessTheme.textSecondary,
              fontSize: 14,
              letterSpacing: 0.3,
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'اصنع قصصك القصيرة بالذكاء الاصطناعي',
            textAlign: TextAlign.center,
            style: TextStyle(
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
              label: const Text(
                'Start creating',
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
              ),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Free to write · Subscribe to render',
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
          english: 'Choose a theme',
          arabic: 'اختر ثيمة',
          subtitle: 'Tap to start a new story with this style',
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
                    Row(
                      children: [
                        Flexible(
                          child: Text(
                            theme.titleEn,
                            style: const TextStyle(
                              color: FacelessTheme.textPrimary,
                              fontWeight: FontWeight.w700,
                              fontSize: 14,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        const SizedBox(width: 6),
                        Text(
                          theme.titleAr,
                          style: TextStyle(
                            color: FacelessTheme.textSecondary
                                .withValues(alpha: 0.7),
                            fontSize: 11,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 2),
                    Text(
                      theme.subtitle,
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
  final String english;
  final String arabic;
  final String? subtitle;
  const _SectionTitle({
    required this.english,
    required this.arabic,
    this.subtitle,
  });
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                english,
                style: const TextStyle(
                  color: FacelessTheme.textPrimary,
                  fontWeight: FontWeight.w700,
                  fontSize: 17,
                  letterSpacing: 0.3,
                ),
              ),
              const SizedBox(width: 8),
              Text(
                arabic,
                style: TextStyle(
                  color: FacelessTheme.textSecondary.withValues(alpha: 0.7),
                  fontSize: 13,
                ),
              ),
            ],
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
        const _SectionTitle(english: 'How it works', arabic: 'كيف تعمل'),
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
          child: const Column(
            children: [
              _Step(
                number: '1',
                title: 'Write a premise',
                subtitle: 'One sentence is enough',
              ),
              _StepDivider(),
              _Step(
                number: '2',
                title: 'AI writes your script',
                subtitle: 'Arabic, in seconds — free for everyone',
              ),
              _StepDivider(),
              _Step(
                number: '3',
                title: 'Subscribe to render the video',
                subtitle: 'Each clip uses 1 credit',
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
        const _SectionTitle(english: 'Plans', arabic: 'الخطط'),
        const SizedBox(height: 12),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: _PlanChip(
                name: 'Starter',
                price: r'$9',
                credits: 12,
                badge: badgeFor('starter'),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _PlanChip(
                name: 'Creator',
                price: r'$29',
                credits: 60,
                badge: badgeFor('creator'),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _PlanChip(
                name: 'Pro',
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
            label: const Text('See full plans'),
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
                  child: const Text(
                    'Your plan',
                    style: TextStyle(
                      color: FacelessTheme.accent,
                      fontSize: 9,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.4,
                    ),
                  ),
                ),
              _PlanBadge.recommended => Text(
                  'Recommended',
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
          Text('$credits credits',
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
      padding: const EdgeInsets.only(left: 16),
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
                  const Text('Could not reach the server.',
                      style: TextStyle(
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
                          label: const Text('Retry')),
                      const SizedBox(width: 12),
                      FilledButton.icon(
                          onPressed: onSettings,
                          icon: const Icon(Icons.settings),
                          label: const Text('Settings')),
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
          'Make your first AI song',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 8),
        const Text(
          'Pick a sample to start with, or tap "New song" to write your own.',
          textAlign: TextAlign.center,
          style: TextStyle(color: FacelessTheme.textSecondary),
        ),
        const SizedBox(height: 24),
        for (final (emoji, theme, preset) in _samples)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 6),
            child: OutlinedButton(
              onPressed: () => onTrySample(theme, preset),
              style: OutlinedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 16),
                alignment: Alignment.centerLeft,
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
            label: const Text('New song from scratch'),
          ),
        ),
      ],
    );
  }
}
