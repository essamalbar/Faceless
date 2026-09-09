/// Morning drafts: free overnight drafts awaiting the user's approval.
/// Derived from the already-fetched song list (no separate endpoint) — the
/// filtering below is pure presentation, not new fetching/state.
library;

import 'package:flutter/material.dart';

import '../../api/models.dart';
import '../../l10n/l10n.dart';
import '../../theme.dart';

class MorningDraftsSection extends StatelessWidget {
  final List<SongSummary> songs;
  final void Function(SongSummary) onOpen;
  const MorningDraftsSection({
    super.key,
    required this.songs,
    required this.onOpen,
  });

  @override
  Widget build(BuildContext context) {
    final drafts = songs
        .where((s) =>
            s.source == 'morning_draft' && s.status == 'awaiting_approval')
        .toList();
    if (drafts.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 8),
          child: Text('🌅 ${context.l10n.draftSectionTitle}',
              style: const TextStyle(
                  fontWeight: FontWeight.w700,
                  fontSize: 15,
                  color: FacelessTheme.textPrimary)),
        ),
        for (final d in drafts)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 10),
            child: InkWell(
              borderRadius: BorderRadius.circular(16),
              onTap: () => onOpen(d),
              child: Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: FacelessTheme.accent.withValues(alpha: 0.035),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: FacelessTheme.borderAccent),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(d.title ?? d.theme ?? '',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                  fontWeight: FontWeight.w700,
                                  fontSize: 15,
                                  color: FacelessTheme.textPrimary)),
                          if ((d.trendRationale ?? '').isNotEmpty)
                            Padding(
                              padding: const EdgeInsets.only(top: 3),
                              child: Text(d.trendRationale!,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(
                                      fontSize: 12.5,
                                      color: FacelessTheme.textSecondary)),
                            ),
                          if (d.artistName != null)
                            Padding(
                              padding: const EdgeInsets.only(top: 3),
                              child: Text(d.artistName!,
                                  style: const TextStyle(
                                      fontSize: 12,
                                      color: FacelessTheme.accent,
                                      fontWeight: FontWeight.w600)),
                            ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 10),
                    FilledButton(
                      style: FilledButton.styleFrom(
                        visualDensity: VisualDensity.compact,
                        padding: const EdgeInsets.symmetric(
                            horizontal: 14, vertical: 8),
                      ),
                      onPressed: () => onOpen(d),
                      child: Text(context.l10n.draftReviewButton,
                          style: const TextStyle(fontSize: 13)),
                    ),
                  ],
                ),
              ),
            ),
          ),
      ],
    );
  }
}
