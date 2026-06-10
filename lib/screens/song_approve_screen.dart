import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import 'song_detail_screen.dart';

class SongApproveScreen extends StatefulWidget {
  final FacelessApiClient client;
  final String runId;
  const SongApproveScreen({super.key, required this.client, required this.runId});

  @override
  State<SongApproveScreen> createState() => _SongApproveScreenState();
}

class _SongApproveScreenState extends State<SongApproveScreen> {
  SongScript? _script;
  String? _error;
  bool _busy = true;
  bool _approving = false;

  @override
  void initState() {
    super.initState();
    _pollUntilReady();
  }

  Future<void> _pollUntilReady() async {
    for (int i = 0; i < 30; i++) {
      try {
        final s = await widget.client.getSong(widget.runId);
        if (s.status == 'awaiting_approval') {
          final script = await widget.client.getSongScript(widget.runId);
          if (!mounted) return;
          setState(() {
            _script = script;
            _busy = false;
          });
          return;
        }
        if (s.status == 'failed') {
          if (!mounted) return;
          setState(() {
            _error = s.lastError ?? 'lyrics generation failed';
            _busy = false;
          });
          return;
        }
      } catch (e) {
        // Keep polling — may be a transient 404 while disk write settles
      }
      await Future.delayed(const Duration(seconds: 1));
    }
    if (!mounted) return;
    setState(() {
      _error = 'Timed out waiting for lyrics';
      _busy = false;
    });
  }

