/// Shared brand UI widgets for the Faceless obsidian + champagne luxury
/// look: a warm near-black backdrop lit by a soft champagne wash from the
/// top and a slow jade breath at the base, frosted translucent glass cards
/// with warm hairline edges, a dark-ground champagne-hairline primary
/// button, champagne gradient accent text, and jewel-tone cover art. Used
/// across every screen. Widget NAMES are kept stable so screens inherit the
/// look without edits — only the rendering changed from the old dark-neon
/// look. Mirrors docs/superpowers/specs/redesign-artboards/DirectionA-Home.dc.html.
library;

import 'dart:ui';
import 'package:flutter/material.dart';

import '../theme.dart';
import 'motion.dart';

/// Full-bleed obsidian backdrop: a vertical near-black gradient lit by a
/// soft champagne wash from the top and a cool jade/teal breath rising from
/// the base. Wrapped around the whole app in main.dart's MaterialApp.builder
/// so every screen sits on it; individual scaffolds are transparent. The
/// wash layer is IgnorePointer-wrapped so it never steals hit-testing from
/// `child`; the washes gently "breathe" unless the platform requests
/// reduced motion, in which case they render at a static intensity.
///
/// TEST NOTE: the breathe animation runs an infinite repeating
/// AnimationController. A widget test that pumps something built through
/// this widget (e.g. the real `FacelessApp`, or any screen wrapped in
/// `MeshBackground` directly) must call `tester.pump(duration)` rather than
/// `tester.pumpAndSettle()` — pumpAndSettle waits for the frame schedule to
/// go idle and will time out against an infinite ticker. To exercise the
/// static (non-animating) path instead, wrap the pumped widget in
/// `MediaQuery(data: MediaQueryData(disableAnimations: true), child: ...)`.
class MeshBackground extends StatefulWidget {
  final Widget child;
  const MeshBackground({super.key, required this.child});

  @override
  State<MeshBackground> createState() => _MeshBackgroundState();
}

class _MeshBackgroundState extends State<MeshBackground>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 4200),
  );

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Widget _wash(Alignment align, Color color, double size, double alpha) {
    return Align(
      alignment: align,
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          gradient: RadialGradient(
            colors: [color.withValues(alpha: alpha), color.withValues(alpha: 0.0)],
          ),
        ),
      ),
    );
  }

  Widget _washes(double breathe, double topSize, double baseSize) => Stack(
        fit: StackFit.expand,
        children: [
          // Warm champagne wash from the top — a wide ellipse, per the artboard.
          _wash(const Alignment(0, -1.15), FacelessTheme.accent, topSize, 0.10 * breathe),
          // Cool jade/teal breath rising from the base.
          _wash(const Alignment(-0.6, 1.2), const Color(0xFF2E7A6E), baseSize, 0.14 * breathe),
        ],
      );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Start/stop the ticker here (not in build) — didChangeDependencies
    // re-runs exactly when an inherited dependency (MediaQuery) changes,
    // which is when disableAnimations can flip.
    final reduceMotion = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    if (reduceMotion) {
      if (_controller.isAnimating) _controller.stop();
    } else if (!_controller.isAnimating) {
      _controller.repeat(reverse: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final reduceMotion = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    // Scale the washes to the viewport so the top wash reads as a wide
    // ellipse (per the artboard) rather than a fixed-size spot on wide web.
    final w = MediaQuery.sizeOf(context).width;
    final topSize = (w * 1.9).clamp(700.0, 1600.0);
    final baseSize = (w * 1.4).clamp(560.0, 1100.0);
    return DecoratedBox(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [FacelessTheme.bg, FacelessTheme.bgDeep],
        ),
      ),
      child: Stack(
        fit: StackFit.expand,
        children: [
          // RepaintBoundary isolates the continuously-repainting breathe
          // animation into its own layer so it doesn't invalidate/repaint
          // `widget.child` (the rest of the app) on every tick.
          RepaintBoundary(
            child: IgnorePointer(
              child: reduceMotion
                  ? _washes(1.0, topSize, baseSize)
                  : AnimatedBuilder(
                      animation: _controller,
                      builder: (context, _) =>
                          _washes(0.65 + _controller.value * 0.35, topSize, baseSize),
                    ),
            ),
          ),
          widget.child,
        ],
      ),
    );
  }
}

