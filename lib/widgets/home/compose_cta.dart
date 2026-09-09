/// Primary "start a new song" call-to-action — the champagne-hairline
/// [GradientButton], full width, below the hero greeting. Wraps the same
/// `_openNewSong` action the old plain "New Song" button called.
library;

import 'package:flutter/material.dart';

import '../../l10n/l10n.dart';
import '../../ui/brand.dart';

class ComposeCta extends StatelessWidget {
  final VoidCallback onPressed;
  const ComposeCta({super.key, required this.onPressed});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 4),
      child: GradientButton(
        label: context.l10n.homeNewSong,
        icon: Icons.auto_awesome,
        expand: true,
        onPressed: onPressed,
      ),
    );
  }
}
