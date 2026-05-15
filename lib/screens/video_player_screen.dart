import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:video_player/video_player.dart';

import '../api/client.dart';
import '../theme.dart';

class VideoPlayerScreen extends StatefulWidget {
  final FacelessApiClient client;
  final String runId;
  final String? title;
  final int? clipIndex;
  const VideoPlayerScreen({
    super.key,
    required this.client,
    required this.runId,
    this.title,
    this.clipIndex,
  });

  @override
  State<VideoPlayerScreen> createState() => _VideoPlayerScreenState();
}

class _VideoPlayerScreenState extends State<VideoPlayerScreen> {
  VideoPlayerController? _controller;
  String? _error;
  bool _showControls = true;
  // Auto-repair is single-shot per screen entry — if the first repair attempt
  // doesn't fix playback we don't loop forever on a broken file.
  bool _didAutoRepair = false;
  bool _isRepairing = false;
  // 422 path: server says the file is genuinely unrecoverable. Surface a
  // re-render prompt instead of the raw exception string.
  bool _needsRerender = false;

  Future<Uri> _resolveUrl() async {
    return widget.clipIndex == null
        ? await widget.client.videoUrl(widget.runId)
        : await widget.client.clipVideoUrl(widget.runId, widget.clipIndex!);
  }

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    try {
      final url = await _resolveUrl();
      final c = VideoPlayerController.networkUrl(url);
      await c.initialize();
      c.setLooping(false);
      c.play();
      c.addListener(_onTick);
      if (!mounted) {
        await c.dispose();
        return;
      }
      setState(() {
        _controller = c;
        _error = null;
      });
    } catch (e) {
      // Initialize() throws on browsers when the moov atom is absent or
      // the codec isn't supported. Try auto-repair once for the main
      // video; for individual clips we have nothing to repair.
      await _tryAutoRepair(error: e.toString());
    }
  }

  /// One-shot: call /runs/{id}/repair-video, then retry initialize.
  ///
  /// Skipped for clip URLs (we only repair final.mp4) and when we've
  /// already tried once this session. On 422 we flip _needsRerender so
  /// the user gets a clear "re-render required" UI instead of the raw
  /// API error string.
  Future<void> _tryAutoRepair({required String error}) async {
    final canRepair = widget.clipIndex == null && !_didAutoRepair;
    if (!canRepair) {
      if (mounted) setState(() => _error = error);
      return;
    }
    _didAutoRepair = true;
    if (mounted) {
      setState(() {
        _isRepairing = true;
        _error = null;
      });
    }
    try {
      await widget.client.repairVideo(widget.runId);
    } on FacelessApiException catch (e) {
      // 422: server-side ffprobe says the file is truly unrecoverable —
      // no point retrying, push the user toward a re-render.
      if (e.status == 422) {
        if (mounted) {
          setState(() {
            _isRepairing = false;
            _needsRerender = true;
          });
        }
        return;
      }
      if (mounted) {
        setState(() {
          _isRepairing = false;
          _error = 'Repair failed: ${e.message}';
        });
      }
      return;
    } catch (e) {
      if (mounted) {
        setState(() {
          _isRepairing = false;
          _error = 'Repair failed: $e';
        });
      }
      return;
    }
    if (!mounted) return;
    setState(() => _isRepairing = false);
    // Retry initialize with the same URL — the file on disk has been
    // re-muxed with +faststart so the second attempt should succeed.
    await _init();
  }

  void _onTick() {
    if (!mounted) return;
    final c = _controller;
    if (c != null && c.value.hasError && !_didAutoRepair) {
      // The controller decoded the header but then choked mid-stream.
      // Tear it down and run the same auto-repair path as the init
      // failure. Don't fall through to setState — _tryAutoRepair will
      // rebuild once it's done.
      final msg = c.value.errorDescription ?? 'playback error';
      _controller = null;
      c.removeListener(_onTick);
      c.dispose();
      _tryAutoRepair(error: msg);
      return;
    }
    setState(() {});
  }

  Future<void> _copyLink() async {
    final url = await _resolveUrl();
    await Clipboard.setData(ClipboardData(text: url.toString()));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Video URL copied — paste anywhere')),
    );
  }

  Future<void> _download() async {
    // On web `flutter run -d chrome`, opening a tab to the URL triggers
    // the browser's native download because the response has
    // Content-Disposition: attachment from FastAPI's FileResponse(filename=).
    // On mobile we'd swap to url_launcher / save to device — left as TODO.
    final url = await _resolveUrl();
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Open the link in a new tab to download'),
        duration: Duration(seconds: 2),
      ),
    );
    // copy to clipboard so user can paste into a new tab if window-open is blocked
    await Clipboard.setData(ClipboardData(text: url.toString()));
  }

  String _formatDuration(Duration d) {
    final m = d.inMinutes.toString().padLeft(2, '0');
    final s = (d.inSeconds % 60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        title: Text(
          widget.clipIndex == null
              ? (widget.title ?? widget.runId)
              : 'Clip ${widget.clipIndex.toString().padLeft(2, "0")}'
                '${widget.title != null ? " — ${widget.title}" : ""}',
          textDirection: TextDirection.rtl,
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.link),
            tooltip: 'Copy link',
            onPressed: _copyLink,
          ),
          IconButton(
            icon: const Icon(Icons.download),
            tooltip: 'Download',
            onPressed: _download,
          ),
        ],
      ),
      body: Center(
        child: _buildBody(),
      ),
    );
  }

  Widget _buildBody() {
    if (_needsRerender) {
      return Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.movie_filter_outlined,
                color: Colors.white70, size: 56),
            const SizedBox(height: 16),
            const Text(
              'This video can\'t be repaired.\n\n'
              'The mp4 file is corrupt at a level we can\'t fix without '
              're-rendering. Use the Reroll button on the run page to '
              'regenerate the affected clips.',
              style: TextStyle(color: Colors.white),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Back to run'),
            ),
          ],
        ),
      );
    }
    if (_isRepairing) {
      return const Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          CircularProgressIndicator(),
          SizedBox(height: 12),
          Text('Repairing playback…',
              style: TextStyle(color: Colors.white)),
        ],
      );
    }
    if (_error != null) {
      return Padding(
        padding: const EdgeInsets.all(24),
        child: Text(_error!,
            style: const TextStyle(color: Colors.white),
            textAlign: TextAlign.center),
      );
    }
    if (_controller == null) {
      return const CircularProgressIndicator();
    }
    return _buildPlayer();
  }

  Widget _buildPlayer() {
    final c = _controller!;
    final pos = c.value.position;
    final dur = c.value.duration;
    return GestureDetector(
      onTap: () => setState(() => _showControls = !_showControls),
      child: Stack(
        alignment: Alignment.center,
        children: [
          AspectRatio(
            aspectRatio: c.value.aspectRatio,
            child: VideoPlayer(c),
          ),
          if (_showControls) ...[
            // Tap-to-toggle play/pause
            AnimatedOpacity(
              opacity: _showControls ? 1.0 : 0.0,
              duration: const Duration(milliseconds: 200),
              child: Container(
                color: Colors.black26,
                child: Center(
                  child: IconButton(
                    iconSize: 80,
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
            // Bottom bar: scrub + time + replay
            Positioned(
              left: 0, right: 0, bottom: 0,
              child: Container(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                decoration: BoxDecoration(
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
                        onChanged: (v) =>
                            c.seekTo(Duration(milliseconds: v.toInt())),
                      ),
                    ),
                    Row(
                      children: [
                        Text(_formatDuration(pos),
                            style: const TextStyle(
                                color: Colors.white,
                                fontFeatures: [
                                  FontFeature.tabularFigures()
                                ])),
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
                        Text(_formatDuration(dur),
                            style: const TextStyle(
                                color: Colors.white,
                                fontFeatures: [
                                  FontFeature.tabularFigures()
                                ])),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  @override
  void dispose() {
    _controller?.removeListener(_onTick);
    _controller?.dispose();
    super.dispose();
  }
}
