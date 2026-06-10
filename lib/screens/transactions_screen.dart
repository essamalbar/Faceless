import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../theme.dart';

/// Recent credit-ledger transactions for the current user. Powered
/// by GET /billing/transactions (endpoint already existed; this
/// screen is purely the UI surface).
class TransactionsScreen extends StatefulWidget {
  final FacelessApiClient client;
  const TransactionsScreen({super.key, required this.client});

  @override
  State<TransactionsScreen> createState() => _TransactionsScreenState();
}

class _TransactionsScreenState extends State<TransactionsScreen> {
  late Future<List<CreditTx>> _future;

  @override
  void initState() {
    super.initState();
    _future = widget.client.getTransactions(limit: 100);
  }

  Future<void> _refresh() async {
    setState(() {
      _future = widget.client.getTransactions(limit: 100);
    });
    await _future;
  }

  // Per-kind icon + sign-color. Falls back to a neutral icon for
  // any unknown kind so a future schema change doesn't crash the UI.
  static const _kindLabels = <String, String>{
    'run_charge': 'Song spend',
    'song-spend': 'Song spend',
    'run_refund': 'Refund',
    'admin_credit': 'Admin credit',
    'signup_grant': 'Welcome credit',
    'subscription_renewal': 'Subscription',
    'topup': 'Top-up',
  };

  IconData _iconFor(String kind, int amount) {
    if (amount > 0) return Icons.add_circle_outline;
    return Icons.remove_circle_outline;
  }

  Color _colorFor(int amount, BuildContext ctx) {
    if (amount > 0) return Colors.green.shade400;
    return Theme.of(ctx).colorScheme.error;
  }

  String _fmtDate(String iso) {
    try {
      final d = DateTime.parse(iso).toLocal();
      return '${d.year}-${d.month.toString().padLeft(2, "0")}-'
          '${d.day.toString().padLeft(2, "0")} '
          '${d.hour.toString().padLeft(2, "0")}:${d.minute.toString().padLeft(2, "0")}';
    } catch (_) {
      return iso;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Transactions')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<List<CreditTx>>(
          future: _future,
          builder: (ctx, snap) {
            if (snap.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snap.hasError) {
              return Center(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Text(
                    'Failed to load: ${snap.error}',
                    style: TextStyle(
                        color: Theme.of(context).colorScheme.error),
                    textAlign: TextAlign.center,
                  ),
                ),
              );
            }
            final txs = snap.data ?? [];
            if (txs.isEmpty) {
              return ListView(
                children: const [
                  SizedBox(height: 80),
                  Icon(Icons.receipt_long,
                      size: 64, color: FacelessTheme.textSecondary),
                  SizedBox(height: 16),
                  Padding(
                    padding: EdgeInsets.symmetric(horizontal: 32),
                    child: Text(
                      'No transactions yet.\n'
                      'Generate a song or buy credits to see activity here.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: FacelessTheme.textSecondary),
                    ),
                  ),
                ],
              );
            }
            return ListView.separated(
              padding: const EdgeInsets.symmetric(vertical: 8),
              itemCount: txs.length,
              separatorBuilder: (_, _) => const Divider(height: 1),
              itemBuilder: (ctx, i) {
                final t = txs[i];
                final amount = t.amount;
                final label = _kindLabels[t.kind] ?? t.kind;
                final sign = amount > 0 ? '+' : '';
                return ListTile(
                  leading: Icon(_iconFor(t.kind, amount),
                      color: _colorFor(amount, ctx)),
                  title: Text(label),
                  subtitle: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (t.description != null && t.description!.isNotEmpty)
                        Text(t.description!,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontSize: 12)),
                      Text(_fmtDate(t.createdAt),
                          style: const TextStyle(
                              fontSize: 11,
                              color: FacelessTheme.textSecondary)),
                    ],
                  ),
                  trailing: Text(
                    '$sign$amount',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: _colorFor(amount, ctx),
                    ),
                  ),
                );
              },
            );
          },
        ),
      ),
    );
  }
}
