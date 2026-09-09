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
import '../ui/brand.dart';
import '../ui/primitives.dart';
import '../widgets/composing_view.dart';
import '../widgets/perform_sheet.dart';

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

  // "Make me sing this" — separate inline player for perform.mp4 (a fixed
  // 30s clip, so a lighter tap-to-toggle control surface than the main
  // song player's scrubber).
  VideoPlayerController? _performVideoController;
  bool _performVideoLoading = false;
  String? _performVideoError;
  bool _performPolling = false;

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

  // ─── composing (the signature "AI magic moment") ───────────────────────────
  //
  // Ordered post-approval generation stages a `kind=song` run actually walks
  // through server-side (verified against pipeline/api.py + run.py, NOT
  // guessed): writing_lyrics → [awaiting_approval, user pays] →
  // generating_song → generating_cover → aligning → detecting_beats (only
  // for video_mode != "static") → assembling → complete. `writing_lyrics`
  // is included even though it precedes payment (real code writes it, and
  // it renders as an already-"done" step once the run reaches
  // generating_song, which is the only way it's ever actually observed
  // here in practice). `analyzing` (YouTube-import pre-approval) is
  // deliberately NOT a composing stage — it falls through to the plain
  // status header below, unchanged.
  static const _composingStatuses = {
    'writing_lyrics',
    'generating_song',
    'generating_cover',
    'aligning',
    'detecting_beats',
    'assembling',
  };

  /// Whether [s] is mid-generation and should show [ComposingView] instead
  /// of the plain status header — the live counterpart of
  /// `run_detail_screen.dart`'s `run.isRunning` branch. Deliberately
  /// excludes `awaiting_approval` (pre-spend review — reachable here if the
  /// user backed out of [SongApproveScreen] without approving/discarding)
  /// even though it's non-terminal, per the recipe in Task 5's report.
  bool _isComposing(SongSummary s) =>
      !_terminalStatuses.contains(s.status) &&
      s.status != 'awaiting_approval' &&
      _composingStatuses.contains(s.status);

  /// First grapheme of the song's artist/title/theme for the composing
  /// screen's hero [ArtistBadge] — mirrors the pattern in
  /// `run_detail_screen.dart`/`artist_screen.dart`.
  String _composingMonogram(SongSummary s) {
    final name = (s.artistName ?? s.title ?? s.theme ?? '').trim();
    return name.isEmpty ? '?' : name.characters.first;
  }

  /// Maps the song's live status to an ordered [StepItem] list. Stage
  /// order/labels reuse the existing `homeStatus*` copy this app already
  /// shows for the exact same status codes on the home "Your songs" list
  /// (`lib/widgets/home/home_shared.dart:songStatusStyle`) — no new
  /// information, only a new presentation. `detecting_beats` is omitted
  /// entirely for `video_mode == "static"` songs, matching the backend:
  /// that stage is never written for static renders.
  List<StepItem> _composingSteps(BuildContext context, SongSummary s) {
    final l = context.l10n;
    final stages = [
      'writing_lyrics',
      'generating_song',
      'generating_cover',
      'aligning',
      if (s.videoMode != 'static') 'detecting_beats',
      'assembling',
    ];
    var activeIndex = stages.indexOf(s.status);
    if (activeIndex == -1) activeIndex = 0;

    String labelFor(String stage) => switch (stage) {
          'writing_lyrics' => l.homeStatusWritingLyrics,
          'generating_song' => l.homeStatusComposing,
          'generating_cover' => l.homeStatusDesigningCover,
          'aligning' => l.homeStatusSyncingLyrics,
          'detecting_beats' => l.homeStatusSyncingBeat,
          'assembling' => l.homeStatusRendering,
          _ => stage,
        };

    return [
      for (var i = 0; i < stages.length; i++)
        StepItem(
          label: labelFor(stages[i]),
          state: i < activeIndex
              ? StepPhase.done
              : i == activeIndex
                  ? StepPhase.active
                  : StepPhase.pending,
          // Songs have no fractional per-stage progress to report.
        ),
    ];
  }

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
      if (s.performStatus == 'rendering') _pollPerformStatus();
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
        // copyWith overrides only what the SSE event carries; every other
        // field (title/theme/artist/released/youtube/source/trendRationale…)
        // is preserved automatically — a hand-rebuild here used to silently
        // drop source/trendRationale.
        final merged = summary.copyWith(
          status: event['status'] as String?,
          hasVideo: summary.hasVideo || (event['status'] == 'complete'),
          chosenTake: event['chosen_take'] as int?,
          lastError: event['last_error'] as String?,
          failureStage: event['failure_stage'] as String?,
          performStatus: event['perform_status'] as String?,
          performVideo: event['perform_video'] as String?,
        );
        setState(() => _summary = merged);
        if (merged.performStatus == 'rendering') _pollPerformStatus();
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
          if (!mounted) return;
          setState(() => _summary = s);
          if (s.performStatus == 'rendering') _pollPerformStatus();
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

  // ─── "make me sing this" ────────────────────────────────────────────────────

  Future<void> _openPerformSheet() async {
    final status = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => PerformSheet(
        client: widget.client,
        runId: widget.runId,
        performCredits: _summary?.performCredits,
      ),
    );
    if (status == null || !mounted) return;
    _mergePerformStatus(status, video: null);
    if (status == 'rendering') _pollPerformStatus();
  }

  /// Patch just the perform fields into the current snapshot so the UI
  /// reflects the render kicking off without waiting for a full refetch.
  void _mergePerformStatus(String status, {String? video}) {
    final s = _summary;
    if (s == null) return;
    setState(() {
      _summary = s.copyWith(performStatus: status, performVideo: video);
    });
  }

  /// Slow poll for `performStatus` specifically. The main [_poll]/SSE
  /// machinery is tied to the song's own lifecycle and stops once
  /// `status` is terminal (already "complete" by the time this feature is
  /// reachable) — so once a render is kicked off we re-fetch the same
  /// [FacelessApiClient.getSong] snapshot on a timer until it resolves.
  Future<void> _pollPerformStatus() async {
    if (_performPolling) return; // already looping
    _performPolling = true;
    try {
      while (mounted && _summary?.performStatus == 'rendering') {
        await Future.delayed(const Duration(seconds: 4));
        if (!mounted) return;
        try {
          final s = await widget.client.getSong(widget.runId);
          if (mounted) setState(() => _summary = s);
        } catch (_) {
          // Tolerate transient errors; the loop retries.
        }
      }
    } finally {
      _performPolling = false;
    }
  }

  Future<void> _initPerformVideo() async {
    setState(() {
      _performVideoLoading = true;
      _performVideoError = null;
    });
    final old = _performVideoController;
    _performVideoController = null;
    old?.removeListener(_onPerformVideoTick);
    await old?.dispose();

    try {
      final url = await widget.client.performVideoUrl(widget.runId);
      final c = VideoPlayerController.networkUrl(url);
      await c.initialize();
      c.setLooping(false);
      c.addListener(_onPerformVideoTick);
      if (!mounted) {
        await c.dispose();
        return;
      }
      setState(() {
        _performVideoController = c;
        _performVideoLoading = false;
      });
      c.play();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _performVideoLoading = false;
        _performVideoError = e.toString();
      });
    }
  }

  void _onPerformVideoTick() {
    if (!mounted) return;
    setState(() {});
  }

  /// Save/share affordance for perform.mp4 — same authed-URL hand-off as
  /// [_downloadVideo].
  Future<void> _openPerformVideoExternally() async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      final uri = await widget.client.performVideoUrl(widget.runId);
      await launchUrl(uri, webOnlyWindowName: '_blank');
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(
          SnackBar(content: Text(context.l10n.songDetailDownloadFailed('$e'))),
        );
      }
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

  /// Artist Core one-step door: save this song's voice as a persona AND
  /// create an artist wrapping it (POST /artists/from-song). The song
  /// joins the new artist's discography.
  Future<void> _showMakeArtistDialog(SongSummary s) async {
    final nameCtrl = TextEditingController(text: s.title ?? '');
    final create = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(ctx.l10n.artistMakeFromSongButton),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              ctx.l10n.artistMakeFromSongBody,
              style: const TextStyle(fontSize: 13),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: nameCtrl,
              decoration: InputDecoration(
                labelText: ctx.l10n.artistNameLabel,
                border: const OutlineInputBorder(),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: Text(ctx.l10n.commonCancel)),
          FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: Text(ctx.l10n.artistCreateButton)),
        ],
      ),
    );
    if (create != true || !mounted) return;
    final name = nameCtrl.text.trim();
    if (name.isEmpty) return;
    final messenger = ScaffoldMessenger.of(context);
    try {
      final artist = await widget.client.createArtistFromSong(
        runId: widget.runId,
        name: name,
      );
      if (mounted) {
        messenger.showSnackBar(SnackBar(
          content: Text(context.l10n.artistCreatedSnack(artist.name)),
          duration: const Duration(seconds: 5),
        ));
      }
    } on FacelessApiException catch (e) {
      // 409 (duplicate handle) / 422 (no voice on this take) etc — the
      // server detail is the actionable part; surface it as-is.
      if (mounted) {
        messenger.showSnackBar(SnackBar(
            content: Text(context.l10n.artistCreateFailed(e.message))));
      }
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(
            SnackBar(content: Text(context.l10n.artistCreateFailed('$e'))));
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

  // ─── release to stores ──────────────────────────────────────────────────────

  /// Browser download of the store-ready release zip — same url_launcher
  /// hand-off as the MP4 download. No pre-check: if the package isn't
  /// ready the server answers the navigation itself.
  Future<void> _downloadReleasePackage() async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      final uri = await widget.client.releasePackageUrl(widget.runId);
      await launchUrl(uri, webOnlyWindowName: '_blank');
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(
          SnackBar(content: Text(context.l10n.songDetailDownloadFailed('$e'))),
        );
      }
    }
  }

  Future<void> _toggleReleased(bool released, StateSetter setDialogState,
      void Function(bool) setBusy) async {
    final messenger = ScaffoldMessenger.of(context);
    setDialogState(() => setBusy(true));
    try {
      final confirmed = await widget.client.markReleased(widget.runId, released);
      if (!mounted) return;
      // Sync screen state so the button label + list badges update.
      final s = _summary;
      if (s != null) {
        setState(() {
          _summary = s.copyWith(released: confirmed);
        });
      }
      setDialogState(() => setBusy(false));
      messenger.showSnackBar(SnackBar(
        content: Text(confirmed
            ? context.l10n.releaseMarkedSnack
            : context.l10n.releaseUnmarkedSnack),
      ));
    } catch (e) {
      if (!mounted) return;
      setDialogState(() => setBusy(false));
      messenger.showSnackBar(
        SnackBar(content: Text(context.l10n.releaseMarkFailed('$e'))),
      );
    }
  }

  Future<void> _showReleaseDialog(SongSummary s) async {
    var busy = false;
    await showDialog<void>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) {
          final released = _summary?.released ?? s.released;
          final steps = [
            ctx.l10n.releaseStep1,
            ctx.l10n.releaseStep2,
            ctx.l10n.releaseStep3,
            ctx.l10n.releaseStep4,
            ctx.l10n.releaseStep5,
            ctx.l10n.releaseStep6,
            ctx.l10n.releaseStep7,
            ctx.l10n.releaseStep8,
          ];
          return AlertDialog(
            title: Text(ctx.l10n.releaseDialogTitle),
            content: SizedBox(
              width: 420,
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(ctx.l10n.releaseDialogExplainer,
                        style: const TextStyle(fontSize: 13)),
                    // Non-blocking nudge: the package still builds without
                    // an artist, but branding is more consistent with one.
                    if (s.artistId == null) ...[
                      const SizedBox(height: 10),
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Icon(Icons.lightbulb_outline,
                              size: 16, color: FacelessTheme.warning),
                          const SizedBox(width: 6),
                          Expanded(
                            child: Text(
                              ctx.l10n.releaseArtistHint,
                              style: const TextStyle(
                                  fontSize: 12,
                                  color: FacelessTheme.warning),
                            ),
                          ),
                        ],
                      ),
                    ],
                    const SizedBox(height: 14),
                    for (var i = 0; i < steps.length; i++)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Container(
                              width: 22,
                              height: 22,
                              alignment: Alignment.center,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                color: FacelessTheme.accent
                                    .withValues(alpha: 0.14),
                              ),
                              child: Text('${i + 1}',
                                  style: const TextStyle(
                                      fontSize: 11,
                                      fontWeight: FontWeight.w700,
                                      color: FacelessTheme.accent)),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(steps[i],
                                  style: const TextStyle(
                                      fontSize: 13, height: 1.35)),
                            ),
                          ],
                        ),
                      ),
                    const SizedBox(height: 4),
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      dense: true,
                      title: Text(ctx.l10n.releaseMarkAsReleased,
                          style: const TextStyle(
                              fontSize: 13, fontWeight: FontWeight.w600)),
                      value: released,
                      onChanged: busy
                          ? null
                          : (v) => _toggleReleased(
                              v, setDialogState, (b) => busy = b),
                    ),
                  ],
                ),
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: Text(ctx.l10n.commonClose),
              ),
              FilledButton.icon(
                icon: const Icon(Icons.download),
                label: Text(ctx.l10n.releaseDownloadPackage),
                onPressed: _downloadReleasePackage,
              ),
            ],
          );
        },
      ),
    );
  }

  // ─── publish to YouTube ─────────────────────────────────────────────────────

  /// Local-state stamp after a successful publish so the button flips to
  /// "On YouTube" without a refetch.
  void _setYoutubeUrl(String url) {
    final s = _summary;
    if (s == null) return;
    setState(() {
      _summary = s.copyWith(youtubeUrl: url);
    });
  }

  Future<void> _openOnYoutube(SongSummary s) async {
    final url = s.youtubeUrl;
    if (url == null) return;
    final messenger = ScaffoldMessenger.of(context);
    try {
      await launchUrl(Uri.parse(url), webOnlyWindowName: '_blank');
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(SnackBar(content: Text('$e')));
      }
    }
  }

  Future<void> _showPublishYoutubeDialog(SongSummary s) async {
    final l10n = context.l10n;
    final title = s.title ?? s.theme ?? l10n.songDetailAiSongFallback;
    // Metadata preview — the exact title line the upload will use.
    final preview =
        s.artistName != null ? '$title — ${s.artistName}' : title;
    final messenger = ScaffoldMessenger.of(context);
    var busy = false;
    await showDialog<void>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: Text(ctx.l10n.ytPublishDialogTitle),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                preview,
                style: const TextStyle(
                    fontWeight: FontWeight.w700, fontSize: 14),
              ),
              const SizedBox(height: 10),
              // Pre-audit reality: Google caps unreviewed apps to private
              // uploads. One sentence so the user isn't surprised.
              Text(
                ctx.l10n.ytPublishPreauditNote,
                style: const TextStyle(fontSize: 13, height: 1.35),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: busy ? null : () => Navigator.pop(ctx),
              child: Text(ctx.l10n.commonCancel),
            ),
            FilledButton.icon(
              icon: busy
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(
                          strokeWidth: 2, color: Colors.white),
                    )
                  : const Icon(Icons.play_circle_outline, size: 18),
              label: Text(ctx.l10n.ytPublish),
              onPressed: busy
                  ? null
                  : () async {
                      setDialogState(() => busy = true);
                      try {
                        final url = await widget.client
                            .publishYoutube(widget.runId);
                        if (!mounted) return;
                        _setYoutubeUrl(url);
                        if (ctx.mounted) Navigator.pop(ctx);
                        messenger.showSnackBar(
                            SnackBar(content: Text(l10n.ytPublishedSnack)));
                      } on FacelessApiException catch (e) {
                        if (!mounted) return;
                        if (ctx.mounted) Navigator.pop(ctx);
                        // 409 "youtube not connected" → route the user to
                        // Settings; everything else surfaces the server
                        // message ("no finished video yet", 502 upload…).
                        final notConnected = e.status == 409 &&
                            e.message.contains('not connected');
                        messenger.showSnackBar(SnackBar(
                          content: Text(notConnected
                              ? l10n.ytNotConnectedSnack
                              : l10n.ytPublishFailed(e.message)),
                        ));
                      } catch (e) {
                        if (!mounted) return;
                        if (ctx.mounted) Navigator.pop(ctx);
                        messenger.showSnackBar(SnackBar(
                            content: Text(l10n.ytPublishFailed('$e'))));
                      }
                    },
            ),
          ],
        ),
      ),
    );
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
      backgroundColor: Colors.transparent,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
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
          const SizedBox(height: 20),
          // In-progress ("composing") is the signature AI-magic moment —
          // the live counterpart of run_detail_screen.dart's ComposingView
          // wiring (that screen is dead code; this is the real user-facing
          // song generation surface). Every other state keeps the plain
          // editorial title + status header below, untouched in spirit.
          if (_isComposing(s)) ...[
            ComposingView(
              monogram: _composingMonogram(s),
              artistName: s.artistName,
              title: s.title ?? s.theme,
              steps: _composingSteps(context, s),
              // No mid-render cancel affordance exists on this screen today
              // (the AppBar's delete button is deliberately hidden for
              // exactly these statuses — see the condition above), so this
              // stays behavior-preserving rather than inventing one.
            ),
          ] else ...[
            EditorialHeading(
              s.title ?? l10n.songDetailTitleFallback,
              size: 26,
            ),
            const SizedBox(height: 10),
            _buildStatusCard(context, s),
          ],
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
            // "Make me sing this" — hidden unless the backend enables the
            // feature (perform_enabled); its money guard + Kie id land first.
            if (s.performEnabled) ...[
              const SizedBox(height: 8),
              _buildPerformSection(context, s),
            ],
            const SizedBox(height: 16),
            const Hairline(),
            const SizedBox(height: 16),
            // Save this song's voice as a Persona for reuse in
            // future songs. Closest thing Suno offers to voice
            // cloning across generations.
            OutlinedButton.icon(
              icon: const Icon(Icons.record_voice_over),
              label: Text(l10n.songDetailSaveVoiceTitle),
              onPressed: () => _showSavePersonaDialog(s),
            ),
            const SizedBox(height: 8),
            // Artist Core: turn this song's singer into a full artist
            // (voice persona + identity + discography) in one step.
            // TODO(artist-core): "Add to artist" (assign an EXISTING song
            // to an artist) needs a song-assignment endpoint on the
            // backend; skipped for v1.
            OutlinedButton.icon(
              icon: const Icon(Icons.star_outline),
              label: Text(l10n.artistMakeFromSongButton),
              onPressed: () => _showMakeArtistDialog(s),
            ),
            const SizedBox(height: 8),
            // Distribution: guided release-package export + released toggle.
            // Still opens when already released (to re-download or un-mark);
            // the label flips to a "done" state. YouTube publish sits next
            // to it — the button flips to "On YouTube" once published.
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.rocket_launch_outlined),
                    label: Text(s.released
                        ? l10n.releaseButtonReleased
                        : l10n.releaseButton),
                    onPressed: () => _showReleaseDialog(s),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: s.youtubeUrl == null
                      ? OutlinedButton.icon(
                          icon: const Icon(Icons.play_circle_outline),
                          label: Text(l10n.ytPublishButton),
                          onPressed: () => _showPublishYoutubeDialog(s),
                        )
                      : OutlinedButton.icon(
                          icon: const Icon(Icons.play_arrow),
                          label: Text(l10n.ytOnYoutubeButton),
                          onPressed: () => _openOnYoutube(s),
                        ),
                ),
              ],
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
    return ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: SizedBox(
        height: 320,
        width: double.infinity,
        child: _showCover
            ? _MaterializingCover(client: widget.client, runId: widget.runId)
            : _CoverPlaceholder(seed: widget.runId),
      ),
    );
  }

  // ─── status card ────────────────────────────────────────────────────────────

  /// Plain status header for every non-composing state (awaiting_approval,
  /// analyzing, complete, failed, canceled). [StatusPill] only models the
  /// ready/review "kinds" — complete and awaiting_approval get the pill,
  /// everything else keeps the original spinner-or-icon row (now in a
  /// [GlassCard]), preserving [_stageLabel]'s exact copy either way.
  Widget _buildStatusCard(BuildContext context, SongSummary s) {
    final label = _stageLabel(context.l10n, s.status);
    if (s.status == 'complete') {
      return GlassCard(
        padding: const EdgeInsets.all(16),
        child: StatusPill(label: label, kind: StatusKind.ready),
      );
    }
    if (s.status == 'awaiting_approval') {
      return GlassCard(
        padding: const EdgeInsets.all(16),
        child: StatusPill(label: label, kind: StatusKind.review),
      );
    }
    final isTerminal = _terminalStatuses.contains(s.status);
    return GlassCard(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          if (!isTerminal)
            const SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(
                  strokeWidth: 2, color: FacelessTheme.accent),
            )
          else
            const Icon(Icons.error, color: FacelessTheme.danger),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              label,
              style: const TextStyle(
                  fontWeight: FontWeight.w500,
                  color: FacelessTheme.textPrimary),
            ),
          ),
        ],
      ),
    );
  }

  // ─── inline video ───────────────────────────────────────────────────────────

  Widget _buildVideoSection(BuildContext context) {
    final c = _videoController;

    if (c == null && !_videoLoading && _videoError == null) {
      // Not started yet — a "sound made visible" waveform above the
      // play/download row, matching the composing screen's motif now that
      // the song is ready.
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Center(child: LivingWaveform(height: 32)),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: GradientButton(
                  icon: Icons.play_arrow,
                  label: context.l10n.songDetailPlayVideo,
                  expand: true,
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
                        color: FacelessTheme.textPrimary,
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
                              style: const TextStyle(
                                  color: FacelessTheme.textPrimary)),
                          IconButton(
                            icon: const Icon(Icons.replay_10,
                                color: FacelessTheme.textPrimary),
                            onPressed: () => c.seekTo(
                                pos - const Duration(seconds: 10)),
                          ),
                          IconButton(
                            icon: const Icon(Icons.forward_10,
                                color: FacelessTheme.textPrimary),
                            onPressed: () => c.seekTo(
                                pos + const Duration(seconds: 10)),
                          ),
                          const Spacer(),
                          Text(_fmt(dur),
                              style: const TextStyle(
                                  color: FacelessTheme.textPrimary)),
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

  // ─── "make me sing this" ────────────────────────────────────────────────────

  Widget _buildPerformSection(BuildContext context, SongSummary s) {
    switch (s.performStatus) {
      case 'rendering':
        return GlassCard(
          padding: const EdgeInsets.all(14),
          child: const Row(
            children: [
              SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
              SizedBox(width: 12),
              Expanded(
                child: Text(
                  'Rendering your performance video — this can take a '
                  'few minutes…',
                ),
              ),
            ],
          ),
        );
      case 'complete':
        return GlassCard(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                '✨ Your performance video',
                style: TextStyle(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 10),
              _buildPerformVideoSection(context),
            ],
          ),
        );
      case 'failed':
        return GlassCard(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Performance video failed to render.',
                style: TextStyle(
                  color: Theme.of(context).colorScheme.error,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 10),
              OutlinedButton.icon(
                icon: const Icon(Icons.refresh),
                label: const Text('Try again'),
                onPressed: _openPerformSheet,
              ),
            ],
          ),
        );
      default:
        // Never started — offer the feature.
        return OutlinedButton.icon(
          icon: const Icon(Icons.auto_awesome),
          label: const Text('✨ Make me sing this'),
          onPressed: _openPerformSheet,
        );
    }
  }

  Widget _buildPerformVideoSection(BuildContext context) {
    final c = _performVideoController;

    if (c == null && !_performVideoLoading && _performVideoError == null) {
      return Row(
        children: [
          Expanded(
            child: FilledButton.icon(
              icon: const Icon(Icons.play_arrow),
              label: const Text('Play performance'),
              onPressed: _initPerformVideo,
            ),
          ),
          const SizedBox(width: 12),
          OutlinedButton.icon(
            icon: const Icon(Icons.ios_share),
            label: const Text('Save / share'),
            onPressed: _openPerformVideoExternally,
          ),
        ],
      );
    }

    if (_performVideoLoading) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.symmetric(vertical: 24),
          child: CircularProgressIndicator(),
        ),
      );
    }

    if (_performVideoError != null) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            context.l10n.songDetailVideoLoadError(_performVideoError!),
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            icon: const Icon(Icons.refresh),
            label: Text(context.l10n.commonRetry),
            onPressed: _initPerformVideo,
          ),
        ],
      );
    }

    if (c == null) return const SizedBox.shrink();

    return ClipRRect(
      borderRadius: BorderRadius.circular(12),
      child: GestureDetector(
        onTap: () => setState(() {
          c.value.isPlaying ? c.pause() : c.play();
        }),
        child: AspectRatio(
          aspectRatio: c.value.aspectRatio,
          child: Stack(
            alignment: Alignment.center,
            children: [
              VideoPlayer(c),
              if (!c.value.isPlaying)
                const Icon(Icons.play_circle_filled,
                    size: 64, color: Colors.white70),
            ],
          ),
        ),
      ),
    );
  }

  // ─── take swap ──────────────────────────────────────────────────────────────

  Widget _buildTakeSwapCard(BuildContext context, SongSummary s) {
    return GlassCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Eyebrow(context.l10n.songDetailActiveTake),
          const SizedBox(height: 10),
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
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        color: FacelessTheme.danger.withValues(alpha: 0.08),
        border: Border.all(color: FacelessTheme.danger.withValues(alpha: 0.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.error_outline,
                  color: FacelessTheme.danger, size: 20),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    color: FacelessTheme.danger,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            s.lastError ?? context.l10n.songDetailUnknownError,
            style: const TextStyle(color: FacelessTheme.textPrimary),
          ),
          if (hint != null) ...[
            const SizedBox(height: 8),
            Text(
              hint,
              style: TextStyle(
                fontSize: 12,
                fontStyle: FontStyle.italic,
                color: FacelessTheme.textSecondary.withValues(alpha: 0.9),
              ),
            ),
          ],
        ],
      ),
    );
  }

  // ─── lifecycle ──────────────────────────────────────────────────────────────

  @override
  void dispose() {
    _polling = false;
    _performPolling = false;
    _eventsSub?.cancel();
    _videoController?.removeListener(_onVideoTick);
    _videoController?.dispose();
    _performVideoController?.removeListener(_onPerformVideoTick);
    _performVideoController?.dispose();
    super.dispose();
  }
}

