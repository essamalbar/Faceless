/// Autonomous Artist Agent: the A&R feed (spec §9) — the surface where the
/// agent's reasoned song proposals land, one-tap Approve/Reject/Edit plus a
/// reasoning-trace view. A proposal IS a normal `awaiting_approval` song run
/// (spec §6), so Approve and Edit both reuse the existing
/// [SongApproveScreen] unchanged — exactly the navigation
/// `HomeScreen._openSong` already uses for any awaiting_approval song. Only
/// Reject is new here (`FacelessApiClient.rejectSong`).
library;

import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../l10n/l10n.dart';
import '../theme.dart';
import '../ui/brand.dart';
import '../ui/primitives.dart';
import '../widgets/agent/proposal_card.dart';
import '../widgets/agent/reasoning_trace_sheet.dart';
import 'song_approve_screen.dart';

class AgentFeedScreen extends StatefulWidget {
  final FacelessApiClient client;
  const AgentFeedScreen({super.key, required this.client});

  @override
  State<AgentFeedScreen> createState() => _AgentFeedScreenState();
}

class _AgentFeedScreenState extends State<AgentFeedScreen> {
  Future<List<AgentProposal>>? _proposalsFuture;
  Future<List<Artist>>? _artistsFuture;

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() {
    setState(() {
      _proposalsFuture = widget.client.listAgentProposals();
      _artistsFuture = widget.client.listArtists();
    });
  }

  Future<void> _refresh() async {
    _load();
    await _proposalsFuture;
  }

  /// Approve and Edit both land here — [SongApproveScreen] IS the existing
  /// edit surface for an `awaiting_approval` song (inline lyrics/style edit
  /// + the cost-disclosure Approve button live in the same screen; there is
  /// no separate song edit screen to route to). Mirrors
  /// `HomeScreen._openSong`'s branch for `status == 'awaiting_approval'`.
  void _openApproveOrEdit(String runId) {
    Navigator.of(context)
        .push(MaterialPageRoute(
          builder: (_) =>
              SongApproveScreen(client: widget.client, runId: runId),
        ))
        .then((_) => _refresh());
  }

  void _openWhy(AgentProposal p) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => ReasoningTraceSheet(
        client: widget.client,
        runId: p.runId,
        title: p.title.trim().isEmpty ? context.l10n.homeUntitled : p.title,
      ),
    );
  }

  Future<void> _openReject(AgentProposal p) async {
    final reason = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _RejectSheet(
        title: p.title.trim().isEmpty ? context.l10n.homeUntitled : p.title,
      ),
    );
    if (reason == null || !mounted) return; // sheet dismissed / canceled
    final messenger = ScaffoldMessenger.of(context);
    try {
      await widget.client.rejectSong(p.runId, reason: reason);
      if (!mounted) return;
      messenger.showSnackBar(
        SnackBar(content: Text(context.l10n.agentFeedRejectedSnackbar)),
      );
      _refresh();
    } catch (e) {
      if (!mounted) return;
      messenger.showSnackBar(
        SnackBar(content: Text(context.l10n.agentFeedRejectError('$e'))),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Scaffold(
      backgroundColor: Colors.transparent,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
        title: Text(l10n.agentFeedScreenTitle),
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<List<AgentProposal>>(
          future: _proposalsFuture,
          builder: (context, snap) {
            if (snap.connectionState == ConnectionState.waiting) {
              return const Center(
                child: CircularProgressIndicator(color: FacelessTheme.accent),
              );
            }
            if (snap.hasError) {
              return ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                children: [
                  Padding(
                    padding: const EdgeInsets.fromLTRB(32, 80, 32, 32),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          l10n.agentFeedLoadError('${snap.error}'),
                          textAlign: TextAlign.center,
                          style: const TextStyle(color: FacelessTheme.danger),
                        ),
                        const SizedBox(height: 14),
                        OutlinedButton(
                          onPressed: _load,
                          child: Text(l10n.commonRetry),
                        ),
                      ],
                    ),
                  ),
                ],
              );
            }
            final proposals = snap.data ?? const <AgentProposal>[];
            if (proposals.isEmpty) {
              return ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                children: const [_EmptyState()],
              );
            }
            return FutureBuilder<List<Artist>>(
              future: _artistsFuture,
              builder: (context, artistSnap) {
                final names = <String, String>{
                  for (final a in artistSnap.data ?? const <Artist>[])
                    a.id: a.name,
                };
                return ListView.separated(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
                  itemCount: proposals.length,
                  separatorBuilder: (_, _) => const SizedBox(height: 14),
                  itemBuilder: (context, i) {
                    final p = proposals[i];
                    return ProposalCard(
                      proposal: p,
                      artistName: names[p.artistId],
                      onApprove: () => _openApproveOrEdit(p.runId),
                      onEdit: () => _openApproveOrEdit(p.runId),
                      onReject: () => _openReject(p),
                      onWhy: () => _openWhy(p),
                    );
                  },
                );
              },
            );
          },
        ),
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Padding(
      padding: const EdgeInsets.fromLTRB(32, 96, 32, 32),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.auto_awesome, size: 38, color: FacelessTheme.faint),
          const SizedBox(height: 16),
          Text(
            l10n.agentFeedEmptyTitle,
            textAlign: TextAlign.center,
            style: FacelessTheme.display(size: 20),
          ),
          const SizedBox(height: 10),
          Text(
            l10n.agentFeedEmptySubtitle,
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: FacelessTheme.textSecondary,
              fontSize: 13.5,
              height: 1.45,
            ),
          ),
        ],
      ),
    );
  }
}

/// Small reason sheet behind the card's Reject action. Pops with the typed
/// reason (possibly empty — reason is optional) on confirm, `null` when
/// dismissed/canceled so the caller can tell "user backed out" apart from
/// "submitted with no reason".
class _RejectSheet extends StatefulWidget {
  final String title;
  const _RejectSheet({required this.title});

  @override
  State<_RejectSheet> createState() => _RejectSheetState();
}

class _RejectSheetState extends State<_RejectSheet> {
  final _ctrl = TextEditingController();

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.viewInsetsOf(context).bottom,
          left: 16,
          right: 16,
          top: 16,
        ),
        child: GlassCard(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(child: Eyebrow(widget.title)),
                  IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.of(context).pop(),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text(l10n.agentFeedRejectSheetTitle,
                  style: FacelessTheme.display(size: 18)),
              const SizedBox(height: 14),
              TextField(
                controller: _ctrl,
                maxLines: 3,
                style: const TextStyle(fontSize: 14),
                decoration: InputDecoration(
                  hintText: l10n.agentFeedRejectReasonHint,
                  hintStyle: const TextStyle(
                      fontSize: 12.5, color: FacelessTheme.textSecondary),
                  border: const OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => Navigator.of(context).pop(),
                      child: Text(l10n.commonCancel),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: FilledButton(
                      style: FilledButton.styleFrom(
                        backgroundColor: FacelessTheme.danger,
                        // Obsidian & Champagne forbids pure white text —
                        // warm off-white even on the danger fill.
                        foregroundColor: FacelessTheme.textPrimary,
                      ),
                      onPressed: () =>
                          Navigator.of(context).pop(_ctrl.text.trim()),
                      child: Text(l10n.agentFeedRejectConfirm),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
