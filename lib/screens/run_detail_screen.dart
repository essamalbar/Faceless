import 'dart:async';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../api/settings.dart';
import '../theme.dart';
import 'edit_script_screen.dart';
import 'log_viewer_screen.dart';
import 'video_player_screen.dart';

class RunDetailScreen extends StatefulWidget {
  final FacelessApiClient client;
  final String runId;
  const RunDetailScreen({super.key, required this.client, required this.runId});

  @override
  State<RunDetailScreen> createState() => _RunDetailScreenState();
}

class _RunDetailScreenState extends State<RunDetailScreen> {
  RunSummary? _run;
  ScriptResponse? _script;
  String? _error;
  bool _busy = false;
  Timer? _poll;

  @override
  void initState() {
    super.initState();
    _refresh();
    // Poll every 5s. Always retry — if the very first refresh failed (e.g.
    // network blip), `_run` would otherwise stay null and the timer would
    // be locked out forever, requiring the user to manually navigate
    // away and back.
    _poll = Timer.periodic(const Duration(seconds: 5), (_) {
      if (_run == null ||
          _run!.isRunning ||
          _run!.isAwaitingApproval ||
          _run!.isAwaitingVeoApproval ||
          _run!.isFailed) {
        _refresh(silent: true);
      }
    });
  }

  Future<void> _refresh({bool silent = false}) async {
    try {
      final run = await widget.client.getRun(widget.runId);
      ScriptResponse? script = _script;
      if (script == null && !run.status.contains('creating')) {
        // Try to fetch script when available
        try {
          script = await widget.client.getScript(widget.runId);
        } on FacelessApiException catch (e) {
          if (e.status != 409) rethrow;
        }
      }
      if (!mounted) return;
      setState(() {
        _run = run;
        _script = script;
        if (!silent) _error = null;
      });
    } catch (e) {
      if (!silent) setState(() => _error = e.toString());
    }
  }

