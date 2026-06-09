import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:video_player/video_player.dart';

import '../api/client.dart';
import '../api/models.dart';
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

  // Inline video player state
  VideoPlayerController? _videoController;
  bool _videoLoading = false;
  String? _videoError;
  bool _showControls = true;

  static const _terminalStatuses = {'complete', 'failed', 'canceled'};

  static const _stageLabels = <String, String>{
    'awaiting_approval': 'Waiting for approval',
    'generating_song': 'Generating song (Suno ~30 s)…',
    'generating_cover': 'Generating cover (~15 s)…',
    'assembling': 'Assembling video…',
    'complete': 'Done',
    'failed': 'Failed',
    'canceled': 'Canceled',
  };

  @override
  void initState() {
    super.initState();
    _poll();
  }

  // ─── polling ────────────────────────────────────────────────────────────────

  Future<void> _poll() async {
    while (mounted && _polling) {
      try {
        final s = await widget.client.getSong(widget.runId);
        if (!mounted) return;
        setState(() => _summary = s);
        if (_terminalStatuses.contains(s.status)) {
          setState(() => _polling = false);
          return;
        }
      } catch (_) {
        // tolerate transient errors during polling
      }
      await Future.delayed(const Duration(seconds: 3));
    }
  }

  // ─── take swap ──────────────────────────────────────────────────────────────

  Future<void> _swap(int take) async {
    setState(() => _swapping = true);
    try {
      await widget.client.swapTake(widget.runId, take);
      final s = await widget.client.getSong(widget.runId);
      if (!mounted) return;
      setState(() => _summary = s);
      // Reload the video player so it picks up the new take's clip
      await _initVideo();
    } on FacelessApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Swap failed: ${e.message}')),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Swap failed: $e')),
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
          title: const Text('Retry will re-charge'),
          content: const Text(
            'The song generation failed. Retrying will spawn a new Suno '
            'job and deduct credits again. Continue?',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Retry'),
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
        SnackBar(content: Text('Retry failed: ${e.message}')),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Retry failed: $e')),
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
          SnackBar(content: Text('Download failed: $e')),
        );
      }
    }
  }

  Future<void> _showDeleteDialog(SongSummary s) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete this song?'),
        content: Text(
          'This permanently removes the song, cover, takes, and final '
          'video for "${s.title ?? s.theme ?? 'this run'}". '
          'Credits already spent on Suno + Flux are not refunded.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(ctx).colorScheme.error,
            ),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete'),
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
        messenger.showSnackBar(const SnackBar(content: Text('Song deleted')));
        // Pop back to the songs list so the deleted run isn't still
        // showing on screen.
        nav.pop();
      }
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(SnackBar(content: Text('Delete failed: $e')));
      }
    }
  }

  Future<void> _showSavePersonaDialog(SongSummary s) async {
    final nameCtrl = TextEditingController(text: s.title ?? '');
    final descCtrl = TextEditingController(
      text: 'Arabic male vocal, warm baritone, gentle vibrato, '
          'intimate close-mic, modern 2020s production',
    );
    final saved = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Save this voice'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'Locks the singer\'s voice from this song so you can reuse '
              'it on future generations.',
              style: TextStyle(fontSize: 13),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: nameCtrl,
              decoration: const InputDecoration(
                labelText: 'Voice name',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: descCtrl,
              maxLines: 3,
              decoration: const InputDecoration(
                labelText: 'Description',
                helperText: 'Genre, mood, vocal qualities',
                border: OutlineInputBorder(),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Save')),
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
          content: Text('Voice "${persona.name}" saved. Use it on '
              'the next song from the New Song form.'),
          duration: const Duration(seconds: 5),
        ));
      }
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(SnackBar(content: Text('Save failed: $e')));
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
        messenger.showSnackBar(SnackBar(content: Text('Download failed: $e')));
      }
    }
  }

  Future<void> _shareSong() async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      final info = await widget.client.shareSong(widget.runId);
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Share this song'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'Anyone with this link can play the song — no sign-in '
                'needed. Paste it in WhatsApp, Twitter, or anywhere; '
                'the preview shows the cover.',
                style: TextStyle(fontSize: 13),
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
              child: const Text('Close'),
            ),
            TextButton.icon(
              icon: const Icon(Icons.open_in_new),
              label: const Text('Open'),
              onPressed: () {
                Navigator.pop(ctx);
                launchUrl(Uri.parse(info.url),
                    webOnlyWindowName: '_blank');
              },
            ),
            FilledButton.icon(
              icon: const Icon(Icons.copy),
              label: const Text('Copy link'),
              onPressed: () async {
                await Clipboard.setData(ClipboardData(text: info.url));
                if (ctx.mounted) Navigator.pop(ctx);
                messenger.showSnackBar(
                  const SnackBar(content: Text('Link copied to clipboard')),
                );
              },
            ),
          ],
        ),
      );
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(SnackBar(content: Text('Share failed: $e')));
      }
    }
  }

  Future<void> _regenerateCover() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Regenerate cover?'),
        content: const Text(
          'Calls Flux for a fresh cover image (~\$0.03) and re-assembles '
          'the video with the new cover. Suno output is preserved. '
          'Takes ~2 minutes.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Regenerate')),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    try {
      await widget.client.regenerateSongCover(widget.runId);
      if (mounted) {
        messenger.showSnackBar(const SnackBar(
          content: Text('Regenerating cover — refresh in ~2 min'),
        ));
        // Re-poll to show the new "generating_cover" status
        setState(() {
          _summary = null;
        });
        _poll();
      }
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(SnackBar(content: Text('Failed: $e')));
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
    final s = _summary;
    if (s == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Song')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(
          s.title ?? 'Song',
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
              tooltip: 'Delete this song',
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
                    label: const Text('Download MP4'),
                    onPressed: _downloadVideo,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.music_note),
                    label: const Text('Download MP3'),
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
              label: const Text('Save this voice'),
              onPressed: () => _showSavePersonaDialog(s),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.share),
                    label: const Text('Share'),
                    onPressed: _shareSong,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.refresh),
                    label: const Text('Regenerate cover'),
                    onPressed: _regenerateCover,
                  ),
                ),
              ],
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
              label: const Text('Retry'),
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
                _stageLabels[s.status] ?? s.status,
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
              label: const Text('Play video'),
              onPressed: _initVideo,
            ),
          ),
          const SizedBox(width: 12),
          OutlinedButton.icon(
            icon: const Icon(Icons.download),
            label: const Text('Download'),
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
          Text('Could not load video: $_videoError',
              style: TextStyle(
                  color: Theme.of(context).colorScheme.error)),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            icon: const Icon(Icons.refresh),
            label: const Text('Retry'),
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
            Text('Active take',
                style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed:
                        _swapping || s.chosenTake == 1 ? null : () => _swap(1),
                    child: Text(s.chosenTake == 1 ? 'Take 1 ✓' : 'Use Take 1'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton(
                    onPressed:
                        _swapping || s.chosenTake == 2 ? null : () => _swap(2),
                    child: Text(s.chosenTake == 2 ? 'Take 2 ✓' : 'Use Take 2'),
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

  Widget _buildErrorCard(BuildContext context, SongSummary s) {
    return Card(
      color: Theme.of(context).colorScheme.errorContainer,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Error',
              style: TextStyle(
                fontWeight: FontWeight.bold,
                color: Theme.of(context).colorScheme.onErrorContainer,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              s.lastError ?? 'Unknown error',
              style: TextStyle(
                  color: Theme.of(context).colorScheme.onErrorContainer),
            ),
          ],
        ),
      ),
    );
  }

  // ─── lifecycle ──────────────────────────────────────────────────────────────

  @override
  void dispose() {
    _polling = false;
    _videoController?.removeListener(_onVideoTick);
    _videoController?.dispose();
    super.dispose();
  }
}
