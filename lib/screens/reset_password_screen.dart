import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../theme.dart';
import '../widgets/faceless_logo.dart';

/// Shown when the user returns from a password-reset email link. Supabase
/// emits `AuthChangeEvent.passwordRecovery` (wired in main.dart), which pushes
/// this screen. The user is in a temporary recovery session, so setting a new
/// password via `updateUser` completes the reset and keeps them signed in.
class ResetPasswordScreen extends StatefulWidget {
  const ResetPasswordScreen({super.key});

  @override
  State<ResetPasswordScreen> createState() => _ResetPasswordScreenState();
}

class _ResetPasswordScreenState extends State<ResetPasswordScreen> {
  final _password = TextEditingController();
  final _confirm = TextEditingController();
  final _formKey = GlobalKey<FormState>();
  bool _busy = false;
  bool _showPassword = false;
  String? _error;

  @override
  void dispose() {
    _password.dispose();
    _confirm.dispose();
    super.dispose();
  }

  String? _validatePassword(String? v) {
    final s = v ?? '';
    if (s.isEmpty) return 'Please enter a new password.';
    if (s.length < 8) return 'Password must be at least 8 characters.';
    return null;
  }

  String? _validateConfirm(String? v) {
    if ((v ?? '') != _password.text) return 'Passwords do not match.';
    return null;
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await Supabase.instance.client.auth.updateUser(
        UserAttributes(password: _password.text),
      );
      messenger.showSnackBar(
        const SnackBar(content: Text('Your password has been updated.')),
      );
      // Recovery session is now a full session — return to the app root
      // (the auth-state stream in main.dart shows HomeScreen).
      navigator.popUntil((route) => route.isFirst);
    } on AuthException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (e) {
      if (mounted) {
        setState(() => _error = 'Something went wrong: $e');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding:
                const EdgeInsets.symmetric(horizontal: 24, vertical: 48),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const FacelessLogo(size: 56),
                  const SizedBox(height: 24),
                  Text(
                    'Set a new password',
                    textAlign: TextAlign.center,
                    style: FacelessTheme.display(size: 24),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Choose a new password for your account.',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: FacelessTheme.textSecondary,
                      fontSize: 14,
                    ),
                  ),
                  const SizedBox(height: 28),
                  Container(
                    decoration: BoxDecoration(
                      color: FacelessTheme.surface,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: FacelessTheme.border),
                      boxShadow: FacelessTheme.softShadow,
                    ),
                    padding: const EdgeInsets.all(28),
                    child: Form(
                      key: _formKey,
                      autovalidateMode: AutovalidateMode.onUserInteraction,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          TextFormField(
                            controller: _password,
                            enabled: !_busy,
                            obscureText: !_showPassword,
                            autofillHints: const [AutofillHints.newPassword],
                            validator: _validatePassword,
                            decoration: InputDecoration(
                              labelText: 'New password',
                              prefixIcon:
                                  const Icon(Icons.lock_outline, size: 20),
                              suffixIcon: IconButton(
                                icon: Icon(
                                  _showPassword
                                      ? Icons.visibility_off
                                      : Icons.visibility,
                                  size: 20,
                                ),
                                onPressed: () => setState(
                                    () => _showPassword = !_showPassword),
                              ),
                            ),
                          ),
                          const SizedBox(height: 14),
                          TextFormField(
                            controller: _confirm,
                            enabled: !_busy,
                            obscureText: !_showPassword,
                            autofillHints: const [AutofillHints.newPassword],
                            validator: _validateConfirm,
                            onFieldSubmitted: (_) => _submit(),
                            decoration: const InputDecoration(
                              labelText: 'Confirm new password',
                              prefixIcon: Icon(Icons.lock_outline, size: 20),
                            ),
                          ),
                          if (_error != null) ...[
                            const SizedBox(height: 14),
                            Container(
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: FacelessTheme.danger
                                    .withValues(alpha: 0.10),
                                border: Border.all(
                                    color: FacelessTheme.danger
                                        .withValues(alpha: 0.4)),
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const Icon(Icons.error_outline,
                                      color: FacelessTheme.danger, size: 18),
                                  const SizedBox(width: 10),
                                  Expanded(
                                    child: Text(
                                      _error!,
                                      style: const TextStyle(
                                        color: FacelessTheme.textPrimary,
                                        fontSize: 13,
                                        height: 1.4,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                          const SizedBox(height: 20),
                          SizedBox(
                            height: 48,
                            child: FilledButton(
                              onPressed: _busy ? null : _submit,
                              child: _busy
                                  ? const SizedBox(
                                      width: 22,
                                      height: 22,
                                      child: CircularProgressIndicator(
                                        strokeWidth: 2.5,
                                        color: Colors.white,
                                      ),
                                    )
                                  : const Text('Update password'),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
