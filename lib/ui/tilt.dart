/// Tactile 3D depth for the Obsidian & Champagne app: a card that tilts toward
/// the pointer in real perspective and catches a champagne glare, giving the
/// glass genuine thickness. Pointer-hover driven (web/desktop), with an
/// optional gentle idle sway for the one hero element so the depth reads on
/// touch devices too. Reduced motion renders it perfectly flat.
///
/// Hover-only by design — it never captures drags, so it can't fight a
/// surrounding scroll view. (Mobile gyro tilt is a follow-up that needs the
/// device-orientation permission flow.)
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';

class TiltCard extends StatefulWidget {
  final Widget child;

  /// Max tilt in degrees at the card's edge.
  final double maxTilt;

  /// Soft champagne light that follows the pointer.
  final bool glare;

  /// Gentle always-on 3D sway when not hovered — reserve for ONE hero element.
  final bool idle;

  const TiltCard({
    super.key,
    required this.child,
    this.maxTilt = 9,
    this.glare = true,
    this.idle = false,
  });

  @override
  State<TiltCard> createState() => _TiltCardState();
}

class _TiltCardState extends State<TiltCard> with SingleTickerProviderStateMixin {
  Offset _p = Offset.zero; // pointer position, each axis in -1..1 (0 = center)
  bool _hover = false;
  AnimationController? _idle;

  @override
  void initState() {
    super.initState();
    if (widget.idle) {
      _idle = AnimationController(
        vsync: this,
        duration: const Duration(seconds: 7),
      )..addListener(() {
          if (mounted && !_hover) setState(() {});
        });
    }
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final reduce = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    final idle = _idle;
    if (idle != null) {
      if (reduce) {
        if (idle.isAnimating) idle.stop();
      } else if (!idle.isAnimating) {
        idle.repeat();
      }
    }
  }

  @override
  void dispose() {
    _idle?.dispose();
    super.dispose();
  }

  void _set(Offset local, Size size) {
    if (size.width <= 0 || size.height <= 0) return;
    setState(() {
      _hover = true;
      _p = Offset(
        (local.dx / size.width - 0.5) * 2,
        (local.dy / size.height - 0.5) * 2,
      );
    });
  }

  void _reset() => setState(() {
        _hover = false;
        _p = Offset.zero;
      });

  @override
  Widget build(BuildContext context) {
    final reduce = MediaQuery.maybeOf(context)?.disableAnimations ?? false;

    Offset p = _p;
    if (!_hover && _idle != null && !reduce) {
      final t = _idle!.value * 2 * math.pi;
      p = Offset(math.sin(t) * 0.34, math.cos(t * 0.8) * 0.2); // gentle sway
    }

    final rx = reduce ? 0.0 : (-p.dy * widget.maxTilt) * math.pi / 180;
    final ry = reduce ? 0.0 : (p.dx * widget.maxTilt) * math.pi / 180;
    final m = Matrix4.identity()
      ..setEntry(3, 2, 0.0012) // perspective
      ..rotateX(rx)
      ..rotateY(ry);

    return MouseRegion(
      onHover: (e) {
        final box = context.findRenderObject() as RenderBox?;
        if (box != null) _set(box.globalToLocal(e.position), box.size);
      },
      onExit: (_) => _reset(),
      child: AnimatedContainer(
        // Smooth, weighted follow while hovering; a softer settle on exit.
        duration: Duration(milliseconds: _hover ? 110 : 320),
        curve: Curves.easeOut,
        transform: m,
        transformAlignment: Alignment.center,
        child: Stack(
          children: [
            widget.child,
            if (widget.glare && _hover && !reduce)
              Positioned.fill(
                child: IgnorePointer(
                  child: CustomPaint(painter: _GlarePainter(p)),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// A soft, warm champagne highlight centered near the pointer — light playing
/// on glass. Falls off well before the edges, so it reads inside a rounded
/// card without needing to clip to its exact radius.
class _GlarePainter extends CustomPainter {
  final Offset p;
  _GlarePainter(this.p);

  @override
  void paint(Canvas canvas, Size size) {
    if (size.width <= 0) return;
    final cx = (0.5 + p.dx * 0.45) * size.width;
    final cy = (0.5 + p.dy * 0.45) * size.height;
    final rect = Rect.fromCircle(
        center: Offset(cx, cy), radius: size.width * 0.45);
    final paint = Paint()
      ..blendMode = BlendMode.screen
      ..shader = const RadialGradient(
        colors: [Color(0x3DFFF6E0), Color(0x00FFF6E0)],
      ).createShader(rect);
    canvas.drawRect(Offset.zero & size, paint);
  }

  @override
  bool shouldRepaint(_GlarePainter o) => o.p != p;
}
