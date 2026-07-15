import 'dart:async';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:video_player/video_player.dart';

import '../web_share_stub.dart' if (dart.library.js_interop) '../web_share_web.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../l10n/l10n.dart';
import '../theme.dart';

class SongDetailScreen extends StatefulWidget {
  final FacelessApiClient client;
  final String runId;
  const SongDetailScreen(
      {super.key, required this.client, required this.runId});

  @override
  State<SongDetailScreen> createState() => _SongDetailScreenState();
}

class _SongDetailScreenState extends State<SongDetailScreen> {
  SongSummary? _summary;
  bool _polling = true;
  bool _swapping = false;
  StreamSubscription<Map<String, dynamic>>? _eventsSub;

  // Inline video player state
  VideoPlayerController? _videoController;
  bool _videoLoading = false;
  String? _videoError;
  bool _showControls = true;

  static const _terminalStatuses = {'complete', 'failed', 'canceled'};

  /// Localized progress label per backend status. Richer than the generic
  /// [statusLabel] wording where the extra context (timings) helps; falls
  /// back to [statusLabel] for anything else.
  static String _stageLabel(AppLocalizations l10n, String status) =>
      switch (status) {
        'awaiting_approval' => l10n.songDetailStatusWaitingApproval,
        'generating_song' => l10n.songDetailStatusGeneratingSong,
        'generating_cover' => l10n.songDetailStatusGeneratingCover,
        'assembling' => l10n.songDetailStatusAssembling,
        'complete' => l10n.songDetailStatusDone,
        'canceled' => l10n.statusCancelled,
        _ => statusLabel(l10n, status),
      };

  @override
  void initState() {
    super.initState();
    _poll();
  }

  // ─── polling ────────────────────────────────────────────────────────────────

  Future<void> _poll() async {
    // First load: snapshot via REST so the UI has data immediately.
    try {
      final s = await widget.client.getSong(widget.runId);
      if (!mounted) return;
      setState(() => _summary = s);
      if (_terminalStatuses.contains(s.status)) {
        setState(() => _polling = false);
        return;
      }
    } catch (_) {
      // Tolerate transient errors; SSE will re-establish.
    }
    _subscribeToEvents();
  }

  /// Subscribe to the SSE event stream for live status updates.
  /// Falls back to a 3-second poll loop if SSE fails for any reason
  /// (some old browsers, hostile proxies, etc).
  void _subscribeToEvents() {
    _eventsSub?.cancel();
    _eventsSub = widget.client.songEvents(widget.runId).listen(
      (event) async {
        if (!mounted) return;
        final summary = _summary;
        if (summary == null) {
          // No baseline yet — fetch a full snapshot
          final s = await widget.client.getSong(widget.runId).catchError(
            (_) => SongSummary(
              id: widget.runId,
              status: event['status'] as String? ?? 'unknown',
              title: null, theme: null, createdAt: '',
              hasVideo: false, chosenTake: null, lastError: null,
            ),
          );
          if (!mounted) return;
          setState(() => _summary = s);
          return;
        }
        // Merge event fields into the current summary
        final merged = SongSummary(
          id: summary.id,
          status: (event['status'] as String?) ?? summary.status,
          title: summary.title,
          theme: summary.theme,
          createdAt: summary.createdAt,
          hasVideo: summary.hasVideo
              || (event['status'] == 'complete'),
          chosenTake: (event['chosen_take'] as int?) ?? summary.chosenTake,
          lastError: event['last_error'] as String? ?? summary.lastError,
          failureStage:
              event['failure_stage'] as String? ?? summary.failureStage,
        );
        setState(() => _summary = merged);
        if (_terminalStatuses.contains(merged.status)) {
          setState(() => _polling = false);
        }
      },
      onError: (_) {
        // SSE dropped — fall back to slow REST polling.
        _fallbackPollLoop();
      },
      onDone: () {
        // Stream closed (server saw terminal). Re-snapshot once to
        // pull fields the SSE didn't carry (e.g. hasVideo path-existence).
        if (!mounted) return;
        widget.client.getSong(widget.runId).then((s) {
          if (mounted) setState(() => _summary = s);
        }).catchError((_) {});
      },
    );
  }