  Future<void> _approve() async {
    if (_busy) return; // double-tap guard — busy is set synchronously below
    setState(() => _busy = true);
    // Immediate user feedback — Flux character sheet takes ~30 sec before
    // backend status flips to "running_paid", and without this snackbar the
    // user thinks nothing happened and starts spam-tapping.
    final messenger = ScaffoldMessenger.of(context);
    messenger.showSnackBar(const SnackBar(
      content: Text('Approved — generating character sheet on Flux (~30 sec)…'),
      duration: Duration(seconds: 4),
    ));
    try {
      await widget.client.approveRun(widget.runId);
      await _refresh();
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(SnackBar(content: Text('Approve failed: $e')));
        setState(() => _busy = false);
      }
      return;
    }
    // Keep _busy=true so the approval bar stays in its loading state until
    // a status refresh confirms we've moved past awaiting_approval. The
    // 5-sec poll will release it.
    if (mounted) setState(() => _busy = false);
  }

  Future<void> _approveVeo() async {
    if (_busy) return;
    setState(() => _busy = true);
    final messenger = ScaffoldMessenger.of(context);
    messenger.showSnackBar(const SnackBar(
      content: Text('Approved — starting Veo generation…'),
      duration: Duration(seconds: 4),
    ));
    try {
      await widget.client.approveVeoRun(widget.runId);
      await _refresh();
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(SnackBar(content: Text('Approve failed: $e')));
        setState(() => _busy = false);
      }
      return;
    }
    if (mounted) setState(() => _busy = false);
  }

  Future<void> _rerollCharacterSheet() async {
    if (_busy) return;
    final yes = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Reroll character sheet?'),
        content: const Text(
          'This deletes the current character sheet and regenerates it on Flux. '
          'Costs another \$0.05.',
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Keep')),
          FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Reroll (\$0.05)')),
        ],
      ),
    );
    if (yes != true || !mounted) return;
    setState(() => _busy = true);
    try {
      await widget.client.rerollCharacterSheet(widget.runId);
      await _refresh();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Reroll failed: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _resume() async {
    if (_busy) return;
    setState(() => _busy = true);
    final messenger = ScaffoldMessenger.of(context);
    messenger.showSnackBar(const SnackBar(
      content: Text('Resuming pipeline…'),
      duration: Duration(seconds: 2),
    ));
    try {
      await widget.client.resumeRun(widget.runId);
      await _refresh();
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(SnackBar(content: Text('Resume failed: $e')));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  /// Cancel = throw this run away. Kills any subprocess, deletes the run dir
  /// entirely, pops back to the gallery. The user explicitly asked for this
  /// behaviour — a cancelled run should not linger as a "failed" entry.
  Future<void> _cancelAndDelete() async {
    if (_busy) return;
    final yes = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Discard this run?'),
        content: const Text(
          'Cancelling will stop any running pipeline AND delete the run '
          'entirely. The script and any partially-generated artifacts will '
          'be removed. This cannot be undone.',
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Keep')),
          FilledButton(
              style: FilledButton.styleFrom(
                  backgroundColor: FacelessTheme.danger,
                  foregroundColor: Colors.white),
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Discard')),
        ],
      ),
    );
    if (yes != true || !mounted) return;
    setState(() => _busy = true);
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    try {
      // Backend's DELETE handler atomically stops any running subprocess
      // (SIGTERM → wait → SIGKILL fallback) and then removes the dir.
      // We don't call cancelRun separately — that caused a race where the
      // process was technically still alive when delete fired.
      await widget.client.deleteRun(widget.runId);
      if (!mounted) return;
      messenger.showSnackBar(const SnackBar(
          content: Text('Run discarded'),
          duration: Duration(seconds: 2)));
      navigator.pop();  // back to gallery
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(SnackBar(content: Text('Discard failed: $e')));
        setState(() => _busy = false);
      }
    }
  }

  Future<void> _rerollClips() async {
    final n = _script?.beats.length ?? 0;
    if (n == 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No script — nothing to reroll')),
      );
      return;
    }
    final selected = await showDialog<List<int>>(
      context: context,
      builder: (_) => _RerollDialog(beatCount: n),
    );
    if (selected == null || selected.isEmpty || !mounted) return;
    setState(() => _busy = true);
    final messenger = ScaffoldMessenger.of(context);
    messenger.showSnackBar(SnackBar(
      content: Text('Rerolling ${selected.length} clip(s) — ~\$${(selected.length * 0.85).toStringAsFixed(2)}'),
      duration: const Duration(seconds: 4),
    ));
    try {
      await widget.client.rerollClips(widget.runId, selected);
      await _refresh();
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(SnackBar(content: Text('Reroll failed: $e')));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _openLog() {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) =>
            LogViewerScreen(client: widget.client, runId: widget.runId),
      ),
    );
  }

  Future<void> _editScript() async {
    if (_script == null) return;
    final saved = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => EditScriptScreen(
          client: widget.client,
          runId: widget.runId,
          initialScript: _script!,
        ),
      ),
    );
    if (saved == true) {
      // Force-refetch the script
      setState(() => _script = null);
      _refresh();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.runId, style: const TextStyle(fontSize: 14)),
        actions: [
          IconButton(
              icon: const Icon(Icons.article_outlined),
              tooltip: 'View log',
              onPressed: _openLog),
          IconButton(icon: const Icon(Icons.refresh), onPressed: _refresh),
        ],
      ),
      body: SafeArea(child: _body()),
    );
  }

  Widget _body() {
    if (_run == null && _error == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return _ErrorPanel(error: _error!, onRetry: _refresh);
    }
    final run = _run!;
    return RefreshIndicator(
      onRefresh: _refresh,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _StatusBanner(run: run),
          const SizedBox(height: 16),
          if (run.title != null)
            Text(
              run.title!,
              style: Theme.of(context).textTheme.headlineSmall,
              textDirection: TextDirection.rtl,
            ),
          if (run.premise != null) ...[
            const SizedBox(height: 8),
            Text(
              run.premise!,
              textDirection: TextDirection.rtl,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ],
          const SizedBox(height: 16),
          if (run.isComplete) ...[
            Row(
              children: [
                Expanded(
                  flex: 2,
                  child: FilledButton.icon(
                    onPressed: () => Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => VideoPlayerScreen(
                          client: widget.client,
                          runId: run.id,
                          title: run.title,
                        ),
                      ),
                    ),
                    icon: const Icon(Icons.play_arrow),
                    label: const Text('Play Video'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _busy ? null : _rerollClips,
                    icon: const Icon(Icons.refresh),
                    label: const Text('Reroll'),
                  ),
                ),
              ],
            ),
          ],
          if (run.isFailed) ...[
            Card(
              color: Theme.of(context).colorScheme.errorContainer,
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      run.lastError ?? 'Run failed.',
                      style: TextStyle(
                          color: Theme.of(context).colorScheme.onErrorContainer,
                          fontFamily: 'monospace',
                          fontSize: 11),
                    ),
                    if (run.errorHint != null) ...[
                      const SizedBox(height: 12),
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: Colors.black.withValues(alpha: 0.25),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Icon(Icons.lightbulb_outline,
                                color: FacelessTheme.accent, size: 18),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                run.errorHint!,
                                style: const TextStyle(
                                    color: Colors.white,
                                    fontWeight: FontWeight.w500,
                                    height: 1.4),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: FilledButton.icon(
                    onPressed: _busy ? null : _resume,
                    icon: const Icon(Icons.replay),
                    label: const Text('Resume'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _openLog,
                    icon: const Icon(Icons.article_outlined),
                    label: const Text('View Log'),
                  ),
                ),
              ],
            ),
          ],
          if (run.isRunning && run.progress != null) ...[
            const SizedBox(height: 12),
            _ProgressPanel(progress: run.progress!),
          ],
          if (_script != null) ...[
            const SizedBox(height: 24),
            _ScriptPanel(
              script: _script!,
              showCost: run.isAwaitingApproval,
              runId: run.id,
              clipsDoneCount: run.progress?.clipsDone ??
                  (run.isComplete ? _script!.beats.length : 0),
            ),
          ],
          if (run.isAwaitingVeoApproval) ...[
            const SizedBox(height: 16),
            _CharacterSheetPanel(
              runId: run.id,
              client: widget.client,
              onReroll: _busy ? null : _rerollCharacterSheet,
            ),
          ],
          if (run.isAwaitingApproval || run.isAwaitingVeoApproval) ...[
            const SizedBox(height: 16),
            _ApprovalBar(
              busy: _busy,
              // For the Veo gate, show only the Veo cost (Flux $0.05 already spent).
              cost: run.isAwaitingVeoApproval
                  ? ((_script?.estimatedCostUsd ?? 0) - 0.05).clamp(0.0, double.infinity)
                  : (_script?.estimatedCostUsd ?? 0),
              isVeoGate: run.isAwaitingVeoApproval,
              onApprove: run.isAwaitingVeoApproval ? _approveVeo : _approve,
              onEdit: _editScript,
              onCancel: _cancelAndDelete,
            ),
          ],
          if (run.isRunning) ...[
            const SizedBox(height: 16),
            FilledButton.tonalIcon(
              onPressed: _busy ? null : _cancelAndDelete,
              icon: const Icon(Icons.delete_forever),
              label: const Text('Cancel & Discard'),
            ),
          ],
        ],
      ),
    );
  }

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
  }
}