/// Frosted translucent surface: dark glass fill + a single blur layer + a
/// warm hairline border + soft shadow. The "glass" over the ambient wash.
/// Set [accentEdge] for a champagne hairline instead of the neutral one
/// (e.g. the "in progress" row on the home screen).
class GlassCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final double radius;
  final VoidCallback? onTap;
  final Color? tint;
  final bool accentEdge;
  const GlassCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(18),
    this.radius = 20,
    this.onTap,
    this.tint,
    this.accentEdge = false,
  });

  @override
  Widget build(BuildContext context) {
    final r = BorderRadius.circular(radius);
    Widget card = DecoratedBox(
      decoration: BoxDecoration(borderRadius: r, boxShadow: FacelessTheme.softShadow),
      child: ClipRRect(
        borderRadius: r,
        // Single BackdropFilter layer — kept cheap on Flutter web.
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 17, sigmaY: 17),
          child: Container(
            padding: padding,
            decoration: BoxDecoration(
              // A faint top sheen over the glass fill. A solid tint overrides it.
              color: tint,
              gradient: tint == null
                  ? LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [
                        Colors.white.withValues(alpha: 0.05),
                        FacelessTheme.glass,
                      ],
                    )
                  : null,
              borderRadius: r,
              border: Border.all(
                color: accentEdge ? FacelessTheme.borderAccent : FacelessTheme.border,
              ),
            ),
            child: child,
          ),
        ),
      ),
    );
    if (onTap != null) {
      // Scale-down press feedback reads more "luxury" than a Material ripple.
      card = Pressable(onTap: onTap, scale: 0.975, child: card);
    }
    return card;
  }
}

/// Primary CTA — a dark ground with a faint champagne wash (NOT a solid gold
/// fill), a champagne hairline border, a champagne label, and a subtle inner
/// sheen along the top edge.
class GradientButton extends StatefulWidget {
  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool loading;
  final bool expand;
  final EdgeInsetsGeometry padding;
  const GradientButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.loading = false,
    this.expand = false,
    this.padding = const EdgeInsets.symmetric(horizontal: 22, vertical: 15),
  });

  @override
  State<GradientButton> createState() => _GradientButtonState();
}

