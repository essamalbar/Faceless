import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../l10n/l10n.dart';
import '../theme.dart';
import '../ui/brand.dart';
import '../ui/primitives.dart';
import '../widgets/paywall_dialog.dart';
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

  /// Non-null while the run is in the `analyzing` state (import flow).
  /// Drives the "Analyzing the song…" UI instead of a plain spinner.
  String? _analyzingStatus;

  @override
  void initState() {
    super.initState();
    _pollUntilReady();
  }

  Future<void> _pollUntilReady() async {
    // 150 polls × 2 s = 5 minutes — generous enough for cold-start +
    // yt-dlp download + Whisper transcription + 2 LLM calls (import path).
    // Normal (non-import) runs reach `awaiting_approval` in a few seconds
    // and exit the loop early, so they are unaffected.
    for (int i = 0; i < 150; i++) {
      try {
        final s = await widget.client.getSong(widget.runId);
        if (s.status == 'awaiting_approval') {
          final script = await widget.client.getSongScript(widget.runId);
          if (!mounted) return;
          setState(() {
            _script = script;
            _analyzingStatus = null;
            _busy = false;
          });
          return;
        }
        if (s.status == 'failed') {
          if (!mounted) return;
          setState(() {
            _error = s.lastError ?? context.l10n.approveAnalysisFailed;
            _analyzingStatus = null;
            _busy = false;
          });
          return;
        }
        // Show a richer "Analyzing…" state for import runs so the user
        // knows the app is working, not frozen.
        if (s.status == 'analyzing' && _analyzingStatus != s.status) {
          if (!mounted) return;
          setState(() => _analyzingStatus = s.status);
        }
      } catch (_) {
        // Keep polling — transient 404 while song.json hasn't been written
        // yet (normal during the early seconds of an import run).
      }
      await Future.delayed(const Duration(seconds: 2));
    }
    if (!mounted) return;
    setState(() {
      _error = context.l10n.approveTimedOut;
      _analyzingStatus = null;
      _busy = false;
    });
  }

  Future<void> _editLyrics(SongScript s) async {
    final ctrl = TextEditingController(text: s.lyrics);
    final saved = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(ctx.l10n.approveEditLyrics),
        content: SizedBox(
          width: 560,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                ctx.l10n.approveKeepSectionTags,
                style: const TextStyle(fontSize: 12),
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
              child: Text(ctx.l10n.commonCancel)),
          FilledButton(onPressed: () => Navigator.pop(ctx, true),
              child: Text(ctx.l10n.commonSave)),
        ],
      ),
    );
    if (saved != true || !mounted) return;
    if (ctrl.text.length > 4000) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(context.l10n.approveLyricsTooLong),
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

  /// Mirror of [_editLyrics] for the style prompt — same dialog shape,
  /// same save path (`/songs/{id}/edit`, style_prompt only).
  Future<void> _editStyle(SongScript s) async {
    final ctrl = TextEditingController(text: s.stylePrompt);
    final saved = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(ctx.l10n.qualityEditStyle),
        content: SizedBox(
          width: 560,
          child: TextField(
            controller: ctrl,
            maxLines: 8,
            style: const TextStyle(fontSize: 15, height: 1.6),
            decoration: const InputDecoration(
              border: OutlineInputBorder(),
              alignLabelWithHint: true,
            ),
          ),
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
    setState(() => _busy = true);
    try {
      await widget.client.editSong(widget.runId, stylePrompt: ctrl.text);
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

  /// Arabic quality: add full tashkeel to the draft lyrics so Suno's
  /// pronunciation is unambiguous. Server persists the result; we swap
  /// the returned lyrics into the displayed script.
  Future<void> _diacritize(SongScript s) async {
    final l10n = context.l10n;
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _busy = true);
    try {
      final lyrics = await widget.client.diacritizeSong(widget.runId);
      if (!mounted) return;
      setState(() {
        _script = SongScript(
          title: s.title,
          lyrics: lyrics,
          stylePrompt: s.stylePrompt,
          coverPrompt: s.coverPrompt,
          language: s.language,
          costCredits: s.costCredits,
          costUsd: s.costUsd,
          videoMode: s.videoMode,
        );
      });
      messenger.showSnackBar(
          SnackBar(content: Text(l10n.qualityDiacritizeDone)));
    } catch (e) {
      if (!mounted) return;
      messenger.showSnackBar(
          SnackBar(content: Text(l10n.qualityDiacritizeFailed('$e'))));
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
    } on InsufficientCreditsException catch (e) {
      // Out of credits — route to the paywall so the user gets a clear
      // "Subscribe / Top up" action instead of a silent dead button. The
      // draft is saved, so they can approve again after topping up.
      if (!mounted) return;
      setState(() => _approving = false);
      await PaywallDialog.show(context, balance: e.balance, required: e.required);
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
      // Import runs linger in `analyzing` for minutes — show richer feedback.
      final label = _analyzingStatus == 'analyzing'
          ? context.l10n.approveAnalyzing
          : context.l10n.approvePreparing;
      return Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          elevation: 0,
          scrolledUnderElevation: 0,
          title: Text(context.l10n.approveReviewDraft),
        ),
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const CircularProgressIndicator(color: FacelessTheme.accent),
              const SizedBox(height: 20),
              Text(
                label,
                textAlign: TextAlign.center,
                style: const TextStyle(color: FacelessTheme.textSecondary),
              ),
            ],
          ),
        ),
      );
    }
    if (_error != null && _script == null) {
      return Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          elevation: 0,
          scrolledUnderElevation: 0,
          title: Text(context.l10n.approveReviewDraft),
        ),
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
    final l10n = context.l10n;
    return Scaffold(
      backgroundColor: Colors.transparent,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
        title: Text(s.title, maxLines: 1, overflow: TextOverflow.ellipsis),
      ),
      body: Stack(children: [
        ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
          children: [
            _Reveal(index: 0, child: Eyebrow(l10n.approveReviewDraft)),
            const SizedBox(height: 16),
            _Reveal(
              index: 1,
              child: _SectionCard(
                title: l10n.approveLyricsSection,
                body: _LyricsPreview(
                  lyrics: s.lyrics,
                  language: s.language,
                ),
                actions: [
                  TextButton.icon(
                    icon: const Icon(Icons.edit_outlined),
                    label: Text(l10n.approveEdit),
                    onPressed: _busy ? null : () => _editLyrics(s),
                  ),
                  // Arabic quality: full-tashkeel pass, Arabic scripts only.
                  if (s.language == 'ar')
                    OutlinedButton(
                      onPressed: _busy ? null : () => _diacritize(s),
                      child: Text(l10n.qualityDiacritize),
                    ),
                  TextButton.icon(
                    icon: const Icon(Icons.refresh),
                    label: Text(l10n.approveReroll),
                    onPressed: _busy ? null : _regenLyrics,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 14),
            _Reveal(
              index: 2,
              child: _SectionCard(
                title: l10n.approveStyleSection,
                body: Text(
                  s.stylePrompt,
                  style: const TextStyle(
                    color: FacelessTheme.textSecondary,
                    fontSize: 14,
                    height: 1.5,
                  ),
                ),
                actions: [
                  TextButton.icon(
                    icon: const Icon(Icons.edit_outlined),
                    label: Text(l10n.approveEdit),
                    onPressed: _busy ? null : () => _editStyle(s),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 14),
            _Reveal(
              index: 3,
              child: _SectionCard(
                title: l10n.approveCoverPromptSection,
                body: Text(
                  s.coverPrompt,
                  style: const TextStyle(
                    color: FacelessTheme.textSecondary,
                    fontSize: 14,
                    height: 1.5,
                  ),
                ),
                actions: [
                  TextButton.icon(
                    icon: const Icon(Icons.refresh),
                    label: Text(l10n.approveReroll),
                    onPressed: _busy ? null : _regenCover,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),
            _Reveal(index: 4, child: const Hairline()),
            const SizedBox(height: 20),
            // Cost disclosure — the pay-gate figure. Container/typography are
            // restyled for the redesign; the l10n call, its arguments, and
            // the credits/USD values themselves are untouched.
            _Reveal(
              index: 5,
              child: GlassCard(
                accentEdge: true,
                padding: const EdgeInsets.all(18),
                child: Row(
                  children: [
                    const Icon(Icons.account_balance_wallet_outlined,
                        color: FacelessTheme.accent2),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        l10n.approveCost(
                          s.costCredits,
                          '\$${s.costUsd.toStringAsFixed(2)}',
                        ),
                        style: const TextStyle(
                          fontWeight: FontWeight.w700,
                          fontSize: 15,
                          color: FacelessTheme.textPrimary,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 20),
            // Approve/spend trigger — restyled as GradientButton, but the
            // enable/disable condition and the call to _approve() are
            // unchanged from the pre-redesign FilledButton.
            _Reveal(
              index: 6,
              child: Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      icon: const Icon(Icons.delete_outline),
                      label: Text(l10n.approveDiscard),
                      onPressed: _approving ? null : _discard,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: GradientButton(
                      label: l10n.approveApproveGenerate,
                      icon: Icons.check,
                      loading: _approving,
                      expand: true,
                      onPressed: _approving ? null : _approve,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        if (_busy)
          Positioned.fill(
            child: ColoredBox(
              color: Colors.black.withValues(alpha: 0.15),
              child: const Center(
                child: CircularProgressIndicator(color: FacelessTheme.accent),
              ),
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
  Widget build(BuildContext context) => GlassCard(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Eyebrow(title),
            const SizedBox(height: 12),
            body,
            if (actions != null) ...[
              const SizedBox(height: 10),
              // Wrap (not Row): the lyrics card can carry three actions
              // (Edit / تشكيل / Re-roll) which overflow a Row on phones.
              Align(
                alignment: AlignmentDirectional.centerEnd,
                child: Wrap(
                  spacing: 4,
                  runSpacing: 4,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: actions!,
                ),
              ),
            ],
          ],
        ),
      );
}


/// Lyrics renderer that pulls section tags ([Verse 1], [Chorus], etc.)
/// out into colored chip headers — matches the public share page so
/// users approve what they'll actually see published. Lines render in the
/// editorial serif ([FacelessTheme.display]) and fade in one-by-one — the
/// "lyric reveal" moment — via [_Reveal], which honors
/// `MediaQuery.disableAnimations`.
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
    final lines = <Widget>[];
    var lineIndex = 0;
    for (final raw in lyrics.split('\n')) {
      final line = raw.trim();
      if (line.isEmpty) {
        lines.add(const SizedBox(height: 8));
        continue;
      }
      final m = _sectionRe.firstMatch(line);
      if (m != null) {
        lines.add(_Reveal(
          index: lineIndex++,
          stepMs: 24,
          fadeMs: 480,
          translateY: 6,
          child: Align(
            alignment: _isRtl ? Alignment.centerRight : Alignment.centerLeft,
            child: Container(
              margin: const EdgeInsets.only(top: 12, bottom: 4),
              padding:
                  const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
              decoration: BoxDecoration(
                color: FacelessTheme.accent.withValues(alpha: 0.16),
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text(
                m.group(1)!,
                style: const TextStyle(
                  fontSize: 11,
                  letterSpacing: 1.6,
                  fontWeight: FontWeight.w600,
                  color: FacelessTheme.accent2,
                ),
              ),
            ),
          ),
        ));
      } else {
        lines.add(_Reveal(
          index: lineIndex++,
          stepMs: 24,
          fadeMs: 480,
          translateY: 6,
          child: Text(
            line,
            textAlign: _isRtl ? TextAlign.right : TextAlign.left,
            style: FacelessTheme.display(
              size: _isRtl ? 18 : 17,
              weight: FontWeight.w500,
              height: _isRtl ? 1.9 : 1.6,
              letterSpacing: 0,
              color: FacelessTheme.textPrimary,
              locale: _isRtl ? const Locale('ar') : null,
            ),
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

/// Fades [child] in on first build, offset later in the sequence for a
/// higher [index] — used both for the pay-gate screen's section entrance
/// and (with a shorter [stepMs]/[fadeMs]) the line-by-line lyric reveal.
/// Honors `MediaQuery.disableAnimations` (renders [child] instantly, with no
/// animation, when reduced motion is requested).
///
/// The TOTAL animation duration grows with [index] (rather than clamping the
/// `Interval` start against a fixed duration) so every item gets a full
/// [fadeMs] fade window — clamping just the start would squeeze a fixed
/// window for later items, so a long lyric (or a long beat list) would
/// visibly "pop" in near the end instead of fading. Items past the cap
/// start together (capped stagger) but still get the full fade.
class _Reveal extends StatelessWidget {
  final int index;
  final Widget child;
  final int stepMs;
  final int fadeMs;
  final double translateY;
  const _Reveal({
    required this.index,
    required this.child,
    this.stepMs = 50,
    this.fadeMs = 640,
    this.translateY = 14,
  });

  static const _maxIndex = 24;

  @override
  Widget build(BuildContext context) {
    final reduceMotion =
        MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    if (reduceMotion) return child;
    final startMs = index.clamp(0, _maxIndex) * stepMs;
    final totalMs = startMs + fadeMs;
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.0, end: 1.0),
      duration: Duration(milliseconds: totalMs),
      curve: Interval(startMs / totalMs, 1.0, curve: Curves.easeOutCubic),
      builder: (context, t, child) => Opacity(
        opacity: t,
        child: Transform.translate(
          offset: Offset(0, (1 - t) * translateY),
          child: child,
        ),
      ),
      child: child,
    );
  }
}
