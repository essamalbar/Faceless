/// Trend Engine: "Trending now" — timely, ready-to-approve song briefs.
/// Fire-and-forget: any fetch error hides the section entirely. The future/
/// refreshing flag/callbacks all come from `_HomeScreenState`.
library;

import 'package:flutter/material.dart';

import '../../api/models.dart';
import '../../l10n/l10n.dart';
import '../../theme.dart';

class TrendingSection extends StatelessWidget {
  final Future<List<TrendBrief>>? trendsFuture;
  final bool refreshing;
  final VoidCallback onRefresh;
  final void Function(TrendBrief) onCreate;
  const TrendingSection({
    super.key,
    required this.trendsFuture,
    required this.refreshing,
    required this.onRefresh,
    required this.onCreate,
  });

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<TrendBrief>>(
      future: trendsFuture,
      builder: (context, snap) {
        if (snap.hasError) return const SizedBox.shrink();
        final briefs = snap.data ?? const <TrendBrief>[];
        final loading =
            snap.connectionState == ConnectionState.waiting || refreshing;
        if (briefs.isEmpty && !loading) {
          return const SizedBox.shrink();
        }
        if (briefs.isEmpty) {
          // First generation takes ~15-20s (charts + LLM). Show a compact
          // placeholder so the feature is discoverable instead of invisible.
          return Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 8),
            child: Row(
              children: [
                Text('✨ ${context.l10n.trendSectionTitle}',
                    style: const TextStyle(
                        fontWeight: FontWeight.w700,
                        fontSize: 15,
                        color: FacelessTheme.textPrimary)),
                const SizedBox(width: 12),
                const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: FacelessTheme.accent)),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(context.l10n.trendGenerating,
                      style: const TextStyle(
                          fontSize: 12.5,
                          color: FacelessTheme.textSecondary)),
                ),
              ],
            ),
          );
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
                          fontWeight: FontWeight.w700,
                          fontSize: 15,
                          color: FacelessTheme.textPrimary)),
                  const Spacer(),
                  refreshing
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(
                              strokeWidth: 2, color: FacelessTheme.accent))
                      : IconButton(
                          icon: const Icon(Icons.refresh, size: 18),
                          color: FacelessTheme.textSecondary,
                          visualDensity: VisualDensity.compact,
                          tooltip: context.l10n.trendRefreshTooltip,
                          onPressed: onRefresh,
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
                separatorBuilder: (_, _) => const SizedBox(width: 12),
                itemBuilder: (_, i) {
                  final b = briefs[i];
                  return Container(
                    width: 250,
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: FacelessTheme.glass,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: FacelessTheme.border),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(b.titleIdea.isEmpty ? b.theme : b.titleIdea,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                                fontWeight: FontWeight.w700,
                                fontSize: 15,
                                color: FacelessTheme.textPrimary)),
                        const SizedBox(height: 5),
                        Expanded(
                          child: Text(
                              b.rationale.isEmpty ? b.theme : b.rationale,
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
                            onPressed: () => onCreate(b),
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
}