class _GradientButtonState extends State<GradientButton>
    with SingleTickerProviderStateMixin {
  // A champagne sheen that sweeps the CTA ONCE when it becomes active — a
  // brand flourish on appear, not a constant shimmer. A one-time forward (not
  // repeat) keeps it off the infinite-ticker path that would hang pumpAndSettle
  // in widget tests (see the MeshBackground test note). Created eagerly in
  // initState (NOT a lazy `late final` initializer): a disabled button never
  // touches it in build/_syncSheen, so a lazy field would first construct it
  // inside dispose(), which throws.
  late final AnimationController _sheen;
  bool _down = false;
  bool _sheened = false;

  bool get _disabled => widget.onPressed == null || widget.loading;

  @override
  void initState() {
    super.initState();
    _sheen = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 1500));
  }

  void _syncSheen() {
    final reduce = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    if (!_disabled && !reduce && !_sheened) {
      _sheened = true;
      _sheen.forward(from: 0);
    }
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _syncSheen();
  }

  @override
  void didUpdateWidget(covariant GradientButton old) {
    super.didUpdateWidget(old);
    _syncSheen();
  }

  @override
  void dispose() {
    _sheen.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final disabled = _disabled;
    final radius = BorderRadius.circular(13);
    final child = Row(
      mainAxisSize: widget.expand ? MainAxisSize.max : MainAxisSize.min,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        if (widget.loading)
          const SizedBox(
              width: 18,
              height: 18,
              child: CircularProgressIndicator(
                  strokeWidth: 2, color: FacelessTheme.accent2))
        else if (widget.icon != null)
          Icon(widget.icon, size: 19, color: FacelessTheme.accent2),
        if (!widget.loading && widget.icon != null) const SizedBox(width: 9),
        Text(widget.label,
            style: const TextStyle(
                color: FacelessTheme.accent2,
                fontWeight: FontWeight.w600,
                fontSize: 15)),
      ],
    );
    return Opacity(
      opacity: disabled ? 0.5 : 1,
      child: Semantics(
        button: true,
        enabled: !disabled,
        child: AnimatedScale(
          scale: _down ? 0.97 : 1.0,
          duration: const Duration(milliseconds: 130),
          curve: Curves.easeOut,
          child: Container(
            decoration: BoxDecoration(
              // Dark ground lit by a faint champagne wash top-to-bottom.
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  FacelessTheme.accent.withValues(alpha: 0.15),
                  FacelessTheme.accent.withValues(alpha: 0.045),
                ],
              ),
              borderRadius: radius,
              border: Border.all(color: FacelessTheme.borderAccent),
              boxShadow: disabled
                  ? null
                  : [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.40),
                        blurRadius: 24,
                        offset: const Offset(0, 10),
                      ),
                    ],
            ),
            // Subtle inner sheen along the top edge — an outer BoxShadow can't
            // fake an inset highlight, so this is a fading gradient overlay.
            foregroundDecoration: BoxDecoration(
              borderRadius: radius,
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Colors.white.withValues(alpha: 0.06), Colors.transparent],
                stops: const [0.0, 0.22],
              ),
            ),
            child: Material(
              color: Colors.transparent,
              child: InkWell(
                borderRadius: radius,
                onTap: disabled ? null : widget.onPressed,
                // Only when enabled — an InkWell with ANY non-null callback
                // counts as interactive, which would make a disabled button
                // report enabled semantics.
                onHighlightChanged:
                    disabled ? null : (v) => setState(() => _down = v),
                child: ClipRRect(
                  borderRadius: radius,
                  child: Stack(
                    children: [
                      Padding(padding: widget.padding, child: child),
                      if (!disabled)
                        Positioned.fill(
                          child: IgnorePointer(
                            child: AnimatedBuilder(
                              animation: _sheen,
                              builder: (context, _) => CustomPaint(
                                painter: _SheenPainter(_sheen.value),
                              ),
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// A soft champagne light band that crosses the button briefly once per cycle,
/// then rests off-screen — sparing, not a constant shimmer.
class _SheenPainter extends CustomPainter {
  final double t;
  _SheenPainter(this.t);

  @override
  void paint(Canvas canvas, Size size) {
    if (size.width <= 0) return;
    // A short settle, then one sweep across and off.
    final double phase = t < 0.3 ? -0.5 : (t - 0.3) / 0.7 * 1.7 - 0.5;
    final x = phase * size.width;
    final bandW = size.width * 0.34;
    final rect = Rect.fromLTWH(x - bandW / 2, 0, bandW, size.height);
    final paint = Paint()
      ..shader = LinearGradient(
        begin: Alignment.centerLeft,
        end: Alignment.centerRight,
        colors: [
          Colors.transparent,
          Colors.white.withValues(alpha: 0.12),
          Colors.transparent,
        ],
      ).createShader(rect);
    canvas.drawRect(rect, paint);
  }

  @override
  bool shouldRepaint(_SheenPainter o) => o.t != t;
}

/// Paints text with the champagne brand gradient (accent headline words).
class GradientText extends StatelessWidget {
  final String text;
  final TextStyle style;
  final TextAlign? align;
  const GradientText(this.text, {super.key, required this.style, this.align});

  @override
  Widget build(BuildContext context) {
    return ShaderMask(
      shaderCallback: (b) => FacelessTheme.brandGradient.createShader(b),
      blendMode: BlendMode.srcIn,
      child: Text(text, textAlign: align, style: style.copyWith(color: Colors.white)),
    );
  }
}

/// Small glass pill (credits, status, tags) with a champagne hairline
/// border. Optional leading dot.
class BrandPill extends StatelessWidget {
  final String label;
  final IconData? icon;
  final bool dot;
  final Color? dotColor;
  const BrandPill(this.label, {super.key, this.icon, this.dot = false, this.dotColor});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
        color: FacelessTheme.accent.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: FacelessTheme.borderAccent),
        boxShadow: FacelessTheme.softShadow,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (dot)
            Container(
              width: 8,
              height: 8,
              margin: const EdgeInsetsDirectional.only(end: 8),
              decoration: BoxDecoration(
                  color: dotColor ?? FacelessTheme.accent, shape: BoxShape.circle),
            ),
          if (icon != null) ...[Icon(icon, size: 14, color: FacelessTheme.accent2), const SizedBox(width: 6)],
          Text(label,
              style: const TextStyle(
                  fontSize: 13, fontWeight: FontWeight.w600, color: FacelessTheme.textPrimary)),
        ],
      ),
    );
  }
}

/// Deterministic jewel-tone gradient for a cover placeholder, seeded by a
/// string so the same song/artist always gets the same art. Palette is the
/// jewel set only (teal, bronze, garnet, emerald) — no violet/plum/indigo/pink.
LinearGradient coverGradient(String seed) {
  const palettes = [
    [Color(0xFF233A44), Color(0xFF2E7A6E)], // teal
    [Color(0xFF3E2E1C), Color(0xFFA0762E)], // bronze
    [Color(0xFF3A1E1C), Color(0xFF7A3A2E)], // garnet
    [Color(0xFF1F3A30), Color(0xFF2E7A5C)], // emerald
  ];
  final h = seed.codeUnits.fold<int>(0, (a, b) => a + b);
  final p = palettes[h % palettes.length];
  return LinearGradient(
      begin: Alignment.topLeft, end: Alignment.bottomRight, colors: p);
}
