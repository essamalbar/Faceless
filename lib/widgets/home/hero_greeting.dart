/// Editorial hero above the song list — an eyebrow + serif heading, purely
/// presentational (no data, no callbacks). Mirrors the artboard's
/// "Good evening / What will your artist sing tonight?" moment.
library;

import 'package:flutter/material.dart';

import '../../l10n/l10n.dart';
import '../../ui/primitives.dart';

class HeroGreeting extends StatelessWidget {
  const HeroGreeting({super.key});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 18, 16, 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Eyebrow(context.l10n.homeGreetingEyebrow),
          const SizedBox(height: 12),
          EditorialHeading(
            context.l10n.homeHeroHeading,
            size: 30,
            accentLast: true,
          ),
        ],
      ),
    );
  }
}