  Future<void> _editLyrics(SongScript s) async {
    final ctrl = TextEditingController(text: s.lyrics);
    final saved = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Edit lyrics'),
        content: SizedBox(
          width: 560,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'Keep Suno section tags ([Verse 1], [Chorus]) intact — '
                'Suno uses them to structure the arrangement. Dropping '
                'them gives a formless song.',
                style: TextStyle(fontSize: 12),
              ),
              const SizedBox(height: 12),
              Directionality(
                textDirection: s.language == 'ar' || s.language == 'he'
                        || s.language == 'fa' || s.language == 'ur'
                    ? TextDirection.rtl
                    : TextDirection.ltr,
                child: TextField(
                  controller: ctrl,
                  maxLines: 16,
                  style: const TextStyle(fontSize: 15, height: 1.6),
                  decoration: const InputDecoration(
                    border: OutlineInputBorder(),
                    alignLabelWithHint: true,
                  ),
                ),
              ),
            ],
          ),
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
    if (ctrl.text.length > 4000) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Lyrics exceed 4000 chars'),
      ));
      return;
    }
    setState(() => _busy = true);
    try {
      await widget.client.editSong(widget.runId, lyrics: ctrl.text);
      final script = await widget.client.getSongScript(widget.runId);
      if (!mounted) return;
      setState(() => _script = script);
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _regenLyrics() async {
    setState(() => _busy = true);
    try {
      await widget.client.regenerateSongLyrics(widget.runId);
      final script = await widget.client.getSongScript(widget.runId);
      if (!mounted) return;
      setState(() => _script = script);
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _regenCover() async {
    setState(() => _busy = true);
    try {
      await widget.client.regenerateSongCoverPrompt(widget.runId);
      final script = await widget.client.getSongScript(widget.runId);
      if (!mounted) return;
      setState(() => _script = script);
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _approve() async {
    setState(() => _approving = true);
    try {
      await widget.client.approveSong(widget.runId);
      if (!mounted) return;
      Navigator.of(context).pushReplacement(MaterialPageRoute(
        builder: (_) =>
            SongDetailScreen(client: widget.client, runId: widget.runId),
      ));
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = '$e';
        _approving = false;
      });
    }
  }

  Future<void> _discard() async {
    try {
      await widget.client.cancelSong(widget.runId);
    } catch (_) {
      // Even if cancel fails on server side, pop back so user isn't stuck.
    }
    if (!mounted) return;
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    if (_busy && _script == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Review draft')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }
    if (_error != null && _script == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Review draft')),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
              textAlign: TextAlign.center,
            ),
          ),
        ),
      );
    }
    final s = _script!;
    return Scaffold(
      appBar: AppBar(title: Text(s.title)),
      body: Stack(children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: ListView(
            children: [
              _SectionCard(
                title: 'Lyrics',
                body: _LyricsPreview(
                  lyrics: s.lyrics,
                  language: s.language,
                ),
                actions: [
                  TextButton.icon(
                    icon: const Icon(Icons.edit_outlined),
                    label: const Text('Edit'),
                    onPressed: _busy ? null : () => _editLyrics(s),
                  ),
                  TextButton.icon(
                    icon: const Icon(Icons.refresh),
                    label: const Text('Re-roll'),
                    onPressed: _busy ? null : _regenLyrics,
                  ),
                ],
              ),
              _SectionCard(
                title: 'Style',
                body: Text(s.stylePrompt),
              ),
              _SectionCard(
                title: 'Cover prompt',
                body: Text(s.coverPrompt),
                actions: [
                  TextButton.icon(
                    icon: const Icon(Icons.refresh),
                    label: const Text('Re-roll'),
                    onPressed: _busy ? null : _regenCover,
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Card(
                color: Theme.of(context).colorScheme.primaryContainer,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      const Icon(Icons.account_balance_wallet_outlined),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          'Cost: ${s.costCredits} credit'
                          '${s.costCredits == 1 ? '' : 's'} '
                          '(~\$${s.costUsd.toStringAsFixed(2)})',
                          style: const TextStyle(fontWeight: FontWeight.bold),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      icon: const Icon(Icons.delete_outline),
                      label: const Text('Discard'),
                      onPressed: _approving ? null : _discard,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: FilledButton.icon(
                      icon: _approving
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child:
                                  CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.check),
                      label: const Text('Approve & generate'),
                      onPressed: _approving ? null : _approve,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        if (_busy)
          Positioned.fill(
            child: ColoredBox(
              color: Colors.black.withValues(alpha: 0.15),
              child: const Center(child: CircularProgressIndicator()),
            ),
          ),
      ]),
    );
  }
}

class _SectionCard extends StatelessWidget {
  final String title;
  final Widget body;
  final List<Widget>? actions;
  const _SectionCard({required this.title, required this.body, this.actions});

  @override
  Widget build(BuildContext context) => Card(
        margin: const EdgeInsets.only(bottom: 12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              body,
              if (actions != null) ...[
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: actions!,
                ),
              ],
            ],
          ),
        ),
      );
}


/// Lyrics renderer that pulls section tags ([Verse 1], [Chorus], etc.)
/// out into colored chip headers — matches the public share page so
/// users approve what they'll actually see published.
class _LyricsPreview extends StatelessWidget {
  final String lyrics;
  final String language;
  const _LyricsPreview({required this.lyrics, required this.language});

  static final _sectionRe = RegExp(r'^\[([^\]]+)\]\s*$');

  bool get _isRtl =>
      language == 'ar' || language == 'he' ||
      language == 'fa' || language == 'ur';

  @override
  Widget build(BuildContext context) {
    final accent = const Color(0xFFD7B46A);
    final lines = <Widget>[];
    for (final raw in lyrics.split('\n')) {
      final line = raw.trim();
      if (line.isEmpty) {
        lines.add(const SizedBox(height: 8));
        continue;
      }
      final m = _sectionRe.firstMatch(line);
      if (m != null) {
        lines.add(Align(
          alignment: _isRtl ? Alignment.centerRight : Alignment.centerLeft,
          child: Container(
            margin: const EdgeInsets.only(top: 12, bottom: 4),
            padding:
                const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
            decoration: BoxDecoration(
              color: accent.withValues(alpha: 0.16),
              borderRadius: BorderRadius.circular(999),
            ),
            child: Text(
              m.group(1)!,
              style: TextStyle(
                fontSize: 11,
                letterSpacing: 1.6,
                fontWeight: FontWeight.w600,
                color: accent,
              ),
            ),
          ),
        ));
      } else {
        lines.add(Text(
          line,
          textAlign: _isRtl ? TextAlign.right : TextAlign.left,
          style: TextStyle(
            fontSize: _isRtl ? 17 : 15,
            height: _isRtl ? 1.9 : 1.6,
          ),
        ));
      }
    }
    return Directionality(
      textDirection: _isRtl ? TextDirection.rtl : TextDirection.ltr,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: lines,
      ),
    );
  }
}
