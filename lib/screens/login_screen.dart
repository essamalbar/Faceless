import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../theme.dart';
import '../widgets/faceless_logo.dart';

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
  String? _error;
  String? _info;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  String? _validateEmail(String? v) {
    final s = (v ?? '').trim();
    if (s.isEmpty) return 'Email is required';
    if (!s.contains('@') || !s.contains('.')) return 'Enter a valid email';
    return null;
  }

  String? _validatePassword(String? v) {
    final s = v ?? '';
    if (s.isEmpty) return 'Password is required';
    if (_mode == _Mode.signUp && s.length < 8) {
      return 'Min 8 characters for new accounts';
    }
    return null;
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
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
        // Auth-state stream in main.dart will route to the home screen.
      } else {
        await Supabase.instance.client.auth.signUp(
          email: _email.text.trim(),
          password: _password.text,
        );
        if (mounted) {
          setState(() => _info =
              'Account created. Check your email to confirm — or sign in '
              'directly if email confirmation is disabled.');
        }
      }
    } on AuthException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (e) {
      if (mounted) setState(() => _error = 'Unexpected error: $e');
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
                                decoration: const InputDecoration(
                                  labelText: 'Email',
                                  prefixIcon: Icon(Icons.alternate_email,
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
                                  labelText: 'Password',
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
                                        ? 'Hide password'
                                        : 'Show password',
                                    onPressed: () => setState(() =>
                                        _showPassword = !_showPassword),
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
                              const SizedBox(height: 20),
                              // Submit
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
                                            color: Colors.black,
                                          ),
                                        )
                                      : Text(
                                          isSignIn
                                              ? 'Sign in'
                                              : 'Create account',
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
                                            ? "No account yet? "
                                            : 'Already have one? ',
                                      ),
                                      TextSpan(
                                        text: isSignIn
                                            ? 'Sign up'
                                            : 'Sign in',
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
                        'Faceless · Arabic horror, scripted by AI',
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
          'Sign in to manage your runs',
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
          _segment('Sign in', _Mode.signIn),
          _segment('Sign up', _Mode.signUp),
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
