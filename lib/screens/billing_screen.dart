import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../api/settings.dart';
import '../l10n/l10n.dart';
import '../theme.dart';
import 'transactions_screen.dart';

/// Localized display name for a plan id. Unknown ids render raw.
String _planDisplayName(AppLocalizations l10n, String plan) => switch (plan) {
      'free' => l10n.billingPlanFree,
      'starter' => l10n.homePlanStarter,
      'creator' => l10n.homePlanCreator,
      'pro' => l10n.homePlanPro,
      _ => plan,
    };

class BillingScreen extends StatefulWidget {
  const BillingScreen({super.key});

  @override
  State<BillingScreen> createState() => _BillingScreenState();
}

class _BillingScreenState extends State<BillingScreen> {
  late final FacelessApiClient _api;
  PlanInfo? _plan;
  List<CreditTx> _txs = [];
  bool _loading = true;
  String? _error;

  // Subscription tiers — match the prices configured in Stripe.
  // 1 credit = 1 video clip. Pricing rework 2026-05-13.
  static List<(String, String, String, String)> _plans(AppLocalizations l10n) => [
        ('starter', l10n.homePlanStarter, l10n.billingPricePerMonth(r'$9'),
            l10n.landingCreditsPerMonth(12)),
        ('creator', l10n.homePlanCreator, l10n.billingPricePerMonth(r'$29'),
            l10n.landingCreditsPerMonth(60)),
        ('pro', l10n.homePlanPro, l10n.billingPricePerMonth(r'$79'),
            l10n.landingCreditsPerMonth(200)),
      ];

  @override
  void initState() {
    super.initState();
    _api = FacelessApiClient(FacelessSettings());
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final plan = await _api.getPlan();
      final txs = await _api.getTransactions(limit: 50);
      if (mounted) setState(() { _plan = plan; _txs = txs; _loading = false; });
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _subscribe(String plan) async {
    final base = Uri.base.toString();
    try {
      final url = await _api.createSubscriptionCheckout(
        plan: plan, successUrl: base, cancelUrl: base,
      );
      await launchUrl(Uri.parse(url), webOnlyWindowName: '_blank');
    } catch (e) {
      _toast(e.toString());
    }
  }

  Future<void> _portal() async {
    final base = Uri.base.toString();
    try {
      final url = await _api.createPortalSession(returnUrl: base);
      await launchUrl(Uri.parse(url), webOnlyWindowName: '_blank');
    } catch (e) {
      _toast(e.toString());
    }
  }

  void _toast(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.billingTitle),
        actions: [
          IconButton(
            icon: const Icon(Icons.receipt_long),
            tooltip: l10n.transactionsTitle,
            onPressed: () => Navigator.of(context).push(MaterialPageRoute(
              builder: (_) => TransactionsScreen(client: _api),
            )),
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: l10n.homeRefresh,
            onPressed: _loading ? null : _load,
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Text(_error!,
                                style: const TextStyle(color: FacelessTheme.danger),
                                textAlign: TextAlign.center),
                  ),
                )
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    if (_plan!.isPastDue) ...[
                      _PastDueBanner(onUpdateCard: _portal),
                      const SizedBox(height: 16),
                    ],
                    _BalanceCard(plan: _plan!),
                    const SizedBox(height: 24),
                    Text(l10n.billingSubscriptions,
                         style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    for (final p in _plans(l10n))
                      _PlanCard(
                        id: p.$1, title: p.$2, price: p.$3, credits: p.$4,
                        current: _plan!.plan == p.$1,
                        onSubscribe: () => _subscribe(p.$1),
                      ),
                    const SizedBox(height: 24),
                    if (_plan!.plan != 'free')
                      OutlinedButton.icon(
                        icon: const Icon(Icons.open_in_new),
                        label: Text(l10n.billingManageSubscription),
                        onPressed: _portal,
                      ),
                    const SizedBox(height: 24),
                    Text(l10n.billingRecentTransactions,
                         style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    if (_txs.isEmpty)
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        child: Text(
                          l10n.billingNoTransactions,
                          style: const TextStyle(
                              color: FacelessTheme.textSecondary),
                        ),
                      ),
                    for (final t in _txs) _TxRow(tx: t),
                  ],
                ),
    );
  }
}