  Future<void> _fallbackPollLoop() async {
    while (mounted && _polling) {
      try {
        final s = await widget.client.getSong(widget.runId);
        if (!mounted) return;
        setState(() => _summary = s);
        if (_terminalStatuses.contains(s.status)) {
          setState(() => _polling = false);
          return;
        }
      } catch (_) {/* tolerate */}
      await Future.delayed(const Duration(seconds: 3));
    }
  }

  // ─── take swap ──────────────────────────────────────────────────────────────

  Future<void> _swap(int take) async {
    setState(() => _swapping = true);
    final messenger = ScaffoldMessenger.of(context);
    try {
      // Swap-take is now async — the API spawns a worker and returns
      // immediately. Status flips to "assembling" until the worker
      // finishes (1-2 min on Cloud Run with veryfast preset). We
      // re-poll so the user sees the live progress, then refresh
      // the video player once we observe a state change away from
      // "assembling".
      await widget.client.swapTake(widget.runId, take);
      // Immediate state read so the take-swap card disables both
      // buttons while assembling.
      final s = await widget.client.getSong(widget.runId);
      if (!mounted) return;
      setState(() => _summary = s);
      if (s.status == 'assembling') {
        messenger.showSnackBar(SnackBar(
          content: Text(context.l10n.songDetailSwitchingTake(take)),
          duration: const Duration(seconds: 4),
        ));
        // Resume polling so the UI auto-updates when assemble completes.
        _poll();
      } else {
        // No-op case (same take already chosen) — refresh video so
        // the cache-busted URL pulls the current bytes.
        await _initVideo();
      }
    } on FacelessApiException catch (e) {
      if (!mounted) return;
      messenger.showSnackBar(
        SnackBar(content: Text(context.l10n.songDetailSwapFailed(e.message))),
      );
    } catch (e) {
      if (!mounted) return;
      messenger.showSnackBar(
        SnackBar(content: Text(context.l10n.songDetailSwapFailed('$e'))),
      );
    } finally {
      if (mounted) setState(() => _swapping = false);
    }
  }

  // ─── retry ──────────────────────────────────────────────────────────────────

