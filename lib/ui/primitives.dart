/// Shared luxe primitives for the Faceless obsidian + champagne redesign:
/// small editorial building blocks (eyebrow labels, serif headings with a
/// gradient accent word, hairline dividers, a "sound made visible" waveform,
/// status pills, artist monogram badges, and a step-progress list). Tasks
/// 4-8 compose these into full screens. Widget NAMES + constructor shapes
/// match the Task 3 brief exactly so downstream tasks can depend on them.
/// Mirrors docs/superpowers/specs/redesign-artboards/DirectionA-Home.dc.html
/// and DirectionA-Composing.dc.html.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../theme.dart';
import 'brand.dart';

/// Small uppercase label ("GOOD EVENING", "YOUR ARTISTS") — Manrope (Tajawal
/// for Arabic locales) at 10.5px with wide tracking, muted secondary color.
class Eyebrow extends StatelessWidget {
  final String text;
  const Eyebrow(this.text, {super.key});

  @override
  Widget build(BuildContext context) {
    final locale = Localizations.maybeLocaleOf(context);
    final isArabic = locale?.languageCode == 'ar';
    // GoogleFonts registers families under variant-suffixed internal names
    // (not the bare 'Manrope'/'Tajawal' string) — go through the same
    // GoogleFonts.<family>() call FacelessTheme.display() uses rather than
    // hardcoding fontFamily, or the text silently falls back to the system
    // font.
    final style = isArabic
        ? GoogleFonts.tajawal(
            fontSize: 10.5,
            fontWeight: FontWeight.w600,
            letterSpacing: 0.10 * 10.5,
            color: FacelessTheme.textSecondary,
          )
        : GoogleFonts.manrope(
            fontSize: 10.5,
            fontWeight: FontWeight.w600,
            letterSpacing: 0.30 * 10.5,
            color: FacelessTheme.textSecondary,
          );
    return Text(text.toUpperCase(), style: style);
  }
}

/// Editorial serif headline (Cormorant Garamond EN / Amiri AR) via
/// [FacelessTheme.display]. When [accentLast] is set, the final
/// whitespace-separated word is painted with the champagne gradient
/// ([GradientText]) instead of the plain text color, matching the "sing" /
/// "أغنيتك" accent word in the artboards.
class EditorialHeading extends StatelessWidget {
  final String text;
  final double size;
  final bool accentLast;
  final TextAlign? textAlign;
  const EditorialHeading(
    this.text, {
    super.key,
    this.size = 32,
    this.accentLast = false,
    this.textAlign,
  });

  @override
  Widget build(BuildContext context) {
    final locale = Localizations.maybeLocaleOf(context);
    final style = FacelessTheme.display(size: size, locale: locale);

    if (!accentLast) {
      return Text(text, style: style, textAlign: textAlign);
    }

    final words = text.trim().split(RegExp(r'\s+'));
    if (words.length <= 1) {
      return GradientText(text, style: style, align: textAlign);
    }
    final lead = words.sublist(0, words.length - 1).join(' ');
    final last = words.last;
    // `.left`/`.right` are PHYSICAL — resolve them against the ambient
    // Directionality before mapping to WrapAlignment, or the mapping is
    // backwards under RTL (e.g. `.right` must mean "start" in RTL, not
    // "end"). `.start`/`.end`/`.center` are already direction-relative and
    // pass through unchanged.
    final isRtl = Directionality.of(context) == TextDirection.rtl;
    final wrapAlignment = switch (textAlign) {
      null => WrapAlignment.start,
      TextAlign.center => WrapAlignment.center,
      TextAlign.start => WrapAlignment.start,
      TextAlign.end => WrapAlignment.end,
      TextAlign.left => isRtl ? WrapAlignment.end : WrapAlignment.start,
      TextAlign.right => isRtl ? WrapAlignment.start : WrapAlignment.end,
      TextAlign.justify => WrapAlignment.start,
    };
    return Wrap(
      alignment: wrapAlignment,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        Text('$lead ', style: style, textAlign: textAlign),
        GradientText(last, style: style, align: textAlign),
      ],
    );
  }
}

