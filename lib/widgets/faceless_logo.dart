import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme.dart';

/// The Faceless brand mark — a sparkle constellation (one large 4-point
/// spark + two smaller satellite sparks) rendered in dark on a gold
/// gradient disc. The 4-point sparkle (✦) is the universal symbol for
/// "AI magic" — used by Apple Intelligence, Gemini, ChatGPT, Midjourney —
/// and the multi-spark layout reads as "magic happening" rather than
/// just a single decorative star.
///
/// Used everywhere the brand needs to appear: AppBar leading, hero on the
/// home screen, login screen splash, run-detail header, PDF cover (via
/// equivalent fpdf2 drawing primitives in pipeline/pdf_export.py).
///
/// `size` is the outer diameter. `withBackground=false` strips the gold
/// disc and renders just the marks in [color], useful when the logo sits
/// on its own gold gradient already (e.g. monogram chips).
class FacelessLogo extends StatelessWidget {
  final double size;
  final bool withBackground;
  final Color color;
  const FacelessLogo({
    super.key,
    this.size = 32,
    this.withBackground = true,
    this.color = FacelessTheme.bg,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(
        painter: _FacelessLogoPainter(
          withBackground: withBackground,
          markColor: color,
        ),
      ),
    );
  }
}

class _FacelessLogoPainter extends CustomPainter {
  final bool withBackground;
  final Color markColor;
  _FacelessLogoPainter({
    required this.withBackground,
    required this.markColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;
    final cx = w / 2;
    final cy = h / 2;
    final r = math.min(w, h) / 2;

    if (withBackground) {
      // Gold gradient disc — anchors the mark when used on dark backgrounds.
      final discRect = Rect.fromCircle(center: Offset(cx, cy), radius: r);
      final discPaint = Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [FacelessTheme.accent, Color(0xFFB07F1F)],
        ).createShader(discRect);
      canvas.drawCircle(Offset(cx, cy), r, discPaint);
    }

    final markPaint = Paint()..color = markColor;

    // Sparkle constellation — one large hero sparkle slightly off-center,
    // plus two smaller satellites at opposing corners. Coordinates are
    // proportional to `r` so the layout is identical at every size.
    final hero = Offset(cx - r * 0.06, cy + r * 0.02);
    final sat1 = Offset(cx + r * 0.42, cy - r * 0.42);   // top-right
    final sat2 = Offset(cx + r * 0.45, cy + r * 0.40);   // bottom-right
    _drawSparkle(canvas, hero, r * 0.50, markPaint);
    _drawSparkle(canvas, sat1, r * 0.20, markPaint);
    _drawSparkle(canvas, sat2, r * 0.15, markPaint);
  }

  /// One 4-point sparkle — the AI-magic motif. Drawn as two crossed
  /// pinched diamonds (vertical + horizontal) so the points stay crisp
  /// at small sizes; a typical 5-point star anti-aliases badly under 16px.
  /// The `pinch` factor controls how thin the rays are — lower = more
  /// dramatic / pointier, higher = chunkier.
  void _drawSparkle(Canvas canvas, Offset c, double r, Paint p) {
    const pinch = 0.18;
    final w = r * pinch;
    final vert = Path()
      ..moveTo(c.dx, c.dy - r)
      ..lineTo(c.dx + w, c.dy)
      ..lineTo(c.dx, c.dy + r)
      ..lineTo(c.dx - w, c.dy)
      ..close();
    final horz = Path()
      ..moveTo(c.dx - r, c.dy)
      ..lineTo(c.dx, c.dy + w)
      ..lineTo(c.dx + r, c.dy)
      ..lineTo(c.dx, c.dy - w)
      ..close();
    canvas.drawPath(vert, p);
    canvas.drawPath(horz, p);
  }

  @override
  bool shouldRepaint(covariant _FacelessLogoPainter old) =>
      old.withBackground != withBackground || old.markColor != markColor;
}