class _StatusBanner extends StatelessWidget {
  final RunSummary run;
  const _StatusBanner({required this.run});

  @override
  Widget build(BuildContext context) {
    final (label, icon, color) = switch (run.status) {
      RunStatus.complete =>
        ('Complete — ready to watch', Icons.check_circle, Colors.green),
      RunStatus.awaitingApproval => (
          'Awaiting your approval to spend Veo \$',
          Icons.pause_circle,
          Colors.orange,
        ),
      RunStatus.awaitingVeoApproval => (
          'Character sheet ready — review before Veo spend',
          Icons.image_outlined,
          Colors.orange,
        ),
      RunStatus.runningPaid =>
        ('Generating clips on Veo…', Icons.movie_filter, Colors.blue),
      RunStatus.creating =>
        ('Writing the script…', Icons.edit_note, Colors.blue),
      RunStatus.failed => (
          'Failed — tap Resume to retry from where it stopped',
          Icons.error,
          Colors.red,
        ),
      _ => (run.status, Icons.info, Colors.grey),
    };
    return Card(
      color: color.withValues(alpha: 0.12),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            Icon(icon, color: color),
            const SizedBox(width: 12),
            Expanded(
              child: Text(label,
                  style: TextStyle(color: color, fontWeight: FontWeight.w600)),
            ),
          ],
        ),
      ),
    );
  }
}