/// Thin 1px hairline divider using the warm neutral [FacelessTheme.border].
class Hairline extends StatelessWidget {
  const Hairline({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(height: 1, color: FacelessTheme.border);
  }
}

/// A row of thin bars painting "sound made visible" — the waveform motif
/// used on the home hero card and the composing screen. Each bar is a
/// [Container] keyed `ValueKey('wavebar_$i')` (UNIQUE per bar — a shared key
/// across Row siblings throws) with a champagne gradient fill and a
/// deterministic-but-varied height.
///
/// When [animate] is true, a single [AnimationController] drives a
/// staggered per-bar scaleY/opacity "pulse", mirroring the artboard's
/// `@keyframes pulse` on `.livewave span`. Honors
/// `MediaQuery.disableAnimations` — when reduced motion is requested the
/// controller never starts and bars render at their static height (same
/// pattern as [MeshBackground]).
class LivingWaveform extends StatefulWidget {
  final int bars;
  final bool animate;
  final double height;
  final Color? color;
  const LivingWaveform({
    super.key,
    this.bars = 18,
    this.animate = true,
    this.height = 40,
    this.color,
  });

  @override
  State<LivingWaveform> createState() => _LivingWaveformState();
}

class _LivingWaveformState extends State<LivingWaveform>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1500),
  );

  // Deterministic per-bar height fractions so the same bar count always
  // renders the same silhouette (no Random() flakiness in golden-ish diffs).
  static const _pattern = [
    0.40, 0.64, 0.90, 0.52, 1.00, 0.70, 0.44, 0.82, 0.58, 0.96,
    0.48, 0.76, 0.62, 0.88, 0.50, 0.72, 0.42, 0.66,
  ];

  double _heightFractionFor(int i) => _pattern[i % _pattern.length];

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final reduceMotion = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    final shouldAnimate = widget.animate && !reduceMotion;
    if (shouldAnimate) {
      if (!_controller.isAnimating) _controller.repeat(reverse: true);
    } else {
      if (_controller.isAnimating) _controller.stop();
    }
  }

  @override
  void didUpdateWidget(covariant LivingWaveform old) {
    super.didUpdateWidget(old);
    if (old.animate != widget.animate) {
      didChangeDependencies();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final reduceMotion = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    final animating = widget.animate && !reduceMotion;
    final topColor = widget.color ?? FacelessTheme.accent2;
    final bottomColor = widget.color ?? FacelessTheme.accentDeep;

    // Multiply against each color's own alpha (not replace it) so a caller
    // passing an already-translucent `color:` keeps that translucency — the
    // old `Opacity(pulse)` wrapper multiplied on top of whatever the bar
    // painted, it didn't override it.
    BoxDecoration decorationFor(double pulse) => BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              topColor.withValues(alpha: topColor.a * pulse),
              bottomColor.withValues(alpha: bottomColor.a * pulse),
            ],
          ),
          borderRadius: BorderRadius.circular(2),
        );

    Widget bar(int i) {
      final baseFraction = _heightFractionFor(i);
      final barHeight = widget.height * baseFraction;
      if (!animating) {
        return Container(
          key: ValueKey('wavebar_$i'),
          width: 2.5,
          height: barHeight,
          margin: const EdgeInsetsDirectional.only(end: 3),
          decoration: decorationFor(1.0),
        );
      }
      // Stagger: each bar's phase is offset around the shared controller.
      // The pulsing alpha is baked into the bar's own gradient color (no
      // per-bar Opacity widget / saveLayer) inside this AnimatedBuilder;
      // Transform.scale (a cheap transform layer) still drives the height
      // pulse. Key stays on the Container itself — the bar-count test finds
      // every widget whose key starts with 'wavebar_'.
      final phase = (i % 6) / 6.0;
      return AnimatedBuilder(
        animation: _controller,
        builder: (context, child) {
          final t = (_controller.value + phase) % 1.0;
          // Triangle wave 0.35..1.0, matching the artboard's scaleY(0.35..1).
          final wave = 1.0 - (2 * t - 1).abs();
          final scale = 0.35 + wave * 0.65;
          final alpha = 0.55 + wave * 0.45;
          return Transform.scale(
            scaleY: scale,
            alignment: Alignment.center,
            child: Container(
              key: ValueKey('wavebar_$i'),
              width: 2.5,
              height: barHeight,
              margin: const EdgeInsetsDirectional.only(end: 3),
              decoration: decorationFor(alpha),
            ),
          );
        },
      );
    }

    return SizedBox(
      height: widget.height,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [for (var i = 0; i < widget.bars; i++) bar(i)],
      ),
    );
  }
}