// ─── cover materialising ──────────────────────────────────────────────────

/// Deterministic jewel-tone wash shown while no cover exists yet (or as the
/// base layer under [_MaterializingCover] so a slow network never flashes a
/// plain grey box). Seeded so the same song always gets the same gradient.
class _CoverPlaceholder extends StatelessWidget {
  final String seed;
  const _CoverPlaceholder({required this.seed});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        gradient: coverGradient(seed),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: FacelessTheme.border),
      ),
      alignment: Alignment.center,
      child: Icon(Icons.music_note,
          size: 56, color: FacelessTheme.textPrimary.withValues(alpha: 0.55)),
    );
  }
}

/// Reveals the fetched cover with a champagne shimmer/fade once its image
/// has actually painted a frame — not merely once its URL resolved, so a
/// slow CDN never skips straight to a half-decoded image. The [_CoverPlaceholder]
/// wash stays underneath throughout (visible instantly, and again if the
/// image ever errors) so there's never a blank/grey gap.
///
/// The cover URL is fetched exactly once per State lifetime (`late final`,
/// mirroring `_ClipThumbBoxState`/`_CharacterSheetPanelState` in
/// run_detail_screen.dart) rather than on every parent rebuild — the parent
/// rebuilds frequently (e.g. every video-player tick), and a fresh
/// `Future`/`Image` on each of those would otherwise replay this reveal (or
/// flicker back to the placeholder) constantly. This is safe because the
/// only flow that actually changes the cover image ([_regenerateCover])
/// already routes through a `_summary = null` intermediate state, which
/// tears down and rebuilds this whole subtree — a fresh [_MaterializingCoverState]
/// is created then, so the new cover's URL is fetched fresh.
///
/// Honors `MediaQuery.disableAnimations` (jumps straight to the fully
/// revealed state, no fade/scale/wash).
class _MaterializingCover extends StatefulWidget {
  final FacelessApiClient client;
  final String runId;
  const _MaterializingCover({required this.client, required this.runId});