class _ScriptPanel extends StatelessWidget {
  final ScriptResponse script;
  final bool showCost;
  final String runId;
  final int clipsDoneCount;
  const _ScriptPanel({
    required this.script,
    required this.showCost,
    required this.runId,
    required this.clipsDoneCount,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text('Script (${script.beats.length} beats)',
                style: Theme.of(context).textTheme.titleMedium),
            if (showCost)
              Text('≈ \$${script.estimatedCostUsd.toStringAsFixed(2)}',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        color: Theme.of(context).colorScheme.primary,
                        fontWeight: FontWeight.bold,
                      )),
          ],
        ),
        const SizedBox(height: 8),
        ...script.beats.asMap().entries.map((e) => _BeatTile(
              index: e.key + 1,
              beat: e.value,
              runId: runId,
              hasClip: e.key < clipsDoneCount,
            )),
      ],
    );
  }
}

class _BeatTile extends StatelessWidget {
  final int index;
  final ScriptBeat beat;
  final String runId;
  final bool hasClip;       // does clips/NN.mp4 exist on disk?
  const _BeatTile({
    required this.index,
    required this.beat,
    required this.runId,
    required this.hasClip,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 9:16 thumbnail of this clip if it's been generated
            _ClipThumbBox(runId: runId, clipIndex: index, hasClip: hasClip),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color:
                              Theme.of(context).colorScheme.primaryContainer,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(index.toString().padLeft(2, '0'),
                            style: const TextStyle(
                                fontWeight: FontWeight.bold)),
                      ),
                      const SizedBox(width: 8),
                      Text(beat.speaker,
                          style: const TextStyle(fontWeight: FontWeight.w600)),
                      const Spacer(),
                      Text('${beat.clipDurationS.toStringAsFixed(0)}s',
                          style: Theme.of(context).textTheme.bodySmall),
                    ],
                  ),
                  const SizedBox(height: 8),
                  if (beat.isSilent)
                    Text('(silent action beat — no dialogue)',
                        style: TextStyle(
                            fontStyle: FontStyle.italic,
                            color: Theme.of(context).hintColor))
                  else
                    Text(
                      beat.arabic,
                      textDirection: TextDirection.rtl,
                      style: Theme.of(context)
                          .textTheme
                          .bodyLarge
                          ?.copyWith(height: 1.6),
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

class _ApprovalBar extends StatelessWidget {
  final bool busy;
  final double cost;
  final bool isVeoGate;     // NEW
  final VoidCallback onApprove;
  final VoidCallback onEdit;
  final VoidCallback onCancel;
  const _ApprovalBar({
    required this.busy,
    required this.cost,
    this.isVeoGate = false,   // NEW with default
    required this.onApprove,
    required this.onEdit,
    required this.onCancel,
  });

  @override
  Widget build(BuildContext context) {
    if (busy) {
      // While the approve POST is in flight, show an unmistakable loading
      // state so the user doesn't tap 5 times thinking nothing happened.
      return Card(
        color: FacelessTheme.accent.withValues(alpha: 0.18),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
          child: Row(
            children: [
              const SizedBox(
                width: 22, height: 22,
                child: CircularProgressIndicator(
                    strokeWidth: 2.5,
                    valueColor:
                        AlwaysStoppedAnimation(FacelessTheme.accent)),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Text(
                  isVeoGate
                      ? 'Starting Veo generation… (clips will appear shortly)'
                      : 'Approving — generating character sheet on Flux (~30s)…',
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
            ],
          ),
        ),
      );
    }
    return Card(
      color: FacelessTheme.surface2,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Row(
              children: [
                const Icon(Icons.warning_amber, color: FacelessTheme.warning),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    isVeoGate
                        ? 'Approve to start Veo generation (~\$${cost.toStringAsFixed(2)})'
                        : 'Approve to render character sheet on Flux (~\$0.05); Veo cost (~\$${cost.toStringAsFixed(2)}) confirmed at the next step',
                    style: const TextStyle(fontWeight: FontWeight.w600),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: onEdit,
                    icon: const Icon(Icons.edit),
                    label: const Text('Edit'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: onCancel,
                    style: OutlinedButton.styleFrom(
                      foregroundColor: FacelessTheme.danger,
                      side: BorderSide(
                          color:
                              FacelessTheme.danger.withValues(alpha: 0.5)),
                    ),
                    icon: const Icon(Icons.delete_forever),
                    label: const Text('Discard'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  flex: 2,
                  child: FilledButton.icon(
                    onPressed: onApprove,
                    icon: const Icon(Icons.check_circle),
                    label: const Text('Approve'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}


class _ProgressPanel extends StatelessWidget {
  final RunProgress progress;
  const _ProgressPanel({required this.progress});

  @override
  Widget build(BuildContext context) {
    final stageLabel = switch (progress.stage) {
      'script' => 'Writing the script…',
      'character_sheet' => 'Generating character sheet on Flux…',
      'video' =>
        'Generating clip ${progress.clipsDone + 1} of ${progress.clipsTotal} on Veo…',
      'captions' => 'Whisper-aligning captions…',
      'assemble' => 'Assembling final mp4…',
      _ => progress.stage,
    };
    final value = progress.fractional;
    return Card(
      color: FacelessTheme.surface,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const SizedBox(
                  width: 16, height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(stageLabel,
                      style:
                          const TextStyle(fontWeight: FontWeight.w600)),
                ),
              ],
            ),
            const SizedBox(height: 12),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: value,
                minHeight: 6,
                backgroundColor: Colors.white.withValues(alpha: 0.08),
                valueColor: const AlwaysStoppedAnimation(FacelessTheme.accent),
              ),
            ),
            if (progress.stage == 'video' && progress.clipsTotal > 0) ...[
              const SizedBox(height: 6),
              Text(
                '${progress.clipsDone} / ${progress.clipsTotal} clips done',
                style: const TextStyle(
                    color: FacelessTheme.textSecondary, fontSize: 12),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _ErrorPanel extends StatelessWidget {
  final String error;
  final VoidCallback onRetry;
  const _ErrorPanel({required this.error, required this.onRetry});

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.error_outline,
                  size: 64, color: Theme.of(context).colorScheme.error),
              const SizedBox(height: 16),
              Text(error, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.refresh),
                label: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
}


/// 9:16 thumbnail of a single beat's clip. Lazily fetches the URL (which
/// includes the bearer token in its query string) once and caches via
/// CachedNetworkImage. Shows a placeholder while the clip hasn't been
/// generated yet.
class _ClipThumbBox extends StatefulWidget {
  final String runId;
  final int clipIndex;
  final bool hasClip;
  const _ClipThumbBox({
    required this.runId,
    required this.clipIndex,
    required this.hasClip,
  });
  @override
  State<_ClipThumbBox> createState() => _ClipThumbBoxState();
}

class _ClipThumbBoxState extends State<_ClipThumbBox> {
  String? _url;

  @override
  void initState() {
    super.initState();
    if (widget.hasClip) _resolve();
  }

  @override
  void didUpdateWidget(covariant _ClipThumbBox old) {
    super.didUpdateWidget(old);
    if (widget.hasClip && !old.hasClip) _resolve();
  }

  Future<void> _resolve() async {
    final settings = FacelessSettings();
    final base = await settings.baseUrl();
    final token = await settings.token();
    if (base == null || token == null) return;
    final cleaned =
        base.endsWith('/') ? base.substring(0, base.length - 1) : base;
    if (mounted) {
      setState(() {
        _url =
            '$cleaned/runs/${widget.runId}/clips/${widget.clipIndex}/thumbnail?token=$token';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 56,
      height: 100,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(6),
        child: _url == null || !widget.hasClip
            ? Container(
                color: FacelessTheme.surface2,
                alignment: Alignment.center,
                child: Icon(
                  widget.hasClip ? Icons.movie : Icons.movie_creation_outlined,
                  color: FacelessTheme.textSecondary,
                  size: 18,
                ),
              )
            : CachedNetworkImage(
                imageUrl: _url!,
                fit: BoxFit.cover,
                placeholder: (_, _) => Container(color: FacelessTheme.surface2),
                errorWidget: (_, _, _) => Container(
                  color: FacelessTheme.surface2,
                  alignment: Alignment.center,
                  child: const Icon(Icons.movie,
                      color: FacelessTheme.textSecondary, size: 18),
                ),
              ),
      ),
    );
  }
}


class _CharacterSheetPanel extends StatefulWidget {
  final String runId;
  final FacelessApiClient client;
  final VoidCallback? onReroll;
  const _CharacterSheetPanel({
    required this.runId,
    required this.client,
    required this.onReroll,
  });
  @override
  State<_CharacterSheetPanel> createState() => _CharacterSheetPanelState();
}

class _CharacterSheetPanelState extends State<_CharacterSheetPanel> {
  String? _url;

  @override
  void initState() {
    super.initState();
    _resolve();
  }

  Future<void> _resolve() async {
    final uri = await widget.client.thumbnailUrl(widget.runId);
    if (mounted) setState(() => _url = uri.toString());
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      color: FacelessTheme.surface2,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('CHARACTER SHEET (FLUX)',
                style: TextStyle(
                    color: FacelessTheme.textSecondary,
                    fontWeight: FontWeight.w700,
                    fontSize: 11,
                    letterSpacing: 1.2)),
            const SizedBox(height: 8),
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: _url == null
                  ? const SizedBox(
                      height: 200,
                      child: Center(child: CircularProgressIndicator()),
                    )
                  : CachedNetworkImage(
                      imageUrl: _url!,
                      fit: BoxFit.contain,
                      errorWidget: (_, _, _) => const SizedBox(
                        height: 200,
                        child: Center(child: Icon(Icons.broken_image)),
                      ),
                      placeholder: (_, _) => const SizedBox(
                        height: 200,
                        child: Center(child: CircularProgressIndicator()),
                      ),
                    ),
            ),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: widget.onReroll,
              icon: const Icon(Icons.refresh),
              label: const Text('Reroll character sheet (\$0.05)'),
            ),
          ],
        ),
      ),
    );
  }
}

/// Multi-select dialog: which clips to regenerate. Each Veo Fast clip is
/// ~$0.85, so the dialog shows live cost as the user toggles indices.
class _RerollDialog extends StatefulWidget {
  final int beatCount;
  const _RerollDialog({required this.beatCount});
  @override
  State<_RerollDialog> createState() => _RerollDialogState();
}

class _RerollDialogState extends State<_RerollDialog> {
  final Set<int> _selected = {};

  @override
  Widget build(BuildContext context) {
    final cost = _selected.length * 0.85;
    return AlertDialog(
      title: const Text('Reroll which clips?'),
      content: SizedBox(
        width: 360,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Pick the clips that need regenerating. Each one costs ~\$0.85. '
              'The other clips stay; the final mp4 re-stitches at the end.',
              style: TextStyle(
                  color: FacelessTheme.textSecondary, fontSize: 12),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 6, runSpacing: 6,
              children: List.generate(widget.beatCount, (i) {
                final n = i + 1;
                final on = _selected.contains(n);
                return FilterChip(
                  label: Text(n.toString().padLeft(2, '0')),
                  selected: on,
                  onSelected: (v) => setState(() {
                    if (v) {
                      _selected.add(n);
                    } else {
                      _selected.remove(n);
                    }
                  }),
                  selectedColor: FacelessTheme.accent.withValues(alpha: 0.4),
                );
              }),
            ),
            const SizedBox(height: 12),
            Text(
              _selected.isEmpty
                  ? 'No clips selected'
                  : '${_selected.length} clip(s) — ~\$${cost.toStringAsFixed(2)}',
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel')),
        FilledButton.icon(
          onPressed: _selected.isEmpty
              ? null
              : () =>
                  Navigator.pop(context, _selected.toList()..sort()),
          icon: const Icon(Icons.refresh),
          label: const Text('Reroll'),
        ),
      ],
    );
  }
}