/// Status kinds a song/run can be in — mirrors the "Ready" / "Composing" /
/// "Review" rows on the home screen.
enum StatusKind { ready, composing, review }

/// Small status indicator: a leading dot + label for [StatusKind.ready] and
/// [StatusKind.composing] (sage dot / pulsing champagne dot respectively),
/// or a hollow champagne-hairline outline pill for [StatusKind.review] with
/// no dot (matches the artboard's "Review" chip). [StatusKind.composing]'s
/// dot pulses via a local [AnimationController], honoring
/// `MediaQuery.disableAnimations`.
class StatusPill extends StatefulWidget {
  final String label;
  final StatusKind kind;
  const StatusPill({super.key, required this.label, required this.kind});

  @override
  State<StatusPill> createState() => _StatusPillState();
}

class _StatusPillState extends State<StatusPill>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1400),
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final reduceMotion = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    final shouldAnimate = widget.kind == StatusKind.composing && !reduceMotion;
    if (shouldAnimate) {
      if (!_controller.isAnimating) _controller.repeat(reverse: true);
    } else {
      if (_controller.isAnimating) _controller.stop();
    }
  }

  @override
  void didUpdateWidget(covariant StatusPill old) {
    super.didUpdateWidget(old);
    if (old.kind != widget.kind) didChangeDependencies();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final reduceMotion = MediaQuery.maybeOf(context)?.disableAnimations ?? false;

    if (widget.kind == StatusKind.review) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: FacelessTheme.borderAccent),
        ),
        child: Text(
          widget.label,
          style: const TextStyle(
            fontSize: 10.5,
            letterSpacing: 0.3,
            color: FacelessTheme.accent2,
          ),
        ),
      );
    }

    final labelColor = widget.kind == StatusKind.composing
        ? FacelessTheme.accent
        : FacelessTheme.textSecondary;

    Widget dot;
    if (widget.kind == StatusKind.ready) {
      dot = Container(
        width: 6,
        height: 6,
        decoration: const BoxDecoration(
          color: FacelessTheme.success,
          shape: BoxShape.circle,
        ),
      );
    } else {
      // composing: pulsing champagne dot.
      final animating = !reduceMotion;
      final staticDot = Container(
        width: 6,
        height: 6,
        decoration: BoxDecoration(
          color: FacelessTheme.accent2,
          shape: BoxShape.circle,
          boxShadow: [
            BoxShadow(
              color: FacelessTheme.accent2.withValues(alpha: 0.8),
              blurRadius: 8,
            ),
          ],
        ),
      );
      dot = !animating
          ? staticDot
          : AnimatedBuilder(
              animation: _controller,
              builder: (context, child) {
                final v = 0.5 + _controller.value * 0.5;
                return Opacity(opacity: v, child: child);
              },
              child: staticDot,
            );
    }

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        dot,
        const SizedBox(width: 6),
        Text(
          widget.label,
          style: TextStyle(
            fontSize: 11,
            letterSpacing: 0.3,
            color: labelColor,
          ),
        ),
      ],
    );
  }
}

