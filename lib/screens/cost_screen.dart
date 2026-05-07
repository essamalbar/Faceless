import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../theme.dart';

/// Cost dashboard — shows total Kie.ai (Veo + Flux) spend across all runs,
/// plus a sortable per-run breakdown. Doesn't include ElevenLabs or LLM
/// costs (those don't write spend logs); useful for monthly cost tracking.
class CostScreen extends StatefulWidget {
  final FacelessApiClient client;
  const CostScreen({super.key, required this.client});

  @override
  State<CostScreen> createState() => _CostScreenState();
}

class _CostScreenState extends State<CostScreen> {
  Future<SpendSummary>? _future;
  bool _sortByAmount = true;

  @override
  void initState() {
    super.initState();
    _future = widget.client.getSpendSummary();
  }

  Future<void> _refresh() async {
    setState(() => _future = widget.client.getSpendSummary());
    await _future;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Spend'),
        actions: [
          IconButton(
            icon: Icon(_sortByAmount ? Icons.sort_by_alpha : Icons.attach_money),
            tooltip: _sortByAmount ? 'Sort by date' : 'Sort by amount',
            onPressed: () =>
                setState(() => _sortByAmount = !_sortByAmount),
          ),
          IconButton(icon: const Icon(Icons.refresh), onPressed: _refresh),
        ],
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _refresh,
          child: FutureBuilder<SpendSummary>(
            future: _future,
            builder: (context, snap) {
              if (snap.connectionState == ConnectionState.waiting) {
                return const Center(child: CircularProgressIndicator());
              }
              if (snap.hasError) {
                return Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Text(snap.error.toString()),
                  ),
                );
              }
              final s = snap.data!;
              final rows = [...s.byRun];
              if (_sortByAmount) {
                rows.sort((a, b) => b.usd.compareTo(a.usd));
              }
              // else: API returns reverse-chrono, keep that order

              return ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  _TotalCard(summary: s),
                  const SizedBox(height: 16),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 4),
                    child: Text(
                      _sortByAmount ? 'BY AMOUNT' : 'BY DATE (newest first)',
                      style: const TextStyle(
                        color: FacelessTheme.textSecondary,
                        fontWeight: FontWeight.w700,
                        fontSize: 11,
                        letterSpacing: 1.2,
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  ...rows.map((r) => _RunSpendTile(row: r, total: s.totalUsd)),
                  const SizedBox(height: 24),
                  const _Footnote(),
                ],
              );
            },
          ),
        ),
      ),
    );
  }
}

class _TotalCard extends StatelessWidget {
  final SpendSummary summary;
  const _TotalCard({required this.summary});

  @override
  Widget build(BuildContext context) {
    final perRun = summary.runCount == 0
        ? 0.0
        : summary.totalUsd / summary.runCount;
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [FacelessTheme.accent, FacelessTheme.accent2],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('TOTAL KIE.AI SPEND',
              style: TextStyle(
                  color: Colors.black87,
                  fontWeight: FontWeight.w700,
                  fontSize: 11,
                  letterSpacing: 1.5)),
          const SizedBox(height: 6),
          Text('\$${summary.totalUsd.toStringAsFixed(2)}',
              style: const TextStyle(
                  color: Colors.black,
                  fontWeight: FontWeight.w900,
                  fontSize: 38,
                  height: 1.0)),
          const SizedBox(height: 12),
          Row(
            children: [
              _Metric(label: 'RUNS', value: '${summary.runCount}'),
              const SizedBox(width: 24),
              _Metric(
                  label: 'AVG / RUN',
                  value: '\$${perRun.toStringAsFixed(2)}'),
            ],
          ),
        ],
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  final String label;
  final String value;
  const _Metric({required this.label, required this.value});
  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label,
              style: const TextStyle(
                  color: Colors.black54,
                  fontWeight: FontWeight.w700,
                  fontSize: 10,
                  letterSpacing: 1.2)),
          Text(value,
              style: const TextStyle(
                  color: Colors.black,
                  fontWeight: FontWeight.w800,
                  fontSize: 18)),
        ],
      );
}

class _RunSpendTile extends StatelessWidget {
  final SpendRow row;
  final double total;
  const _RunSpendTile({required this.row, required this.total});

  bool _isArabic(String s) {
    for (final r in s.runes) {
      if (r >= 0x0600 && r <= 0x06FF) return true;
    }
    return false;
  }

  @override
  Widget build(BuildContext context) {
    final pct = total > 0 ? (row.usd / total) : 0.0;
    final title = row.title?.trim() ?? row.runId;
    final isArabic = _isArabic(title);
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    title,
                    textDirection:
                        isArabic ? TextDirection.rtl : TextDirection.ltr,
                    style: const TextStyle(
                        fontWeight: FontWeight.w600, fontSize: 14),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                const SizedBox(width: 12),
                Text(
                  '\$${row.usd.toStringAsFixed(2)}',
                  style: const TextStyle(
                      fontWeight: FontWeight.w800,
                      fontSize: 16,
                      color: FacelessTheme.accent,
                      fontFeatures: [FontFeature.tabularFigures()]),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(row.runId,
                style: const TextStyle(
                    color: FacelessTheme.textSecondary, fontSize: 11)),
            const SizedBox(height: 8),
            ClipRRect(
              borderRadius: BorderRadius.circular(2),
              child: LinearProgressIndicator(
                value: pct,
                minHeight: 4,
                backgroundColor: Colors.white.withValues(alpha: 0.05),
                valueColor: const AlwaysStoppedAnimation(FacelessTheme.accent),
              ),
            ),
            const SizedBox(height: 4),
            Text('${(pct * 100).toStringAsFixed(1)} % of total',
                style: const TextStyle(
                    color: FacelessTheme.textSecondary, fontSize: 10)),
          ],
        ),
      ),
    );
  }
}

class _Footnote extends StatelessWidget {
  const _Footnote();
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: FacelessTheme.surface,
          borderRadius: BorderRadius.circular(8),
        ),
        child: const Text(
          'Counts Veo (\$0.10/sec) + Flux character sheet (\$0.05/run). '
          'Doesn\'t include ElevenLabs (~\$0.30/episode if used) or '
          'Anthropic / Groq script generation (<\$0.05/episode).',
          style: TextStyle(color: FacelessTheme.textSecondary, fontSize: 11),
        ),
      );
}
