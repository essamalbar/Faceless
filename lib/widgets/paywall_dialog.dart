import 'package:flutter/material.dart';

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
      title: const Text('Out of credits'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'This video needs $required credits. You have $balance — '
            '$missing more to go. Top up to keep generating.',
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          const Text(
            'Your script and characters are saved. After topping up, '
            'tap Resume on this run to continue.',
            textAlign: TextAlign.center,
            style: TextStyle(color: FacelessTheme.textSecondary, fontSize: 13),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton.icon(
          icon: const Icon(Icons.shopping_cart),
          label: const Text('Top up'),
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