/// Dunning banner — shown only when the profile is past_due (a renewal
/// payment failed). Wired to the Stripe billing portal so the user can
/// update their card. `_portal` lives on the screen State, so it is passed
/// in as a callback rather than reached from inside this widget.
class _PastDueBanner extends StatelessWidget {
  final VoidCallback onUpdateCard;
  const _PastDueBanner({required this.onUpdateCard});
  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: FacelessTheme.danger.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: FacelessTheme.danger),
      ),
      child: Row(
        children: [
          const Icon(Icons.warning_amber_rounded,
                     color: FacelessTheme.danger),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              l10n.billingPastDueWarning,
              style: const TextStyle(
                color: FacelessTheme.danger,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          const SizedBox(width: 8),
          FilledButton(
            onPressed: onUpdateCard,
            child: Text(l10n.billingUpdateCard),
          ),
        ],
      ),
    );
  }
}

class _BalanceCard extends StatelessWidget {
  final PlanInfo plan;
  const _BalanceCard({required this.plan});
  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: FacelessTheme.cardGradient(),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(l10n.billingBalance,
                   style:
                       const TextStyle(color: FacelessTheme.textSecondary)),
              const SizedBox(height: 4),
              Text(l10n.homeCreditsCount(plan.balance),
                   style: const TextStyle(
                     color: FacelessTheme.accent,
                     fontSize: 28, fontWeight: FontWeight.w700,
                   )),
              const SizedBox(height: 4),
              Text(l10n.billingPlanLabel(_planDisplayName(l10n, plan.plan)),
                   style: const TextStyle(color: FacelessTheme.textPrimary)),
              if (plan.currentPeriodEnd != null)
                Text(
                  plan.cancelAtPeriodEnd
                      ? l10n.billingCancelsOn(
                          plan.currentPeriodEnd!.substring(0, 10))
                      : l10n.billingRenewsOn(
                          plan.currentPeriodEnd!.substring(0, 10)),
                  style: TextStyle(
                    color: plan.cancelAtPeriodEnd
                        ? FacelessTheme.danger
                        : FacelessTheme.textSecondary,
                    fontSize: 12,
                    fontWeight: plan.cancelAtPeriodEnd
                        ? FontWeight.w600
                        : FontWeight.normal,
                  ),
                ),
            ],
          ),
          const Icon(Icons.monetization_on,
                     color: FacelessTheme.accent, size: 40),
        ],
      ),
    );
  }
}

class _PlanCard extends StatelessWidget {
  final String id, title, price, credits;
  final bool current;
  final VoidCallback onSubscribe;
  const _PlanCard({
    required this.id, required this.title, required this.price,
    required this.credits, required this.current, required this.onSubscribe,
  });
  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: current ? FacelessTheme.accent : Colors.transparent,
          width: 1.5,
        ),
      ),
      child: ListTile(
        title: Text('$title — $price'),
        subtitle: Text(credits),
        trailing: current
            ? Chip(
                label: Text(context.l10n.billingCurrentPlanChip),
                backgroundColor: FacelessTheme.surface2,
              )
            : FilledButton(
                onPressed: onSubscribe,
                child: Text(context.l10n.billingSubscribe),
              ),
      ),
    );
  }
}

class _TxRow extends StatelessWidget {
  final CreditTx tx;
  const _TxRow({required this.tx});
  @override
  Widget build(BuildContext context) {
    final positive = tx.amount > 0;
    return ListTile(
      dense: true,
      leading: Icon(
        positive ? Icons.add_circle_outline : Icons.remove_circle_outline,
        color: positive ? FacelessTheme.success : FacelessTheme.danger,
      ),
      title: Text(tx.description ?? tx.kind),
      subtitle: Text(tx.createdAt.substring(0, 16).replaceFirst('T', ' ')),
      trailing: Text(
        '${positive ? '+' : ''}${tx.amount}',
        style: TextStyle(
          color: positive ? FacelessTheme.success : FacelessTheme.danger,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
