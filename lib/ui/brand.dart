/// Shared brand UI widgets for the Faceless glassy dark-neon look: a
/// near-black backdrop lit by blurred pink/purple/cyan glow, frosted
/// translucent cards with bright glass edges, a pink→purple gradient primary
/// button, gradient accent text, and dark neon cover art. Used across every
/// screen. Widget NAMES are kept stable so screens inherit the look without
/// edits — only the rendering changed from the old light look.
library;

import 'dart:ui';
import 'package:flutter/material.dart';

import '../theme.dart';

/// Full-bleed near-black backdrop lit by soft pink/purple/cyan neon glows.
/// Wrapped around the whole app in main.dart so every screen sits on it;
/// individual scaffolds are transparent. The glows are RadialGradient fades
/// (no blur filter here — the frosted blur lives in GlassCard).
class MeshBackground extends StatelessWidget {
  final Widget child;
  const MeshBackground({super.key, required this.child});

  Widget _blob(Color c, double size, double alpha) => IgnorePointer(
        child: Container(
          width: size,
          height: size,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: RadialGradient(
              colors: [c.withValues(alpha: alpha), c.withValues(alpha: 0.0)],
            ),
          ),
        ),
      );

  @override
  Widget build(BuildContext context) {
    final w = MediaQuery.sizeOf(context).width;
    final s = (w * 0.95).clamp(360.0, 840.0);
    return DecoratedBox(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF0B0810), Color(0xFF140C1F), Color(0xFF0B0810)],
          stops: [0.0, 0.5, 1.0],
        ),
      ),
      child: Stack(
        fit: StackFit.expand,
        children: [
          Positioned(
              left: -s * 0.3, top: -s * 0.35,
              child: _blob(const Color(0xFFFF4D8D), s, 0.5)),
          Positioned(
              right: -s * 0.35, top: -s * 0.3,
              child: _blob(const Color(0xFFA25BFF), s * 0.98, 0.5)),
          Positioned(
              right: -s * 0.25, bottom: -s * 0.3,
              child: _blob(const Color(0xFF3FE0D0), s * 0.8, 0.32)),
          child,
        ],
      ),
    );
  }
}

/// Frosted translucent surface: dark glass fill + blur + a bright glass top
/// edge + hairline border + soft shadow. The "glass" over the neon glow.
class GlassCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final double radius;
  final VoidCallback? onTap;
  final Color? tint;
  const GlassCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(18),
    this.radius = 20,
    this.onTap,
    this.tint,
  });

  @override
  Widget build(BuildContext context) {
    final r = BorderRadius.circular(radius);
    Widget card = DecoratedBox(
      decoration: BoxDecoration(borderRadius: r, boxShadow: FacelessTheme.softShadow),
      child: ClipRRect(
        borderRadius: r,
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 22, sigmaY: 22),
          child: Container(
            padding: padding,
            decoration: BoxDecoration(
              // Bright top edge → glass sheen. A solid tint overrides it.
              color: tint,
              gradient: tint == null
                  ? LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [
                        Colors.white.withValues(alpha: 0.10),
                        FacelessTheme.glass,
                      ],
                    )
                  : null,
              borderRadius: r,
              border: Border.all(color: FacelessTheme.border),
            ),
            child: child,
          ),
        ),
      ),
    );
    if (onTap != null) {
      card = InkWell(borderRadius: r, onTap: onTap, child: card);
    }
    return card;
  }
}

/// Primary CTA — pink→purple gradient fill, white text, neon glow.
class GradientButton extends StatelessWidget {
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
  Widget build(BuildContext context) {
    final disabled = onPressed == null || loading;
    final child = Row(
      mainAxisSize: expand ? MainAxisSize.max : MainAxisSize.min,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        if (loading)
          const SizedBox(
              width: 18,
              height: 18,
              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
        else if (icon != null)
          Icon(icon, size: 19, color: Colors.white),
        if (!loading && icon != null) const SizedBox(width: 9),
        Text(label,
            style: const TextStyle(
                color: Colors.white, fontWeight: FontWeight.w600, fontSize: 15)),
      ],
    );
    return Opacity(
      opacity: disabled ? 0.5 : 1,
      child: DecoratedBox(
        decoration: BoxDecoration(
          gradient: FacelessTheme.brandGradient,
          borderRadius: BorderRadius.circular(13),
          border: Border.all(color: Colors.white.withValues(alpha: 0.20)),
          boxShadow: disabled
              ? null
              : [
                  BoxShadow(
                    color: FacelessTheme.accent.withValues(alpha: 0.40),
                    blurRadius: 24,
                    offset: const Offset(0, 10),
                  ),
                ],
        ),
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            borderRadius: BorderRadius.circular(13),
            onTap: disabled ? null : onPressed,
            child: Padding(padding: padding, child: child),
          ),
        ),
      ),
    );
  }
}

/// Paints text with the pink→purple brand gradient (accent headline words).
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

/// Small glass pill (credits, status, tags) with a hairline border. Optional
/// leading dot.
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
        color: FacelessTheme.glass,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: FacelessTheme.border),
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
          if (icon != null) ...[Icon(icon, size: 14, color: FacelessTheme.accent), const SizedBox(width: 6)],
          Text(label,
              style: const TextStyle(
                  fontSize: 13, fontWeight: FontWeight.w600, color: FacelessTheme.textPrimary)),
        ],
      ),
    );
  }
}

/// Deterministic DARK NEON gradient for a cover placeholder, seeded by a
/// string so the same song always gets the same art.
LinearGradient coverGradient(String seed) {
  const palettes = [
    [Color(0xFF3A2352), Color(0xFF7A2E6E)], // plum → magenta
    [Color(0xFF1F3A5C), Color(0xFF2E7A6E)], // deep blue → teal
    [Color(0xFF5C1F3A), Color(0xFFA2405B)], // wine → rose
    [Color(0xFF2B2352), Color(0xFF5A3AA6)], // indigo → violet
    [Color(0xFF5C3A1F), Color(0xFFA2762E)], // bronze → amber
    [Color(0xFF1F5C4A), Color(0xFF2EA27A)], // emerald → jade
  ];
  final h = seed.codeUnits.fold<int>(0, (a, b) => a + b);
  final p = palettes[h % palettes.length];
  return LinearGradient(
      begin: Alignment.topLeft, end: Alignment.bottomRight, colors: p);
}
