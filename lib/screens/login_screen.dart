import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../api/client.dart';
import '../api/settings.dart';
import '../l10n/l10n.dart';
import '../theme.dart';
import '../widgets/faceless_logo.dart';
import 'legal_screen.dart';

enum _Mode { signIn, signUp }

class LoginScreen extends StatefulWidget {
  /// When true, opens with the "Sign up" segment selected (used by the
  /// landing page's "Start free" CTA). Defaults to sign-in so returning
  /// users land where they expect.
  final bool startInSignUpMode;
  const LoginScreen({super.key, this.startInSignUpMode = false});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _formKey = GlobalKey<FormState>();
  late _Mode _mode =
      widget.startInSignUpMode ? _Mode.signUp : _Mode.signIn;
  bool _busy = false;
  bool _showPassword = false;
  // Tier-3 legal gate: sign-up requires ticking the Terms/Privacy box.
  bool _agreedToTerms = false;
  String? _error;
  String? _info;

  // Recognizers for the tappable "Terms of Service" / "Privacy Policy"
  // spans in the agreement checkbox label. Owned here so they're disposed.
  late final TapGestureRecognizer _tosRecognizer =
      TapGestureRecognizer()..onTap = _openLegal;
  late final TapGestureRecognizer _privacyRecognizer =
      TapGestureRecognizer()..onTap = _openLegal;

