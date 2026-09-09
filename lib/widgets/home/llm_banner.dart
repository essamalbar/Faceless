/// Lyric-quality alarm banner — shown when the primary writing model
/// recently failed and lyrics degraded to the fallback provider. The check
/// itself (`_checkLlmStatus`) and the dismiss flag stay in
/// `_HomeScreenState`; this widget only renders the banner + forwards the
/// dismiss tap.
library;

import 'package:flutter/material.dart';

import '../../l10n/l10n.dart';
import '../../theme.dart';

class LlmBanner extends StatelessWidget {
  final VoidCallback onDismiss;
  const LlmBanner({super.key, required this.onDismiss});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: FacelessTheme.accent.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: FacelessTheme.borderAccent),
        ),
        child: Row(
          children: [
            const Icon(Icons.warning_amber_rounded,
                size: 18, color: FacelessTheme.accent),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                context.l10n.llmDegradedBanner,
                style: const TextStyle(
                    fontSize: 13, color: FacelessTheme.textPrimary),
              ),
            ),
            IconButton(
              icon: const Icon(Icons.close, size: 16),
              color: FacelessTheme.textSecondary,
              onPressed: onDismiss,
            ),
          ],
        ),
      ),
    );
  }
}