/// Circular gradient avatar with a serif monogram — the "artist coming
/// alive" motif on the home artists row and the composing screen's hero.
/// When [alive] is true, a soft pulsing champagne halo breathes behind the
/// circle (the artboard's `.halo` keyframe), honoring
/// `MediaQuery.disableAnimations`.
class ArtistBadge extends StatefulWidget {
  final String monogram;
  final Gradient? gradient;
  final bool alive;
  final double size;
  const ArtistBadge({
    super.key,
    required this.monogram,
    this.gradient,
    this.alive = false,
    this.size = 56,
  });

  @override
  State<ArtistBadge> createState() => _ArtistBadgeState();
}

class _ArtistBadgeState extends State<ArtistBadge>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 4000),
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final reduceMotion = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    final shouldAnimate = widget.alive && !reduceMotion;
    if (shouldAnimate) {
      if (!_controller.isAnimating) _controller.repeat(reverse: true);
    } else {
      if (_controller.isAnimating) _controller.stop();
    }
  }

  @override
  void didUpdateWidget(covariant ArtistBadge old) {
    super.didUpdateWidget(old);
    if (old.alive != widget.alive) didChangeDependencies();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final locale = Localizations.maybeLocaleOf(context);
    final reduceMotion = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    // Default to a jewel-tone gradient (never the solid champagne
    // brandGradient) — "champagne used sparingly" applies to artist avatars
    // too; every artist circle in the artboards is garnet/teal/bronze, with
    // champagne reserved for the border + halo on the alive one.
    final gradient = widget.gradient ?? coverGradient(widget.monogram);

    final circle = Container(
      width: widget.size,
      height: widget.size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: gradient,
        border: Border.all(
          color: widget.alive ? FacelessTheme.borderAccent : FacelessTheme.border,
        ),
        boxShadow: FacelessTheme.softShadow,
      ),
      alignment: Alignment.center,
      child: Text(
        widget.monogram,
        style: FacelessTheme.display(
          size: widget.size * 0.4,
          weight: FontWeight.w600,
          locale: locale,
        ),
      ),
    );

    if (!widget.alive) return circle;

    final haloStatic = Container(
      width: widget.size + 12,
      height: widget.size + 12,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: RadialGradient(
          colors: [
            FacelessTheme.accent2.withValues(alpha: 0.35),
            FacelessTheme.accent2.withValues(alpha: 0.0),
          ],
        ),
      ),
    );

    final halo = reduceMotion
        ? haloStatic
        : AnimatedBuilder(
            animation: _controller,
            builder: (context, child) {
              final scale = 1.0 + _controller.value * 0.08;
              final opacity = 0.55 + _controller.value * 0.35;
              return Opacity(
                opacity: opacity,
                child: Transform.scale(scale: scale, child: child),
              );
            },
            child: haloStatic,
          );

    // Keep the outer footprint exactly `size` (matching the non-alive
    // circle) so an alive badge doesn't grow 12px larger than its siblings
    // and shift a horizontal row (e.g. the home artists row) — let the
    // halo overflow the box via Clip.none instead of enlarging the box.
    return SizedBox(
      width: widget.size,
      height: widget.size,
      child: Stack(
        clipBehavior: Clip.none,
        alignment: Alignment.center,
        children: [halo, circle],
      ),
    );
  }
}

/// A single row in a [StepList] — mirrors "read idea" / "generate melody" /
/// "design cover" progress rows on the composing screen.
enum StepPhase { done, active, pending }

class StepItem {
  final String label;
  final StepPhase state;
  final int? percent;
  const StepItem({required this.label, required this.state, this.percent});
}

/// Vertical progress list: done rows show a filled champagne check circle,
/// the active row is highlighted with a halo dot + optional percent label,
/// pending rows show a hollow dimmed ring. RTL-aware via
/// [EdgeInsetsDirectional] so rows mirror correctly under Arabic
/// [Directionality].
class StepList extends StatelessWidget {
  final List<StepItem> items;
  const StepList(this.items, {super.key});

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [for (final item in items) _StepRow(item: item)],
    );
  }
}

