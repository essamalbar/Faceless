/// Shared brand UI widgets for the Faceless "dark glass + gradient" look:
/// a global mesh-gradient background, glassmorphic cards, gradient buttons,
/// gradient text, and small accent chips. Used across every screen.
library;

import 'dart:ui';
import 'package:flutter/material.dart';

import '../theme.dart';

/// Full-bleed mesh-gradient backdrop (deep base + soft violet/pink/cyan
/// glows). Wrapped around the whole app in main.dart so every screen sits
/// on it; individual scaffolds are transparent.
class MeshBackground extends StatelessWidget {
  final Widget child;
  const MeshBackground({super.key, required this.child});

  Widget _blob(Color c, double size) => Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          gradient: RadialGradient(
            colors: [c.withValues(alpha: 0.55), c.withValues(alpha: 0.0)],
          ),
        ),
      );

  @override
  Widget build(BuildContext context) {
    final w = MediaQuery.sizeOf(context).width;
    final s = (w * 0.9).clamp(360.0, 900.0);
    return DecoratedBox(
      decoration: const BoxDecoration(color: FacelessTheme.bg),
      child: Stack(
        fit: StackFit.expand,
        children: [
          Positioned(left: -s * 0.35, top: -s * 0.4, child: _blob(const Color(0xFF7C5CFF), s)),
          Positioned(right: -s * 0.4, top: -s * 0.55, child: _blob(const Color(0xFFFF5C9A), s * 0.9)),
          Positioned(right: -s * 0.3, bottom: -s * 0.4, child: _blob(const Color(0xFF54E6FF), s * 0.7)),
          Positioned(left: -s * 0.35, bottom: -s * 0.45, child: _blob(const Color(0xFFB14BF4), s * 0.8)),
          child,
        ],
      ),
    );
  }
}

/// Glassmorphic surface: translucent white + blur + hairline border.
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
    Widget card = ClipRRect(
      borderRadius: r,
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 18, sigmaY: 18),
        child: Container(
          padding: padding,
          decoration: BoxDecoration(
            color: tint ?? FacelessTheme.glass,
            borderRadius: r,
            border: Border.all(color: FacelessTheme.border),
          ),
          child: child,
        ),
      ),
    );
    if (onTap != null) {
      card = InkWell(borderRadius: r, onTap: onTap, child: card);
    }
    return card;
  }
}

/// Primary CTA — brand-gradient fill with a soft glow.
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
        else if (icon != null) ...[Icon(icon, size: 19, color: Colors.white)],
        if (!loading && icon != null) const SizedBox(width: 9),
        Text(label,
            style: const TextStyle(
                color: Colors.white, fontWeight: FontWeight.w600, fontSize: 15)),
      ],
    );
    return Opacity(
      opacity: disabled ? 0.55 : 1,
      child: DecoratedBox(
        decoration: BoxDecoration(
          gradient: FacelessTheme.brandGradient,
          borderRadius: BorderRadius.circular(13),
          boxShadow: disabled
              ? null
              : [
                  BoxShadow(
                    color: const Color(0xFF7C5CFF).withValues(alpha: 0.45),
                    blurRadius: 32,
                    offset: const Offset(0, 14),
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

/// Paints its text with the brand gradient (for headlines / accents).
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

/// Small glass pill (credits, status, tags). Optional leading gradient dot.
class BrandPill extends StatelessWidget {
  final String label;
  final IconData? icon;
  final bool dot;
  const BrandPill(this.label, {super.key, this.icon, this.dot = false});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 7),
      decoration: BoxDecoration(
        color: FacelessTheme.glassStrong,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: FacelessTheme.border),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (dot)
            Container(
              width: 7,
              height: 7,
              margin: const EdgeInsets.only(right: 7),
              decoration: const BoxDecoration(
                  gradient: FacelessTheme.brandGradient, shape: BoxShape.circle),
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

/// Deterministic gradient for a cover placeholder, seeded by a string
/// (so the same song always gets the same art). Keeps the music identity
/// even without a real cover image.
LinearGradient coverGradient(String seed) {
  const palettes = [
    [Color(0xFF7C5CFF), Color(0xFFFF5C9A)],
    [Color(0xFF5A3FD6), Color(0xFFC24BF4)],
    [Color(0xFF0E7C86), Color(0xFF54E6FF)],
    [Color(0xFFB14BF4), Color(0xFFFF5C9A)],
    [Color(0xFFC9852B), Color(0xFFFFC24B)],
    [Color(0xFF2A1E5C), Color(0xFF7C5CFF)],
  ];
  final h = seed.codeUnits.fold<int>(0, (a, b) => a + b);
  final p = palettes[h % palettes.length];
  return LinearGradient(
      begin: Alignment.topLeft, end: Alignment.bottomRight, colors: p);
}
