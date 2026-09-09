/// Home screen top bar: wordmark, a champagne credits pill, and the
/// refresh/saved-voices/settings actions. All state (which run/song lists to
/// refetch, navigation) stays in `_HomeScreenState` — this widget only knows
/// how to render the bar and forward taps via callbacks.
library;

import 'package:flutter/material.dart';

import '../../api/client.dart';
import '../../api/settings.dart';
import '../../l10n/l10n.dart';
import '../../screens/billing_screen.dart';
import '../../theme.dart';
import '../../ui/brand.dart';
import '../faceless_logo.dart';

class HomeHeader extends StatelessWidget implements PreferredSizeWidget {
  /// Saved-voices is a song-mode concept only — irrelevant to video runs.
  final bool showSavedVoices;
  final VoidCallback onRefresh;
  final VoidCallback onSavedVoices;
  final VoidCallback onSettings;
  const HomeHeader({
    super.key,
    required this.showSavedVoices,
    required this.onRefresh,
    required this.onSavedVoices,
    required this.onSettings,
  });

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);

  @override
  Widget build(BuildContext context) {
    // NOTE: do NOT use `extendBodyBehindAppBar: true` on the Scaffold that
    // hosts this. With a transparent AppBar over the body, the first sliver
    // of the body can render BEHIND the AppBar, occluding these icons' hit
    // targets. Keep the body in its own band below.
    return AppBar(
      backgroundColor: Colors.transparent,
      elevation: 0,
      scrolledUnderElevation: 0,
      title: Row(
        children: [
          const FacelessLogo(size: 30),
          const SizedBox(width: 10),
          Text(
            context.l10n.appTitle,
            style: const TextStyle(
              fontWeight: FontWeight.w700,
              letterSpacing: 0.4,
              color: FacelessTheme.textPrimary,
            ),
          ),
        ],
      ),
      actions: [
        const Padding(
          padding: EdgeInsetsDirectional.only(end: 4),
          child: Center(child: _BalanceBadge()),
        ),
        IconButton(
          icon: const Icon(Icons.refresh),
          tooltip: context.l10n.homeRefresh,
          onPressed: onRefresh,
        ),
        if (showSavedVoices)
          IconButton(
            icon: const Icon(Icons.record_voice_over),
            tooltip: context.l10n.homeSavedVoices,
            onPressed: onSavedVoices,
          ),
        IconButton(
          icon: const Icon(Icons.settings),
          tooltip: context.l10n.homeSettings,
          onPressed: onSettings,
        ),
      ],
    );
  }
}

/// Credits pill — self-fetches the balance with its own short-lived
/// [FacelessApiClient] (unchanged from the pre-redesign `_BalanceBadge`; this
/// fetch already lived outside `_HomeScreenState` before the redesign, so it
/// stays that way here rather than being rewired into the screen's state).
class _BalanceBadge extends StatefulWidget {
  const _BalanceBadge();
  @override
  State<_BalanceBadge> createState() => _BalanceBadgeState();
}

class _BalanceBadgeState extends State<_BalanceBadge> {
  int? _balance;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    try {
      final b = await FacelessApiClient(FacelessSettings()).getBalance();
      if (mounted) setState(() => _balance = b.balance);
    } catch (_) {
      // Silent on error — non-critical UI element, don't crash the home screen.
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_balance == null) return const SizedBox.shrink();
    return GestureDetector(
      onTap: () async {
        await Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => const BillingScreen()),
        );
        // Refresh on return — user may have just topped up.
        _refresh();
      },
      child: BrandPill('$_balance', icon: Icons.auto_awesome),
    );
  }
}
