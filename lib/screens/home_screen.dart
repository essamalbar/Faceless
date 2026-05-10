import 'dart:async';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../api/settings.dart';
import '../config.dart';
import '../theme.dart';
import 'cost_screen.dart';
import 'new_run_screen.dart';
import 'run_detail_screen.dart';
import 'settings_screen.dart';
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
      });
    }
    _fetchSpend();
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
    setState(() => _runsFuture = _client.listRuns());
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

  Future<void> _openNewRun() async {
    final created = await Navigator.of(context).push<RunSummary?>(
      MaterialPageRoute(builder: (_) => NewRunScreen(client: _client)),
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
            Container(
              width: 28,
              height: 28,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [FacelessTheme.accent, FacelessTheme.accent2],
                ),
                borderRadius: BorderRadius.circular(7),
              ),
              alignment: Alignment.center,
              child: const Text('ف',
                  style: TextStyle(
                      color: Colors.black,
                      fontWeight: FontWeight.bold,
                      fontSize: 16)),
            ),
            const SizedBox(width: 10),
            const Text('Faceless',
                style: TextStyle(fontWeight: FontWeight.w700)),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh',
            onPressed: _refresh,
          ),
          IconButton(
            icon: const Icon(Icons.settings),
            tooltip: 'Settings',
            onPressed: _openSettings,
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _openNewRun,
        backgroundColor: FacelessTheme.accent,
        foregroundColor: Colors.black,
        icon: const Icon(Icons.add),
        label: const Text('New Episode',
            style: TextStyle(fontWeight: FontWeight.w700)),
      ),
      body: RefreshIndicator(
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
            if (allRuns.isEmpty) return const _EmptyView();

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

class _EmptyView extends StatelessWidget {
  const _EmptyView();
  @override
  Widget build(BuildContext context) => SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        child: SizedBox(
          height: MediaQuery.of(context).size.height,
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(32),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.movie_outlined,
                      size: 80, color: FacelessTheme.textSecondary),
                  const SizedBox(height: 16),
                  Text('No episodes yet.',
                      style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 8),
                  const Text('Tap "New Episode" to generate your first video.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: FacelessTheme.textSecondary)),
                ],
              ),
            ),
          ),
        ),
      );
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