  @override
  State<_MaterializingCover> createState() => _MaterializingCoverState();
}

class _MaterializingCoverState extends State<_MaterializingCover> {
  late final Future<Uri> _future = widget.client.songCoverUrl(widget.runId);
  bool _loaded = false;

  void _markLoaded() {
    if (_loaded || !mounted) return;
    setState(() => _loaded = true);
  }

  @override
  Widget build(BuildContext context) {
    final reduceMotion =
        MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    final revealDuration =
        reduceMotion ? Duration.zero : const Duration(milliseconds: 900);
    return FutureBuilder<Uri>(
      future: _future,
      builder: (ctx, snap) {
        if (!snap.hasData) return _CoverPlaceholder(seed: widget.runId);
        return Stack(
          fit: StackFit.expand,
          children: [
            _CoverPlaceholder(seed: widget.runId),
            Image.network(
              snap.data!.toString(),
              fit: BoxFit.cover,
              errorBuilder: (ctx2, err, stack) {
                // A genuinely missing/broken cover: mark "loaded" so the
                // shimmer wash clears instead of glowing forever over the
                // plain gradient placeholder underneath.
                WidgetsBinding.instance
                    .addPostFrameCallback((_) => _markLoaded());
                return const SizedBox.shrink();
              },
              frameBuilder: (ctx3, child, frame, wasSynchronouslyLoaded) {
                // A cached image (e.g. re-opening a song already viewed
                // this session) resolves synchronously — still mark it
                // loaded so the wash clears, just skip the fade-in itself
                // (nothing to fade from; the frame is already on screen).
                if (frame != null || wasSynchronouslyLoaded) {
                  WidgetsBinding.instance
                      .addPostFrameCallback((_) => _markLoaded());
                }
                if (wasSynchronouslyLoaded) return child;
                return TweenAnimationBuilder<double>(
                  tween: Tween(begin: 0.0, end: _loaded ? 1.0 : 0.0),
                  duration: revealDuration,
                  curve: Curves.easeOutCubic,
                  builder: (context, t, c) => Opacity(
                    opacity: t,
                    child: Transform.scale(scale: 1.04 - (0.04 * t), child: c),
                  ),
                  child: child,
                );
              },
            ),
            // Champagne shimmer wash — bright at the moment the image
            // starts painting, fading away as the reveal completes.
            IgnorePointer(
              child: TweenAnimationBuilder<double>(
                tween: Tween(begin: 1.0, end: _loaded ? 0.0 : 1.0),
                duration: revealDuration,
                curve: Curves.easeOutCubic,
                builder: (context, t, _) => Opacity(
                  opacity: t * 0.5,
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                        colors: [
                          FacelessTheme.accent2.withValues(alpha: 0.55),
                          Colors.transparent,
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}
