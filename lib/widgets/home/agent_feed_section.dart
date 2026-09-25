/// Autonomous Artist Agent: home entry point into the A&R feed — a compact
/// teaser section (eyebrow + subtitle + "See all") that opens
/// `AgentFeedScreen`. Mirrors `MorningDraftsSection`/`TrendingSection`'s
/// pattern: the future/callback come from `_HomeScreenState`; this widget
/// only renders from them.
///
/// Unlike those two sections, this one stays VISIBLE even with zero
/// proposals — it is the only entry point into `AgentFeedScreen`, and the
/// screen's own "Your A&R is composing…" empty state (spec §9) needs a way
/// in. Only a genuine fetch error hides it (e.g. an older backend without
/// `/agent/proposals` yet); a legitimately empty list still shows the
/// teaser with a "composing" subtitle instead of disappearing.
library;

import 'package:flutter/material.dart';

import '../../api/models.dart';
import '../../l10n/l10n.dart';
import '../../theme.dart';
import '../../ui/brand.dart';
import '../../ui/primitives.dart';

class AgentFeedSection extends StatelessWidget {
  final Future<List<AgentProposal>>? proposalsFuture;
  final VoidCallback onOpen;
  const AgentFeedSection({
    super.key,
    required this.proposalsFuture,
    required this.onOpen,
  });

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<AgentProposal>>(
      future: proposalsFuture,
      builder: (context, snap) {
        if (snap.hasError) return const SizedBox.shrink();
        final l10n = context.l10n;
        final proposals = snap.data ?? const <AgentProposal>[];
        final loading = snap.connectionState == ConnectionState.waiting;
        // While loading, show the neutral teaser copy (outcome unknown yet);
        // once loaded, switch to the "composing" line only if it really is
        // empty so the subtitle never promises content that isn't there.
        final subtitle = (!loading && proposals.isEmpty)
            ? l10n.agentFeedEmptySubtitle
            : l10n.agentFeedSectionSubtitle;
        return Padding(
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 4),
          child: GlassCard(
            accentEdge: true,
            onTap: onOpen,
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Eyebrow(l10n.agentFeedSectionTitle),
                          if (proposals.isNotEmpty) ...[
                            const SizedBox(width: 8),
                            BrandPill('${proposals.length}'),
                          ],
                        ],
                      ),
                      const SizedBox(height: 6),
                      Text(
                        subtitle,
                        style: const TextStyle(
                          color: FacelessTheme.textSecondary,
                          fontSize: 12.5,
                          height: 1.4,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 12),
                TextButton(
                  onPressed: onOpen,
                  child: Text(l10n.agentFeedSeeAll),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