  void _openLegal() {
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const LegalScreen()),
    );
  }

  @override
  void dispose() {
    _tosRecognizer.dispose();
    _privacyRecognizer.dispose();
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  String? _validateEmail(String? v) {
    final s = (v ?? '').trim();
    if (s.isEmpty) return context.l10n.loginEmailRequired;
    if (!s.contains('@') || !s.contains('.')) {
      return context.l10n.loginEmailInvalid;
    }
    return null;
  }

  String? _validatePassword(String? v) {
    final s = v ?? '';
    if (s.isEmpty) return context.l10n.loginPasswordRequired;
    if (_mode == _Mode.signUp && s.length < 8) {
      return context.l10n.loginPasswordMinLength;
    }
    return null;
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    // Enforce the legal gate here, not only via the disabled button — the
    // password field's onFieldSubmitted (Enter key) bypasses button state.
    if (_mode == _Mode.signUp && !_agreedToTerms) {
      setState(() => _error =
          'Please agree to the Terms of Service and Privacy Policy to continue.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
      _info = null;
    });
    try {
      if (_mode == _Mode.signIn) {
        await Supabase.instance.client.auth.signInWithPassword(
          email: _email.text.trim(),
          password: _password.text,
        );
        // The auth-state stream in main.dart switches home: to HomeScreen
        // on its own, but if we got here via Landing → push LoginScreen,
        // this screen is still on top of the navigation stack and would
        // hide the new home. Pop it so the user actually lands on home.
        if (mounted && Navigator.of(context).canPop()) {
          Navigator.of(context).pop();
        }
      } else {
        await Supabase.instance.client.auth.signUp(
          email: _email.text.trim(),
          password: _password.text,
        );
        // Best-effort: record ToS acceptance server-side now, if signup
        // returned a session. If there's no session yet (email confirmation
        // required) or this call fails, the 403 terms gate will prompt the
        // user on their first paid action instead.
        if (Supabase.instance.client.auth.currentSession != null) {
          try {
            final client = FacelessApiClient(FacelessSettings());
            await client.acceptTerms();
            client.close();
          } catch (_) {
            // Non-fatal — acceptance is re-attemptable via the gate.
          }
        }
        // If Supabase auto-confirms email (project setting), sign-up
        // returns a session immediately and the auth-state stream will
        // route to home — same pop fix as sign-in. If confirmation is
        // required, no session yet and canPop is still safe.
        if (mounted &&
            Supabase.instance.client.auth.currentSession != null &&
            Navigator.of(context).canPop()) {
          Navigator.of(context).pop();
        } else if (mounted) {
          setState(() => _info = context.l10n.loginAccountCreatedInfo);
        }
      }
    } on AuthException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (e) {
      if (mounted) {
        setState(
            () => _error = context.l10n.loginUnexpectedError(e.toString()));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _toggleMode() {
    setState(() {
      _mode = _mode == _Mode.signIn ? _Mode.signUp : _Mode.signIn;
      _error = null;
      _info = null;
    });
  }

  /// Sign-in "Forgot password?" flow. Prompts for the account email
  /// (prefilled from the email field) then asks Supabase to email a reset
  /// link. The link returns to the app via `AuthChangeEvent.passwordRecovery`
  /// (see main.dart), which routes to ResetPasswordScreen.
  Future<void> _forgotPassword() async {
    final controller = TextEditingController(text: _email.text.trim());
    final email = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Reset password'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              "Enter your account email and we'll send you a reset link.",
            ),
            const SizedBox(height: 16),
            TextField(
              controller: controller,
              keyboardType: TextInputType.emailAddress,
              autofocus: true,
              decoration: const InputDecoration(labelText: 'Email'),
              onSubmitted: (v) => Navigator.of(ctx).pop(v.trim()),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(controller.text.trim()),
            child: const Text('Send reset link'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (email == null || email.isEmpty) return;
    if (!mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    try {
      await Supabase.instance.client.auth.resetPasswordForEmail(email);
      messenger.showSnackBar(
        const SnackBar(content: Text('Check your email for a reset link.')),
      );
    } on AuthException catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(e.message)));
    } catch (e) {
      messenger.showSnackBar(
        SnackBar(content: Text('Could not send reset link: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final isSignIn = _mode == _Mode.signIn;
    return Scaffold(
      body: Stack(
        children: [
          // Soft radial accent in the background — gives the dark navy
          // a bit of depth without being noisy.
          Positioned.fill(
            child: DecoratedBox(
              decoration: const BoxDecoration(
                gradient: RadialGradient(
                  center: Alignment(-0.4, -0.6),
                  radius: 1.1,
                  colors: [
                    Color(0x33E7B53C),  // gold glow, ~20% alpha
                    Color(0x000A0E1A),
                  ],
                ),
              ),
            ),
          ),
          Positioned.fill(
            child: DecoratedBox(
              decoration: const BoxDecoration(
                gradient: RadialGradient(
                  center: Alignment(0.7, 0.9),
                  radius: 1.0,
                  colors: [
                    Color(0x288B5CF6),  // violet glow, ~16% alpha
                    Color(0x000A0E1A),
                  ],
                ),
              ),
            ),
          ),
          // Form
          SafeArea(
            child: Center(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(
                    horizontal: 24, vertical: 48),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 420),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      // ----------------- Brand -----------------
                      _BrandHeader(),
                      const SizedBox(height: 32),
                      // ----------------- Card ------------------
                      Container(
                        decoration: BoxDecoration(
                          color: FacelessTheme.surface,
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(
                            color: FacelessTheme.textSecondary
                                .withValues(alpha: 0.12),
                          ),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withValues(alpha: 0.45),
                              blurRadius: 24,
                              offset: const Offset(0, 12),
                            ),
                          ],
                        ),
                        padding: const EdgeInsets.all(28),
                        child: Form(
                          key: _formKey,
                          autovalidateMode:
                              AutovalidateMode.onUserInteraction,
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              // Mode toggle (segmented control)
                              _ModeSegmentedControl(
                                mode: _mode,
                                onChanged: _busy
                                    ? null
                                    : (m) {
                                        setState(() {
                                          _mode = m;
                                          _error = null;
                                          _info = null;
                                        });
                                      },
                              ),
                              const SizedBox(height: 24),
                              // Email
                              TextFormField(
                                controller: _email,
                                enabled: !_busy,
                                keyboardType: TextInputType.emailAddress,
                                autofillHints: const [AutofillHints.email],
                                validator: _validateEmail,
                                decoration: InputDecoration(
                                  labelText: context.l10n.loginEmailLabel,
                                  prefixIcon: const Icon(
                                      Icons.alternate_email,
                                      size: 20),
                                ),
                              ),
                              const SizedBox(height: 14),
                              // Password
                              TextFormField(
                                controller: _password,
                                enabled: !_busy,
                                obscureText: !_showPassword,
                                autofillHints: isSignIn
                                    ? const [AutofillHints.password]
                                    : const [AutofillHints.newPassword],
                                validator: _validatePassword,
                                onFieldSubmitted: (_) => _submit(),
                                decoration: InputDecoration(
                                  labelText: context.l10n.loginPasswordLabel,
                                  prefixIcon: const Icon(
                                      Icons.lock_outline,
                                      size: 20),
                                  suffixIcon: IconButton(
                                    icon: Icon(
                                      _showPassword
                                          ? Icons.visibility_off
                                          : Icons.visibility,
                                      size: 20,
                                    ),
                                    tooltip: _showPassword
                                        ? context.l10n.loginHidePassword
                                        : context.l10n.loginShowPassword,
                                    onPressed: () => setState(() =>
                                        _showPassword = !_showPassword),
                                  ),
                                ),
                              ),
                              // "Forgot password?" — sign-in only.
                              if (isSignIn)
                                Align(
                                  alignment: Alignment.centerRight,
                                  child: TextButton(
                                    onPressed:
                                        _busy ? null : _forgotPassword,
                                    style: TextButton.styleFrom(
                                      padding: const EdgeInsets.symmetric(
                                          horizontal: 4, vertical: 4),
                                      minimumSize: Size.zero,
                                      tapTargetSize: MaterialTapTargetSize
                                          .shrinkWrap,
                                    ),
                                    child: const Text(
                                      'Forgot password?',
                                      style: TextStyle(
                                        color: FacelessTheme.accent,
                                        fontWeight: FontWeight.w600,
                                        fontSize: 13,
                                      ),
                                    ),
                                  ),
                                ),
                              if (_error != null) ...[
                                const SizedBox(height: 14),
                                _Banner(
                                  icon: Icons.error_outline,
                                  color: FacelessTheme.danger,
                                  text: _error!,
                                ),
                              ],
                              if (_info != null) ...[
                                const SizedBox(height: 14),
                                _Banner(
                                  icon: Icons.check_circle_outline,
                                  color: FacelessTheme.success,
                                  text: _info!,
                                ),
                              ],
                              // Terms/Privacy agreement — sign-up only.
                              // Tapping the linked words opens LegalScreen;
                              // the box gates the Sign-Up button below.
                              if (!isSignIn) ...[
                                const SizedBox(height: 18),
                                Row(
                                  crossAxisAlignment:
                                      CrossAxisAlignment.start,
                                  children: [
                                    SizedBox(
                                      width: 24,
                                      height: 24,
                                      child: Checkbox(
                                        value: _agreedToTerms,
                                        onChanged: _busy
                                            ? null
                                            : (v) => setState(() =>
                                                _agreedToTerms = v ?? false),
                                      ),
                                    ),
                                    const SizedBox(width: 10),
                                    Expanded(
                                      child: Padding(
                                        padding:
                                            const EdgeInsets.only(top: 3),
                                        child: RichText(
                                          text: TextSpan(
                                            style: const TextStyle(
                                              color: FacelessTheme
                                                  .textSecondary,
                                              fontSize: 13,
                                              height: 1.4,
                                            ),
                                            children: [
                                              const TextSpan(
                                                  text: 'I agree to the '),
                                              TextSpan(
                                                text: 'Terms of Service',
                                                style: const TextStyle(
                                                  color:
                                                      FacelessTheme.accent,
                                                  fontWeight:
                                                      FontWeight.w600,
                                                ),
                                                recognizer: _tosRecognizer,
                                              ),
                                              const TextSpan(text: ' and '),
                                              TextSpan(
                                                text: 'Privacy Policy',
                                                style: const TextStyle(
                                                  color:
                                                      FacelessTheme.accent,
                                                  fontWeight:
                                                      FontWeight.w600,
                                                ),
                                                recognizer:
                                                    _privacyRecognizer,
                                              ),
                                            ],
                                          ),
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              ],
                              const SizedBox(height: 20),
                              // Submit
                              SizedBox(
                                height: 48,
                                child: FilledButton(
                                  onPressed: (_busy ||
                                          (!isSignIn && !_agreedToTerms))
                                      ? null
                                      : _submit,
                                  child: _busy
                                      ? const SizedBox(
                                          width: 22,
                                          height: 22,
                                          child: CircularProgressIndicator(
                                            strokeWidth: 2.5,
                                            color: Colors.black,
                                          ),
                                        )
                                      : Text(
                                          isSignIn
                                              ? context.l10n.commonSignIn
                                              : context
                                                  .l10n.loginCreateAccount,
                                        ),
                                ),
                              ),
                              const SizedBox(height: 14),
                              // Switch mode link
                              TextButton(
                                onPressed: _busy ? null : _toggleMode,
                                child: RichText(
                                  text: TextSpan(
                                    style: TextStyle(
                                      color: FacelessTheme.textSecondary,
                                      fontSize: 13,
                                    ),
                                    children: [
                                      TextSpan(
                                        text: isSignIn
                                            ? context.l10n.loginNoAccountYet
                                            : context
                                                .l10n.loginAlreadyHaveAccount,
                                      ),
                                      TextSpan(
                                        text: isSignIn
                                            ? context.l10n.loginSignUp
                                            : context.l10n.commonSignIn,
                                        style: const TextStyle(
                                          color: FacelessTheme.accent,
                                          fontWeight: FontWeight.w600,
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
                      const SizedBox(height: 24),
                      Text(
                        context.l10n.loginFooterTagline,
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: FacelessTheme.textSecondary
                              .withValues(alpha: 0.7),
                          fontSize: 12,
                          letterSpacing: 0.3,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _BrandHeader extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          width: 64,
          height: 64,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            boxShadow: [
              BoxShadow(
                color: FacelessTheme.accent.withValues(alpha: 0.35),
                blurRadius: 24,
                offset: const Offset(0, 6),
              ),
            ],
          ),
          child: const FacelessLogo(size: 64),
        ),
        const SizedBox(height: 16),
        const Text(
          'Faceless',
          style: TextStyle(
            color: FacelessTheme.textPrimary,
            fontSize: 32,
            fontWeight: FontWeight.w700,
            letterSpacing: 0.5,
          ),
        ),
        const SizedBox(height: 6),
        Text(
          context.l10n.loginSubtitle,
          style: TextStyle(
            color: FacelessTheme.textSecondary,
            fontSize: 14,
          ),
        ),
      ],
    );
  }
}

class _ModeSegmentedControl extends StatelessWidget {
  final _Mode mode;
  final ValueChanged<_Mode>? onChanged;
  const _ModeSegmentedControl({required this.mode, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: FacelessTheme.bg,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: FacelessTheme.textSecondary.withValues(alpha: 0.12),
        ),
      ),
      padding: const EdgeInsets.all(4),
      child: Row(
        children: [
          _segment(context.l10n.commonSignIn, _Mode.signIn),
          _segment(context.l10n.loginSignUp, _Mode.signUp),
        ],
      ),
    );
  }

  Widget _segment(String label, _Mode m) {
    final active = mode == m;
    return Expanded(
      child: GestureDetector(
        onTap: onChanged == null ? null : () => onChanged!(m),
        behavior: HitTestBehavior.opaque,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 160),
          padding: const EdgeInsets.symmetric(vertical: 10),
          decoration: BoxDecoration(
            color: active ? FacelessTheme.surface2 : Colors.transparent,
            borderRadius: BorderRadius.circular(7),
          ),
          alignment: Alignment.center,
          child: Text(
            label,
            style: TextStyle(
              color: active
                  ? FacelessTheme.textPrimary
                  : FacelessTheme.textSecondary,
              fontWeight: active ? FontWeight.w600 : FontWeight.w500,
              fontSize: 14,
            ),
          ),
        ),
      ),
    );
  }
}

class _Banner extends StatelessWidget {
  final IconData icon;
  final Color color;
  final String text;
  const _Banner(
      {required this.icon, required this.color, required this.text});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.10),
        border: Border.all(color: color.withValues(alpha: 0.4)),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 18),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: TextStyle(
                color: FacelessTheme.textPrimary,
                fontSize: 13,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