  Future<void> _retry() async {
    final last = _summary?.lastError ?? '';
    final lower = last.toLowerCase();
    final mentionsSuno =
        lower.contains('suno') || lower.contains('song');
    if (mentionsSuno) {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text(ctx.l10n.songDetailRetryTitle),
          content: Text(ctx.l10n.songDetailRetryBody),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: Text(ctx.l10n.commonCancel),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: Text(ctx.l10n.commonRetry),
            ),
          ],
        ),
      );
      if (confirmed != true) return;
    }
    try {
      await widget.client.resumeSong(widget.runId);
      if (!mounted) return;
      setState(() => _polling = true);
      _poll();
    } on FacelessApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(context.l10n.songDetailRetryFailed(e.message))),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(context.l10n.songDetailRetryFailed('$e'))),
      );
    }
  }

  // ─── inline video player ────────────────────────────────────────────────────

  Future<void> _downloadVideo() async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      final uri = await widget.client.songDownloadUrl(widget.runId);
      // On web, _blank pops a new tab; with Content-Disposition: attachment
      // the browser saves directly. On mobile, this routes through the OS
      // download handler.
      await launchUrl(uri, webOnlyWindowName: '_blank');
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(
          SnackBar(content: Text(context.l10n.songDetailDownloadFailed('$e'))),
        );
      }
    }
  }

  Future<void> _showDeleteDialog(SongSummary s) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(ctx.l10n.songDetailDeleteTitle),
        content: Text(
          ctx.l10n.songDetailDeleteBody(
              s.title ?? s.theme ?? ctx.l10n.songDetailThisRun),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false),
              child: Text(ctx.l10n.commonCancel)),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(ctx).colorScheme.error,
            ),
            onPressed: () => Navigator.pop(ctx, true),
            child: Text(ctx.l10n.commonDelete),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    final nav = Navigator.of(context);
    try {
      await widget.client.deleteSong(widget.runId);
      if (mounted) {
        messenger.showSnackBar(
            SnackBar(content: Text(context.l10n.songDetailSongDeleted)));
        // Pop back to the songs list so the deleted run isn't still
        // showing on screen.
        nav.pop();
      }
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(
            SnackBar(content: Text(context.l10n.songDetailDeleteFailed('$e'))));
      }
    }
  }

  Future<void> _showSavePersonaDialog(SongSummary s) async {
    // Default the description to the song's actual style_prompt
    // (BPM, instrumentation, vocal traits) — it's the most accurate
    // description of the persona we're saving. Falls back to a
    // generic Arabic-male string if the script fetch fails.
    String defaultDesc = 'Arabic male vocal, warm baritone, gentle '
        'vibrato, intimate close-mic, modern 2020s production';
    try {
      final script = await widget.client.getSongScript(widget.runId);
      if (script.stylePrompt.isNotEmpty) {
        defaultDesc = script.stylePrompt;
      }
    } catch (_) {
      // Use the fallback; not fatal.
    }
    if (!mounted) return;
    final nameCtrl = TextEditingController(text: s.title ?? '');
    final descCtrl = TextEditingController(text: defaultDesc);
    final saved = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(ctx.l10n.songDetailSaveVoiceTitle),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              ctx.l10n.songDetailSaveVoiceBody,
              style: const TextStyle(fontSize: 13),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: nameCtrl,
              decoration: InputDecoration(
                labelText: ctx.l10n.songDetailVoiceNameLabel,
                border: const OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: descCtrl,
              maxLines: 3,
              decoration: InputDecoration(
                labelText: ctx.l10n.songDetailDescriptionLabel,
                helperText: ctx.l10n.songDetailDescriptionHelper,
                border: const OutlineInputBorder(),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false),
              child: Text(ctx.l10n.commonCancel)),
          FilledButton(onPressed: () => Navigator.pop(ctx, true),
              child: Text(ctx.l10n.commonSave)),
        ],
      ),
    );
    if (saved != true || !mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    try {
      final persona = await widget.client.createPersonaFromSong(
        widget.runId,
        name: nameCtrl.text.trim(),
        description: descCtrl.text.trim(),
      );
      if (mounted) {
        messenger.showSnackBar(SnackBar(
          content: Text(context.l10n.songDetailVoiceSaved(persona.name)),
          duration: const Duration(seconds: 5),
        ));
      }
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(
            SnackBar(content: Text(context.l10n.songDetailSaveFailed('$e'))));
      }
    }
  }

  Future<void> _downloadAudio() async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      final uri = await widget.client.songAudioDownloadUrl(widget.runId);
      await launchUrl(uri, webOnlyWindowName: '_blank');
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(
            SnackBar(content: Text(context.l10n.songDetailDownloadFailed('$e'))));
      }
    }
  }

  Future<void> _shareSong() async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      final info = await widget.client.shareSong(widget.runId);
      if (!mounted) return;
      // Try the platform's native share sheet first via the Web
      // Share API. On mobile (Safari iOS, Chrome Android) this
      // pops the OS share UI (WhatsApp, Telegram, Mail, etc).
      // Falls through to the copy-link dialog if unsupported
      // (desktop Chrome on most platforms, Firefox).
      if (await _tryNativeShare(
          info.url, _summary?.title ?? context.l10n.songDetailAiSongFallback)) {
        return;
      }
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text(ctx.l10n.songDetailShareTitle),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                ctx.l10n.songDetailShareBody,
                style: const TextStyle(fontSize: 13),
              ),
              const SizedBox(height: 12),
              SelectableText(
                info.url,
                style: const TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 13,
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: Text(ctx.l10n.commonClose),
            ),
            TextButton.icon(
              icon: const Icon(Icons.open_in_new),
              label: Text(ctx.l10n.songDetailOpen),
              onPressed: () {
                Navigator.pop(ctx);
                launchUrl(Uri.parse(info.url),
                    webOnlyWindowName: '_blank');
              },
            ),
            FilledButton.icon(
              icon: const Icon(Icons.copy),
              label: Text(ctx.l10n.songDetailCopyLink),
              onPressed: () async {
                final copied = ctx.l10n.songDetailLinkCopied;
                await Clipboard.setData(ClipboardData(text: info.url));
                if (ctx.mounted) Navigator.pop(ctx);
                messenger.showSnackBar(
                  SnackBar(content: Text(copied)),
                );
              },
            ),
          ],
        ),
      );
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(
            SnackBar(content: Text(context.l10n.songDetailShareFailed('$e'))));
      }
    }
  }

  /// Try the platform's native share sheet (Web Share API on web).
  /// Returns true when the sheet was shown — caller skips its alt
  /// UI in that case.
  Future<bool> _tryNativeShare(String url, String title) async {
    if (!kIsWeb) return false;  // Mobile/desktop falls through
    return tryNativeWebShare(url: url, title: title);
  }

  Future<void> _applyWatermark(SongSummary s) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(ctx.l10n.songDetailWatermarkTitle),
        content: Text(ctx.l10n.songDetailWatermarkBody),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: Text(ctx.l10n.commonCancel),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: Text(ctx.l10n.songDetailApplyWatermark),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    messenger.showSnackBar(
      SnackBar(
        duration: const Duration(minutes: 8),
        content: Row(
          children: [
            const SizedBox(
              width: 16, height: 16,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(context.l10n.songDetailApplyingWatermark),
            ),
          ],
        ),
      ),
    );
    try {
      final duration = await widget.client.reAssembleSong(widget.runId);
      if (!mounted) return;
      messenger.hideCurrentSnackBar();
      messenger.showSnackBar(
        SnackBar(
          content: Text(
            context.l10n
                .songDetailWatermarkApplied(duration.toStringAsFixed(0)),
          ),
        ),
      );
      // Reload song summary so the button hides and any cached
      // <video> sources pick up the new mtime-fingerprinted URL.
      final fresh = await widget.client.getSong(widget.runId);
      if (mounted) setState(() => _summary = fresh);
    } catch (e) {
      if (!mounted) return;
      messenger.hideCurrentSnackBar();
      messenger.showSnackBar(
        SnackBar(content: Text(context.l10n.songDetailWatermarkFailed('$e'))),
      );
    }
  }

  Future<void> _rerollTakes() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(ctx.l10n.songDetailRerollTitle),
        content: Text(ctx.l10n.songDetailRerollBody),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false),
              child: Text(ctx.l10n.commonCancel)),
          FilledButton(onPressed: () => Navigator.pop(ctx, true),
              child: Text(ctx.l10n.songDetailReroll)),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    try {
      await widget.client.rerollSongTakes(widget.runId);
      if (mounted) {
        messenger.showSnackBar(SnackBar(
          content: Text(context.l10n.songDetailRerolling),
        ));
        setState(() {
          _summary = null;
        });
        _poll();
      }
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(
            SnackBar(content: Text(context.l10n.songDetailRerollFailed('$e'))));
      }
    }
  }

  Future<void> _regenerateCover() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(ctx.l10n.songDetailRegenCoverTitle),
        content: Text(ctx.l10n.songDetailRegenCoverBody),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false),
              child: Text(ctx.l10n.commonCancel)),
          FilledButton(onPressed: () => Navigator.pop(ctx, true),
              child: Text(ctx.l10n.songDetailRegenerate)),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    try {
      await widget.client.regenerateSongCover(widget.runId);
      if (mounted) {
        messenger.showSnackBar(SnackBar(
          content: Text(context.l10n.songDetailRegeneratingCover),
        ));
        // Re-poll to show the new "generating_cover" status
        setState(() {
          _summary = null;
        });
        _poll();
      }
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(
            SnackBar(content: Text(context.l10n.songDetailFailed('$e'))));
      }
    }
  }

  Future<void> _initVideo() async {
    setState(() {
      _videoLoading = true;
      _videoError = null;
    });
    // Dispose any previous controller before creating a new one
    final old = _videoController;
    _videoController = null;
    old?.removeListener(_onVideoTick);
    await old?.dispose();

    try {
      final url = await widget.client.songVideoUrl(widget.runId);
      final c = VideoPlayerController.networkUrl(url);
      await c.initialize();
      c.setLooping(false);
      c.addListener(_onVideoTick);
      if (!mounted) {
        await c.dispose();
        return;
      }
      setState(() {
        _videoController = c;
        _videoLoading = false;
      });
      c.play();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _videoLoading = false;
        _videoError = e.toString();
      });
    }
  }

  void _onVideoTick() {
    if (!mounted) return;
    setState(() {});
  }

  String _fmt(Duration d) {
    final m = d.inMinutes.toString().padLeft(2, '0');
    final s = (d.inSeconds % 60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  // ─── cover thumbnail ────────────────────────────────────────────────────────

  bool get _showCover {
    final s = _summary;
    if (s == null) return false;
    return s.hasVideo ||
        s.status == 'generating_cover' ||
        s.status == 'assembling' ||
        s.status == 'complete';
  }

  // ─── build ──────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final s = _summary;
    if (s == null) {
      return Scaffold(
        appBar: AppBar(title: Text(l10n.songDetailTitleFallback)),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(
          s.title ?? l10n.songDetailTitleFallback,
          textDirection: TextDirection.rtl,
        ),
        actions: [
          // Delete song — only when not actively rendering. The
          // backend also rejects deletes during active workers
          // (409); this just hides the button to keep the UI clean.
          if (s.status != 'generating_song'
              && s.status != 'generating_cover'
              && s.status != 'assembling')
            IconButton(
              tooltip: l10n.songDetailDeleteTooltip,
              icon: const Icon(Icons.delete_outline),
              onPressed: () => _showDeleteDialog(s),
            ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _buildCoverOrPlaceholder(context, s),
          const SizedBox(height: 16),
          _buildStatusCard(context, s),
          if (s.status == 'complete') ...[
            const SizedBox(height: 16),
            _buildVideoSection(context),
            const SizedBox(height: 12),
            // Download button is always visible once status=complete,
            // regardless of whether the inline player has been started.
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.download),
                    label: Text(l10n.songDetailDownloadMp4),
                    onPressed: _downloadVideo,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.music_note),
                    label: Text(l10n.songDetailDownloadMp3),
                    onPressed: _downloadAudio,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            // Save this song's voice as a Persona for reuse in
            // future songs. Closest thing Suno offers to voice
            // cloning across generations.
            OutlinedButton.icon(
              icon: const Icon(Icons.record_voice_over),
              label: Text(l10n.songDetailSaveVoiceTitle),
              onPressed: () => _showSavePersonaDialog(s),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.share),
                    label: Text(l10n.songDetailShare),
                    onPressed: _shareSong,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.refresh),
                    label: Text(l10n.songDetailRegenCoverButton),
                    onPressed: _regenerateCover,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            // Re-roll both Suno takes (paid). Use when both takes
            // missed the mark — lyrics + cover are preserved.
            OutlinedButton.icon(
              icon: const Icon(Icons.shuffle),
              label: Text(l10n.songDetailRerollTakesButton),
              onPressed: _rerollTakes,
            ),
            const SizedBox(height: 8),
            // Watermark backfill — only for songs assembled before the
            // brand-mark feature shipped. Hidden once watermarked=true
            // so the button doesn't surface forever on already-marked
            // songs. Long-running (3-6 min) so the handler shows an
            // explicit busy banner instead of an instant snackbar.
            if (!s.watermarked)
              OutlinedButton.icon(
                icon: const Icon(Icons.verified_outlined),
                label: Text(l10n.songDetailApplyWatermark),
                onPressed: () => _applyWatermark(s),
              ),
            const SizedBox(height: 16),
            if (s.chosenTake != null) _buildTakeSwapCard(context, s),
          ],
          if (s.status == 'failed') ...[
            const SizedBox(height: 16),
            _buildErrorCard(context, s),
            const SizedBox(height: 12),
            FilledButton.icon(
              icon: const Icon(Icons.refresh),
              label: Text(l10n.commonRetry),
              onPressed: _retry,
            ),
          ],
        ],
      ),
    );
  }

  // ─── cover ──────────────────────────────────────────────────────────────────

  Widget _buildCoverOrPlaceholder(BuildContext context, SongSummary s) {
    if (_showCover) {
      return FutureBuilder<Uri>(
        future: widget.client.songCoverUrl(widget.runId),
        builder: (ctx, snap) {
          if (!snap.hasData) {
            return _placeholderCover(context);
          }
          return ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: Image.network(
              snap.data!.toString(),
              fit: BoxFit.cover,
              height: 320,
              width: double.infinity,
              errorBuilder: (ctx2, err, stack) => _placeholderCover(ctx2),
            ),
          );
        },
      );
    }
    return _placeholderCover(context);
  }

  Widget _placeholderCover(BuildContext context) {
    return Container(
      height: 320,
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(12),
      ),
      child: const Center(child: Icon(Icons.music_note, size: 64)),
    );
  }

  // ─── status card ────────────────────────────────────────────────────────────

  Widget _buildStatusCard(BuildContext context, SongSummary s) {
    final isTerminal = _terminalStatuses.contains(s.status);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            if (!isTerminal)
              const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            else if (s.status == 'complete')
              const Icon(Icons.check_circle, color: Colors.green)
            else
              Icon(Icons.error,
                  color: Theme.of(context).colorScheme.error),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                _stageLabel(context.l10n, s.status),
                style: const TextStyle(fontWeight: FontWeight.w500),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ─── inline video ───────────────────────────────────────────────────────────

  Widget _buildVideoSection(BuildContext context) {
    final c = _videoController;

    if (c == null && !_videoLoading && _videoError == null) {
      // Not started yet — show play + download buttons
      return Row(
        children: [
          Expanded(
            child: FilledButton.icon(
              icon: const Icon(Icons.play_arrow),
              label: Text(context.l10n.songDetailPlayVideo),
              onPressed: _initVideo,
            ),
          ),
          const SizedBox(width: 12),
          OutlinedButton.icon(
            icon: const Icon(Icons.download),
            label: Text(context.l10n.songDetailDownload),
            onPressed: _downloadVideo,
          ),
        ],
      );
    }

    if (_videoLoading) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.symmetric(vertical: 24),
          child: CircularProgressIndicator(),
        ),
      );
    }

    if (_videoError != null) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(context.l10n.songDetailVideoLoadError(_videoError!),
              style: TextStyle(
                  color: Theme.of(context).colorScheme.error)),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            icon: const Icon(Icons.refresh),
            label: Text(context.l10n.commonRetry),
            onPressed: _initVideo,
          ),
        ],
      );
    }

    if (c == null) return const SizedBox.shrink();

    final pos = c.value.position;
    final dur = c.value.duration;

    return ClipRRect(
      borderRadius: BorderRadius.circular(12),
      child: GestureDetector(
        onTap: () => setState(() => _showControls = !_showControls),
        child: Stack(
          alignment: Alignment.center,
          children: [
            AspectRatio(
              aspectRatio: c.value.aspectRatio,
              child: VideoPlayer(c),
            ),
            if (_showControls) ...[
              AnimatedOpacity(
                opacity: 1.0,
                duration: const Duration(milliseconds: 200),
                child: Container(
                  color: Colors.black26,
                  child: Center(
                    child: IconButton(
                      iconSize: 72,
                      icon: Icon(
                        c.value.isPlaying
                            ? Icons.pause_circle_filled
                            : Icons.play_circle_filled,
                        color: Colors.white,
                      ),
                      onPressed: () => setState(() {
                        c.value.isPlaying ? c.pause() : c.play();
                      }),
                    ),
                  ),
                ),
              ),
              Positioned(
                left: 0,
                right: 0,
                bottom: 0,
                child: Container(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
                  decoration: const BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [Colors.transparent, Colors.black87],
                    ),
                  ),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      SliderTheme(
                        data: SliderThemeData(
                          trackHeight: 3,
                          thumbShape: const RoundSliderThumbShape(
                              enabledThumbRadius: 6),
                          overlayShape: const RoundSliderOverlayShape(
                              overlayRadius: 12),
                          activeTrackColor: FacelessTheme.accent,
                          inactiveTrackColor: Colors.white24,
                          thumbColor: FacelessTheme.accent,
                        ),
                        child: Slider(
                          min: 0,
                          max: dur.inMilliseconds
                              .clamp(1, double.infinity)
                              .toDouble(),
                          value: pos.inMilliseconds
                              .clamp(0, dur.inMilliseconds)
                              .toDouble(),
                          onChanged: (v) => c.seekTo(
                              Duration(milliseconds: v.toInt())),
                        ),
                      ),
                      Row(
                        children: [
                          Text(_fmt(pos),
                              style: const TextStyle(color: Colors.white)),
                          IconButton(
                            icon: const Icon(Icons.replay_10,
                                color: Colors.white),
                            onPressed: () => c.seekTo(
                                pos - const Duration(seconds: 10)),
                          ),
                          IconButton(
                            icon: const Icon(Icons.forward_10,
                                color: Colors.white),
                            onPressed: () => c.seekTo(
                                pos + const Duration(seconds: 10)),
                          ),
                          const Spacer(),
                          Text(_fmt(dur),
                              style: const TextStyle(color: Colors.white)),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  // ─── take swap ──────────────────────────────────────────────────────────────

  Widget _buildTakeSwapCard(BuildContext context, SongSummary s) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(context.l10n.songDetailActiveTake,
                style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed:
                        _swapping || s.chosenTake == 1 ? null : () => _swap(1),
                    child: Text(s.chosenTake == 1
                        ? context.l10n.songDetailTakeChosen(1)
                        : context.l10n.songDetailUseTake(1)),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton(
                    onPressed:
                        _swapping || s.chosenTake == 2 ? null : () => _swap(2),
                    child: Text(s.chosenTake == 2
                        ? context.l10n.songDetailTakeChosen(2)
                        : context.l10n.songDetailUseTake(2)),
                  ),
                ),
              ],
            ),
            if (_swapping)
              const Padding(
                padding: EdgeInsets.only(top: 8),
                child: LinearProgressIndicator(),
              ),
          ],
        ),
      ),
    );
  }

  // ─── error card ─────────────────────────────────────────────────────────────

  // Maps the worker's failure_stage to a human title + retry hint.
  static (String, String)? _stageInfo(AppLocalizations l10n, String? stage) =>
      switch (stage) {
        'generating_song' =>
          (l10n.songDetailFailSongTitle, l10n.songDetailFailSongHint),
        'generating_cover' =>
          (l10n.songDetailFailCoverTitle, l10n.songDetailFailCoverHint),
        'assembling' =>
          (l10n.songDetailFailAssembleTitle, l10n.songDetailFailAssembleHint),
        _ => null,
      };

  Widget _buildErrorCard(BuildContext context, SongSummary s) {
    final info = _stageInfo(context.l10n, s.failureStage);
    final title = info?.$1 ?? context.l10n.songDetailErrorFallback;
    final hint = info?.$2;
    final colors = Theme.of(context).colorScheme;
    return Card(
      color: colors.errorContainer,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: TextStyle(
                fontWeight: FontWeight.bold,
                color: colors.onErrorContainer,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              s.lastError ?? context.l10n.songDetailUnknownError,
              style: TextStyle(color: colors.onErrorContainer),
            ),
            if (hint != null) ...[
              const SizedBox(height: 8),
              Text(
                hint,
                style: TextStyle(
                  fontSize: 12,
                  fontStyle: FontStyle.italic,
                  color: colors.onErrorContainer.withValues(alpha: 0.85),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  // ─── lifecycle ──────────────────────────────────────────────────────────────

  @override
  void dispose() {
    _polling = false;
    _eventsSub?.cancel();
    _videoController?.removeListener(_onVideoTick);
    _videoController?.dispose();
    super.dispose();
  }
}
