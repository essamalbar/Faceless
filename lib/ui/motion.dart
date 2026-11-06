/// Shared motion primitives for the Obsidian & Champagne app — entrance
/// reveals, press feedback, the page transition, and the living-waveform
/// signature. Kept in the shared layer (like theme.dart / brand.dart) so
/// screens inherit MOTION the same way they inherit tokens: a screen opts in
/// by wrapping content in [Reveal]/[revealStagger] or dropping in a
/// [LivingWaveform], and every CTA gets press + sheen for free through
/// GradientButton. All of it respects the platform's reduced-motion setting.
library;

import 'dart:math' as math;
import 'package:flutter/material.dart';

import '../theme.dart';

/// Fade + rise entrance, played once when the widget mounts. `delayMs` staggers
/// siblings; reduced motion shows the child immediately at rest.
class Reveal extends StatefulWidget {
  final Widget child;
  final int delayMs;
  final double offset;
  final Duration duration;
  const Reveal({
    super.key,
    required this.child,
    this.delayMs = 0,
    this.offset = 16,
    this.duration = const Duration(milliseconds: 520),
  });

  @override
  State<Reveal> createState() => _RevealState();
}

class _RevealState extends State<Reveal> with SingleTickerProviderStateMixin {
  late final AnimationController _c =
      AnimationController(vsync: this, duration: widget.duration);
  late final Animation<double> _a =
      CurvedAnimation(parent: _c, curve: Curves.easeOutCubic);
  bool _started = false;

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  void _maybeStart() {
    if (_started) return;
    _started = true;
    final reduce = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    if (reduce) {
      _c.value = 1;
      return;
    }
    if (widget.delayMs <= 0) {
      _c.forward();
    } else {
      Future.delayed(Duration(milliseconds: widget.delayMs), () {
        if (mounted) _c.forward();
      });
    }
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _maybeStart();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _a,
      builder: (context, child) => Opacity(
        opacity: _a.value.clamp(0.0, 1.0),
        child: Transform.translate(
          offset: Offset(0, (1 - _a.value) * widget.offset),
          child: child,
        ),
      ),
      child: widget.child,
    );
  }
}

/// Wrap a list of children so each one reveals a beat after the last — the
/// staggered entrance used at the top of a screen's scroll view.
List<Widget> revealStagger(
  List<Widget> children, {
  int startMs = 40,
  int stepMs = 68,
  double offset = 16,
}) {
  return [
    for (int i = 0; i < children.length; i++)
      Reveal(
        delayMs: startMs + i * stepMs,
        offset: offset,
        child: children[i],
      ),
  ];
}

/// Scale-down press feedback for any tappable surface. Shows the tap landed.
class Pressable extends StatefulWidget {
  final Widget child;
  final VoidCallback? onTap;
  final double scale;
  const Pressable({super.key, required this.child, this.onTap, this.scale = 0.96});

  @override
  State<Pressable> createState() => _PressableState();
}

class _PressableState extends State<Pressable> {
  bool _down = false;
  void _set(bool v) {
    if (widget.onTap == null) return;
    setState(() => _down = v);
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: widget.onTap,
      onTapDown: (_) => _set(true),
      onTapUp: (_) => _set(false),
      onTapCancel: () => _set(false),
      child: AnimatedScale(
        scale: _down ? widget.scale : 1.0,
        duration: const Duration(milliseconds: 140),
        curve: Curves.easeOut,
        child: widget.child,
      ),
    );
  }
}

/// The brand's living waveform: a row of champagne bars that breathe. `active`
/// drives a lively oscillation; otherwise the bars rest low. Draws on a Canvas
/// so a long bar count stays cheap. Static under reduced motion.
class LivingWaveform extends StatefulWidget {
  final int bars;
  final double seed;
  final bool active;
  final double height;
  const LivingWaveform({
    super.key,
    this.bars = 40,
    this.seed = 1.0,
    this.active = true,
    this.height = 72,
  });

  @override
  State<LivingWaveform> createState() => _LivingWaveformState();
}

class _LivingWaveformState extends State<LivingWaveform>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 1800));

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final reduce = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    if (reduce || !widget.active) {
      if (_c.isAnimating) _c.stop();
    } else if (!_c.isAnimating) {
      _c.repeat();
    }
  }

  @override
  void didUpdateWidget(covariant LivingWaveform old) {
    super.didUpdateWidget(old);
    final reduce = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    if (widget.active && !reduce && !_c.isAnimating) {
      _c.repeat();
    } else if ((!widget.active || reduce) && _c.isAnimating) {
      _c.stop();
    }
  }

  @override
  Widget build(BuildContext context) {
    return RepaintBoundary(
      child: SizedBox(
        height: widget.height,
        width: double.infinity,
        child: AnimatedBuilder(
          animation: _c,
          builder: (context, _) => CustomPaint(
            painter: _WavePainter(_c.value, widget.bars, widget.seed, widget.active),
          ),
        ),
      ),
    );
  }
}

class _WavePainter extends CustomPainter {
  final double t;
  final int bars;
  final double seed;
  final bool active;
  _WavePainter(this.t, this.bars, this.seed, this.active);

  @override
  void paint(Canvas canvas, Size size) {
    if (size.width <= 0) return;
    final gap = size.width / bars;
    final bw = (gap * 0.42).clamp(2.0, 11.0);
    for (int i = 0; i < bars; i++) {
      final x = i * gap + gap / 2;
      final base = 0.22 + 0.5 * math.sin(i * 0.5 + seed).abs();
      final mv =
          active ? (0.5 + 0.5 * math.sin(t * 2 * math.pi + i * 0.35)) : 0.18;
      final amp = base * mv;
      final bh = math.max(3.0, amp * size.height * 0.92);
      final y = (size.height - bh) / 2;
      final rect = RRect.fromRectAndRadius(
          Rect.fromLTWH(x - bw / 2, y, bw, bh), Radius.circular(bw / 2));
      final paint = Paint()
        ..isAntiAlias = true
        ..shader = const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [FacelessTheme.accent2, FacelessTheme.accentDeep],
        ).createShader(Rect.fromLTWH(x - bw / 2, y, bw, bh));
      canvas.drawRRect(rect, paint);
    }
  }

  @override
  bool shouldRepaint(_WavePainter o) => o.t != t || o.active != active;
}

/// App-wide page transition: a soft fade with a small upward settle — the same
/// easing the screens use for their own reveals, so navigation feels of a
/// piece. Wired into the theme's pageTransitionsTheme (theme.dart).
class FadeSettleTransitionBuilder extends PageTransitionsBuilder {
  const FadeSettleTransitionBuilder();

  @override
  Widget buildTransitions<T>(
    PageRoute<T> route,
    BuildContext context,
    Animation<double> animation,
    Animation<double> secondaryAnimation,
    Widget child,
  ) {
    final reduce = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    if (reduce) return child;
    final curved = CurvedAnimation(
      parent: animation,
      curve: Curves.easeOutCubic,
      reverseCurve: Curves.easeInCubic,
    );
    return FadeTransition(
      opacity: curved,
      child: SlideTransition(
        position: Tween<Offset>(begin: const Offset(0, 0.035), end: Offset.zero)
            .animate(curved),
        child: child,
      ),
    );
  }
}
