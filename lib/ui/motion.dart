/// Shared motion primitives for the Obsidian & Champagne app — entrance
/// reveals, press feedback, and the page transition. Kept in the shared layer
/// (like theme.dart / brand.dart) so screens inherit MOTION the way they
/// inherit tokens: a screen opts in by wrapping content in [Reveal] /
/// [revealStagger], every CTA gets press + sheen for free through
/// GradientButton, and navigation animates through the theme's
/// pageTransitionsTheme. All of it respects reduced motion.
///
/// The living-waveform signature lives in ui/primitives.dart (`LivingWaveform`)
/// — this file deliberately does NOT redefine it.
library;

import 'package:flutter/material.dart';

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
