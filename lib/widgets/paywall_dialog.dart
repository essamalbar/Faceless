import 'package:flutter/material.dart';

import '../l10n/l10n.dart';
import '../screens/billing_screen.dart';
import '../theme.dart';

class PaywallDialog extends StatelessWidget {
  final int balance;
  final int required;
  const PaywallDialog({super.key, required this.balance, required this.required});

  static Future<void> show(
    BuildContext context, {
    required int balance,
    required int required,
  }) {
    return showDialog(
      context: context,
      builder: (_) => PaywallDialog(balance: balance, required: required),
    );
  }

  @override
  Widget build(BuildContext context) {
    final missing = required - balance;
    return AlertDialog(
      icon: const Icon(Icons.monetization_on,
                       color: FacelessTheme.accent, size: 36),
      title: Text(context.l10n.paywallOutOfCredits),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            context.l10n.paywallNeedCredits(required, balance, missing),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          Text(
            context.l10n.paywallSavedNotice,
            textAlign: TextAlign.center,
            style: const TextStyle(
                color: FacelessTheme.textSecondary, fontSize: 13),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: Text(context.l10n.commonCancel),
        ),
        FilledButton.icon(
          icon: const Icon(Icons.shopping_cart),
          label: Text(context.l10n.paywallTopUp),
          onPressed: () {
            Navigator.of(context).pop();
            Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const BillingScreen()),
            );
          },
        ),
      ],
    );
  }
}