class _StepRow extends StatefulWidget {
  final StepItem item;
  const _StepRow({required this.item});

  @override
  State<_StepRow> createState() => _StepRowState();
}

class _StepRowState extends State<_StepRow> with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 4000),
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final reduceMotion = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    final shouldAnimate = widget.item.state == StepPhase.active && !reduceMotion;
    if (shouldAnimate) {
      if (!_controller.isAnimating) _controller.repeat(reverse: true);
    } else {
      if (_controller.isAnimating) _controller.stop();
    }
  }

  @override
  void didUpdateWidget(covariant _StepRow old) {
    super.didUpdateWidget(old);
    if (old.item.state != widget.item.state) didChangeDependencies();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Widget _leading(bool reduceMotion) {
    switch (widget.item.state) {
      case StepPhase.done:
        return Container(
          width: 22,
          height: 22,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: FacelessTheme.accent.withValues(alpha: 0.14),
            border: Border.all(color: FacelessTheme.borderAccent),
          ),
          child: const Icon(Icons.check, size: 13, color: FacelessTheme.accent2),
        );
      case StepPhase.pending:
        return Container(
          width: 22,
          height: 22,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            border: Border.all(color: FacelessTheme.border),
          ),
        );
      case StepPhase.active:
        final dot = Container(
          width: 9,
          height: 9,
          decoration: const BoxDecoration(
            color: FacelessTheme.accent2,
            shape: BoxShape.circle,
          ),
        );
        final haloStatic = Container(
          width: 22,
          height: 22,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: RadialGradient(colors: [
              FacelessTheme.accent2.withValues(alpha: 0.5),
              FacelessTheme.accent2.withValues(alpha: 0.0),
            ]),
          ),
        );
        final halo = reduceMotion
            ? haloStatic
            : AnimatedBuilder(
                animation: _controller,
                builder: (context, child) {
                  final scale = 1.0 + _controller.value * 0.08;
                  final opacity = 0.55 + _controller.value * 0.35;
                  return Opacity(
                      opacity: opacity,
                      child: Transform.scale(scale: scale, child: child));
                },
                child: haloStatic,
              );
        return SizedBox(
          width: 22,
          height: 22,
          child: Stack(alignment: Alignment.center, children: [halo, dot]),
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    final reduceMotion = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    final item = widget.item;
    final isActive = item.state == StepPhase.active;
    final isPending = item.state == StepPhase.pending;

    final labelColor = switch (item.state) {
      StepPhase.done => FacelessTheme.faint,
      StepPhase.pending => FacelessTheme.textSecondary,
      StepPhase.active => FacelessTheme.textPrimary,
    };
    final labelWeight = isActive ? FontWeight.w500 : FontWeight.w400;

    Widget row = Row(
      children: [
        _leading(reduceMotion),
        const SizedBox(width: 13),
        Expanded(
          child: Text(
            item.label,
            style: TextStyle(
              fontSize: isActive ? 15 : 14.5,
              fontWeight: labelWeight,
              color: labelColor,
            ),
          ),
        ),
        if (isActive && item.percent != null)
          Padding(
            padding: const EdgeInsetsDirectional.only(start: 8),
            child: Text(
              '${item.percent}%',
              style: const TextStyle(fontSize: 12, color: FacelessTheme.accent),
            ),
          ),
      ],
    );

    if (isActive) {
      row = Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
        margin: const EdgeInsets.symmetric(vertical: 4),
        decoration: BoxDecoration(
          color: FacelessTheme.accent.withValues(alpha: 0.06),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: FacelessTheme.borderAccent),
        ),
        child: row,
      );
    } else {
      row = Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 12),
        child: row,
      );
    }

    if (isPending) {
      row = Opacity(opacity: 0.5, child: row);
    }

    return row;
  }
}
