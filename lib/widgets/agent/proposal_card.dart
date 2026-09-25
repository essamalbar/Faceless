/// Autonomous Artist Agent: one card in the A&R feed — a song the agent
/// proposed on its own, still `awaiting_approval`. Pure presentation: all
/// four actions (Approve/Reject/Edit/Why) are callbacks the parent screen
/// wires to the existing approve/edit flow, the reject-reason sheet, and the
/// reasoning trace sheet respectively. Mirrors the GlassCard-based section
/// cards on [SongApproveScreen] so a proposal card reads as the same design
/// language as the approve flow it feeds into.
library;

import 'package:flutter/material.dart';

import '../../api/models.dart';
import '../../l10n/l10n.dart';
import '../../theme.dart';
import '../../ui/brand.dart';
import '../../ui/primitives.dart';

class ProposalCard extends StatelessWidget {
  final AgentProposal proposal;
  /// Resolved artist display name (looked up by [proposal.artistId] by the
  /// caller) — null while the artists list is still loading.
  final String? artistName;
  final VoidCallback onApprove;
  final VoidCallback onEdit;
  final VoidCallback onReject;
  final VoidCallback onWhy;
  const ProposalCard({
    super.key,
    required this.proposal,
    required this.artistName,
    required this.onApprove,
    required this.onEdit,
    required this.onReject,
    required this.onWhy,
  });

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final name = (artistName ?? '').trim().isEmpty
        ? l10n.agentFeedArtistFallback
        : artistName!.trim();
    final monogram = name.characters.isEmpty ? '?' : name.characters.first;
    final title = proposal.title.trim().isEmpty
        ? l10n.homeUntitled
        : proposal.title.trim();
    final rationale = proposal.rationale.trim();
    // Only the rationale paragraph below is wrapped in the resulting
    // Directionality/textAlign — derive the flag from that string alone,
    // not the title too, or an Arabic title + English rationale would
    // wrongly force the English paragraph to RTL/right-align.
    final isRtl = _looksArabic(rationale);
    final score = proposal.selfScore;
    final scoreDotColor = score <= 0
        ? null
        : (score >= _scoreGoodThreshold
            ? FacelessTheme.success
            : FacelessTheme.warning);

    return GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              ArtistBadge(monogram: monogram, size: 40),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: FacelessTheme.textSecondary,
                      ),
                    ),
                    const SizedBox(height: 3),
                    EditorialHeading(title, size: 19),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              StatusPill(label: l10n.homeFilterAwaiting, kind: StatusKind.review),
            ],
          ),
          const SizedBox(height: 16),
          Eyebrow(l10n.agentFeedWhyNow),
          const SizedBox(height: 6),
          Directionality(
            textDirection: isRtl ? TextDirection.rtl : TextDirection.ltr,
            child: Text(
              rationale.isEmpty ? '—' : rationale,
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
              textAlign: isRtl ? TextAlign.right : TextAlign.left,
              style: const TextStyle(
                fontSize: 13.5,
                height: 1.45,
                color: FacelessTheme.textPrimary,
              ),
            ),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              if (score > 0)
                BrandPill(
                  '${(score * 100).round()}%',
                  icon: Icons.auto_awesome,
                  dot: true,
                  dotColor: scoreDotColor,
                )
              else
                Text(
                  l10n.agentFeedUnscored,
                  style: const TextStyle(fontSize: 12, color: FacelessTheme.faint),
                ),
              const Spacer(),
              TextButton.icon(
                onPressed: onWhy,
                icon: const Icon(Icons.psychology_outlined, size: 16),
                label: Text(l10n.agentFeedWhyButton),
                style: TextButton.styleFrom(
                  foregroundColor: FacelessTheme.accent2,
                  visualDensity: VisualDensity.compact,
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          const Hairline(),
          const SizedBox(height: 12),
          // Cost disclosure — honest about what Approve will charge, same
          // figures the approve gate itself will show (`approveCost`).
          Row(
            children: [
              const Icon(Icons.account_balance_wallet_outlined,
                  size: 16, color: FacelessTheme.accent2),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  l10n.approveCost(
                    proposal.costCredits,
                    '\$${proposal.costUsd.toStringAsFixed(2)}',
                  ),
                  style: const TextStyle(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w600,
                    color: FacelessTheme.textSecondary,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: onReject,
                  style: OutlinedButton.styleFrom(
                    foregroundColor: FacelessTheme.danger,
                    side: BorderSide(
                        color: FacelessTheme.danger.withValues(alpha: 0.4)),
                  ),
                  child: Text(l10n.agentFeedReject),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: OutlinedButton(
                  onPressed: onEdit,
                  child: Text(l10n.approveEdit),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          GradientButton(
            label: l10n.agentFeedApprove,
            icon: Icons.check,
            expand: true,
            onPressed: onApprove,
          ),
        ],
      ),
    );
  }
}

/// Score-dot color threshold — mirrors `config.yaml > agent.critique_threshold`
/// (spec §8: "queue only proposals scoring >= this"), so a card's dot only
/// reads "warning" for a proposal that would sit right at the backend's own
/// queue-admission line. Not fetched from the API (the agent config isn't
/// exposed to the client) — kept as a documented constant instead so the
/// coupling stays visible/greppable if the backend threshold ever moves.
const double _scoreGoodThreshold = 0.6;

/// True when [s] contains at least one Arabic-script codepoint — mirrors the
/// same heuristic `home_screen.dart`'s `_PosterTile._isArabic` uses to pick
/// text direction for backend-authored strings inside an otherwise-LTR
/// English UI (and vice-versa).
bool _looksArabic(String s) {
  for (final r in s.runes) {
    if (r >= 0x0600 && r <= 0x06FF) return true;
  }
  return false;
}
