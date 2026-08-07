/// Legal screen — Terms of Service, Privacy Policy, and Refund Policy.
///
/// IMPORTANT: the Terms and Privacy copy here is PLACEHOLDER text and is
/// clearly marked as non-binding. It MUST be replaced with lawyer-reviewed
/// wording before launch. The Refund section, however, describes the REAL
/// credit-refund behavior of the pipeline and should be kept accurate.
///
/// Strings are intentionally hardcoded in English (not routed through l10n)
/// so that adding this screen doesn't churn the generated localizations.
library;

import 'package:flutter/material.dart';

import '../api/client.dart';
import '../theme.dart';

class LegalScreen extends StatelessWidget {
  /// When set (and [mustAccept] is true) a sticky bottom "I Accept" bar is
  /// shown that calls [FacelessApiClient.acceptTerms]. LegalScreen NEVER
  /// closes this client — the caller owns its lifecycle (new_song passes its
  /// long-lived client; settings creates-and-closes its own).
  final FacelessApiClient? client;

  /// Accept-capable mode. When false (default) the screen is view-only.
  final bool mustAccept;

  const LegalScreen({super.key, this.client, this.mustAccept = false});

  @override
  Widget build(BuildContext context) {
    final acceptClient = client;
    return Scaffold(
      backgroundColor: Colors.transparent,
      appBar: AppBar(title: const Text('Terms & Privacy')),
      bottomNavigationBar: (mustAccept && acceptClient != null)
          ? _AcceptBar(client: acceptClient)
          : null,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 640),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: const [
                  _PlaceholderBanner(),
                  SizedBox(height: 20),
                  _Section(
                    title: 'Terms of Service',
                    body:
                        'These Terms govern your use of the Faceless app and the '
                        'AI content-generation service it provides. By creating '
                        'an account you agree to use the service lawfully, to '
                        'generate only content you are permitted to create, and '
                        'to not misuse or resell the service in violation of '
                        'these Terms.\n\n'
                        'You are responsible for the prompts, lyrics, uploads, '
                        'and other inputs you supply, and for how you use the '
                        'videos, songs, and other outputs the service produces. '
                        'The service is provided "as is" without warranties, and '
                        'our liability is limited to the maximum extent permitted '
                        'by law.',
                  ),
                  SizedBox(height: 16),
                  _Section(
                    title: 'Privacy Policy',
                    body:
                        'We collect the account information you provide (such as '
                        'your email address) and the data needed to run and bill '
                        'the service — your prompts, uploads, generated artifacts, '
                        'and usage/credit history.\n\n'
                        'This data is used to operate the service, process '
                        'payments, and improve reliability. Generation steps may '
                        'send your inputs to third-party AI providers strictly to '
                        'produce your requested output. We do not sell your '
                        'personal information.',
                  ),
                  SizedBox(height: 16),
                  _Section(
                    title: 'Refund Policy',
                    // REAL behavior — keep this accurate (not placeholder).
                    body:
                        'Credits are consumed to render paid output. Refund '
                        'behavior:\n\n'
                        '• Cancel a run before it finishes to refund the unused '
                        'credits for that run.\n'
                        '• A failed render keeps the charge, but you can resume '
                        'it for free — you are not charged again for the retry.\n'
                        '• A completed render is non-refundable.',
                    isPlaceholder: false,
                  ),
                  SizedBox(height: 24),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Sticky bottom action that records the user's acceptance of the current
/// Terms. On success it pops `true` so the caller can react (clear its error
/// / let the user retry). Errors are shown inline and the button re-enables.
class _AcceptBar extends StatefulWidget {
  final FacelessApiClient client;
  const _AcceptBar({required this.client});

  @override
  State<_AcceptBar> createState() => _AcceptBarState();
}

class _AcceptBarState extends State<_AcceptBar> {
  bool _busy = false;
  String? _error;

  Future<void> _accept() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.client.acceptTerms();
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = '$e';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Container(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
        decoration: BoxDecoration(
          color: FacelessTheme.surface,
          border: Border(top: BorderSide(color: FacelessTheme.border)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (_error != null) ...[
              Text(
                _error!,
                style: const TextStyle(
                  color: FacelessTheme.danger,
                  fontSize: 12.5,
                  height: 1.4,
                ),
              ),
              const SizedBox(height: 10),
            ],
            FilledButton(
              onPressed: _busy ? null : _accept,
              child: _busy
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('I Accept the Terms & Privacy'),
            ),
          ],
        ),
      ),
    );
  }
}

/// Big, unmissable warning that the Terms/Privacy copy is not binding.
class _PlaceholderBanner extends StatelessWidget {
  const _PlaceholderBanner();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: FacelessTheme.danger.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: FacelessTheme.danger.withValues(alpha: 0.55),
          width: 1.5,
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.warning_amber_rounded,
              color: FacelessTheme.danger, size: 22),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              '⚠️ PLACEHOLDER — not legal advice. Replace with '
              'lawyer-reviewed text before launch.',
              style: TextStyle(
                color: FacelessTheme.danger,
                fontSize: 13.5,
                fontWeight: FontWeight.w700,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Section extends StatelessWidget {
  final String title;
  final String body;
  final bool isPlaceholder;
  const _Section({
    required this.title,
    required this.body,
    this.isPlaceholder = true,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: FacelessTheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: FacelessTheme.border),
        boxShadow: FacelessTheme.softShadow,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(
                    color: FacelessTheme.textPrimary,
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              if (isPlaceholder)
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: FacelessTheme.danger.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(
                        color: FacelessTheme.danger.withValues(alpha: 0.45)),
                  ),
                  child: const Text(
                    'PLACEHOLDER',
                    style: TextStyle(
                      color: FacelessTheme.danger,
                      fontSize: 10,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 0.6,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            body,
            style: const TextStyle(
              color: FacelessTheme.textSecondary,
              fontSize: 14,
              height: 1.55,
            ),
          ),
        ],
      ),
    );
  }
}
