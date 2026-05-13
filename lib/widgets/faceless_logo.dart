import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme.dart';

/// The Faceless brand mark — a stylized crescent moon with a small accent
/// star, rendered in gold on a circular gradient background.
///
/// Used everywhere the brand needs to appear: AppBar leading, hero on the
/// home screen, login screen splash, run-detail header, PDF cover (via
/// equivalent fpdf2 drawing primitives in pipeline/pdf_export.py).
///
/// `size` is the outer diameter. `withBackground=false` strips the gold
/// disc and renders just the mark in [color], useful when the logo sits
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

    // CRESCENT — drawn by subtracting a smaller circle (offset right) from
    // a slightly larger one (centered slightly left). The difference path
    // gives a clean, even-thickness moon shape that scales to any size.
    final moonOuterR = r * 0.55;
    final moonInnerR = r * 0.50;
    final moonOuterC = Offset(cx - r * 0.04, cy);
    final moonInnerC = Offset(cx + r * 0.10, cy - r * 0.02);

    final outerPath = Path()
      ..addOval(Rect.fromCircle(center: moonOuterC, radius: moonOuterR));
    final innerPath = Path()
      ..addOval(Rect.fromCircle(center: moonInnerC, radius: moonInnerR));
    final crescentPath = Path.combine(PathOperation.difference,
                                      outerPath, innerPath);
    final markPaint = Paint()..color = markColor;
    canvas.drawPath(crescentPath, markPaint);

    // ACCENT STAR — a 4-point starburst at the upper-right corner of the
    // crescent's opening. Drawn as two crossed diamonds for crispness at
    // small sizes (a typical 5-point star anti-aliases badly under 16px).
    final starC = Offset(cx + r * 0.40, cy - r * 0.45);
    final starR = r * 0.13;
    _drawStarBurst(canvas, starC, starR, markPaint);
  }

  void _drawStarBurst(Canvas canvas, Offset c, double r, Paint p) {
    // Vertical+horizontal diamond combined with a diagonal one = 4-pointed
    // sparkle. Tips pinched, body thin so it reads as a star not a flower.
    final inner = r * 0.30;
    final long = Path()
      ..moveTo(c.dx, c.dy - r)
      ..lineTo(c.dx + inner, c.dy)
      ..lineTo(c.dx, c.dy + r)
      ..lineTo(c.dx - inner, c.dy)
      ..close();
    final cross = Path()
      ..moveTo(c.dx - r, c.dy)
      ..lineTo(c.dx, c.dy + inner)
      ..lineTo(c.dx + r, c.dy)
      ..lineTo(c.dx, c.dy - inner)
      ..close();
    canvas.drawPath(long, p);
    canvas.drawPath(cross, p);
  }

  @override
  bool shouldRepaint(covariant _FacelessLogoPainter old) =>
      old.withBackground != withBackground || old.markColor != markColor;
}
