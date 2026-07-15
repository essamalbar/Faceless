/// Shared brand UI widgets for the Faceless light look: a soft pastel
/// gradient background, frosted white cards, a charcoal primary button,
/// green accent text, and pastel cover art. Used across every screen.
library;

import 'dart:ui';
import 'package:flutter/material.dart';

import '../theme.dart';

/// Full-bleed soft pastel backdrop (warm cream → cool lavender → light) with
/// a couple of gentle glows. Wrapped around the whole app in main.dart so
/// every screen sits on it; individual scaffolds are transparent.
class MeshBackground extends StatelessWidget {
  final Widget child;
  const MeshBackground({super.key, required this.child});

  Widget _blob(Color c, double size) => IgnorePointer(
        child: Container(
          width: size,
          height: size,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: RadialGradient(
              colors: [c.withValues(alpha: 0.9), c.withValues(alpha: 0.0)],
            ),
          ),
        ),
      );

  @override
  Widget build(BuildContext context) {
    final w = MediaQuery.sizeOf(context).width;
    final s = (w * 0.9).clamp(360.0, 820.0);
    return DecoratedBox(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFFFBF6EE), Color(0xFFF2EFF7), Color(0xFFE9EBF2)],
          stops: [0.0, 0.5, 1.0],
        ),
      ),
      child: Stack(
        fit: StackFit.expand,
        children: [
          Positioned(left: -s * 0.3, top: -s * 0.35, child: _blob(const Color(0xFFF8ECD7), s)),
          Positioned(right: -s * 0.35, top: -s * 0.4, child: _blob(const Color(0xFFEBE7F7), s * 0.95)),
          Positioned(right: -s * 0.25, bottom: -s * 0.35, child: _blob(const Color(0xFFE4EEF0), s * 0.8)),
          child,
        ],
      ),
    );
  }
}

/// Frosted-white surface: translucent white + blur + hairline border + soft
/// shadow. The "glass" over the pastel background.
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
              color: tint ?? FacelessTheme.glass,
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

/// Primary CTA — charcoal ink fill with white text and a soft shadow.
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
          color: FacelessTheme.ink,
          borderRadius: BorderRadius.circular(13),
          boxShadow: disabled
              ? null
              : [
                  BoxShadow(
                    color: FacelessTheme.ink.withValues(alpha: 0.28),
                    blurRadius: 24,
                    offset: const Offset(0, 12),
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

/// Paints text with the green→teal brand gradient (accent headline words).
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

/// Small white pill (credits, status, tags) with a soft shadow. Optional
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
        color: Colors.white,
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

/// Deterministic SOFT PASTEL gradient for a cover placeholder, seeded by a
/// string so the same song always gets the same tasteful art.
LinearGradient coverGradient(String seed) {
  const palettes = [
    [Color(0xFFE7E1F4), Color(0xFFDCEBE6)], // lavender → mint
    [Color(0xFFF3E7D3), Color(0xFFF0D9DE)], // cream → blush
    [Color(0xFFDCEBE6), Color(0xFFD6E6F0)], // mint → sky
    [Color(0xFFEDE3F5), Color(0xFFF3E7D3)], // lilac → cream
    [Color(0xFFF0D9DE), Color(0xFFE7E1F4)], // blush → lavender
    [Color(0xFFD6E6F0), Color(0xFFDDEFE4)], // sky → mint
  ];
  final h = seed.codeUnits.fold<int>(0, (a, b) => a + b);
  final p = palettes[h % palettes.length];
  return LinearGradient(
      begin: Alignment.topLeft, end: Alignment.bottomRight, colors: p);
}
