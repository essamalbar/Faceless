import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../api/settings.dart';
import '../config.dart';
import '../theme.dart';
import 'billing_screen.dart';

class SettingsScreen extends StatefulWidget {
  final bool firstLaunch;
  const SettingsScreen({super.key, this.firstLaunch = false});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _settings = FacelessSettings();
  final _urlCtrl = TextEditingController();
  final _formKey = GlobalKey<FormState>();
  bool _loading = false;
  String? _testResult;

  // Account state — best-effort, never blocks the screen render.
  String? _email;
  PlanInfo? _plan;

  // Advanced section is hidden by default to keep the screen calm for the
  // 99% case where the launcher already configured everything. We force it
  // open on first launch when there's no saved URL yet.
  late bool _advancedExpanded = widget.firstLaunch;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final url = await _settings.baseUrl();
    if (!mounted) return;
    _urlCtrl.text = url ?? '';
    setState(() {});

    // Account info — fire-and-forget.
    try {
      final user = Supabase.instance.client.auth.currentUser;
      _email = user?.email;
    } catch (_) {
      _email = null;
    }
    try {
      final client = FacelessApiClient(_settings);
      final p = await client.getPlan();
      client.close();
      if (mounted) setState(() => _plan = p);
    } catch (_) {
      // Best-effort.
    }
  }

  Future<void> _testConnection() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _loading = true;
      _testResult = null;
    });
    // CRITICAL: do NOT call _settings.save() here. The previous version did,
    // which meant a FAILED test still wrote bad URLs to the keychain — and
    // since FacelessSettings.baseUrl() resolves saved-storage BEFORE the
    // dart-define default, those bad URLs survived launcher updates and
    // manifested as "the app keeps trying the old Cloudflare URL even after
    // I switched to Tailscale". The Test button must be a pure read op.
    final ephemeral = _EphemeralSettings(baseUrl: _urlCtrl.text.trim());
    final client = FacelessApiClient(ephemeral);
    try {
      // Cloud Run reserves /healthz at the LB so it never reaches FastAPI;
      // exercise the real authenticated path instead.
      await client.listRuns();
      setState(() => _testResult = '✓ Connected');
    } catch (e) {
      setState(() => _testResult = '✗ ${e.toString()}');
    } finally {
      client.close();
      setState(() => _loading = false);
    }
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    await _settings.save(baseUrl: _urlCtrl.text);
    if (!mounted) return;
    Navigator.of(context).pop(true);
  }

  Future<void> _resetToDefaults() async {
    final yes = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Reset to launcher defaults?'),
        content: const Text(
          'This clears your saved Server URL from the device. The app will '
          'fall back to whatever the launcher script (run-app.sh) baked in '
          'via --dart-define on the next launch. Use this when the tunnel '
          'URL has changed and the saved value is stale.',
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          FilledButton(
              style: FilledButton.styleFrom(
                  backgroundColor: FacelessTheme.danger,
                  foregroundColor: Colors.white),
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Reset')),
        ],
      ),
    );
    if (yes != true || !mounted) return;
    await _settings.clear();
    if (!mounted) return;
    final url = await _settings.baseUrl();
    if (mounted) {
      _urlCtrl.text = url ?? '';
      setState(() => _testResult = '✓ Reset — using launcher defaults');
    }
  }

  Future<void> _signOut() async {
    final yes = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Sign out?'),
        content: const Text(
          "You'll need to sign in again to access your library and credits.",
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          FilledButton(
              style: FilledButton.styleFrom(
                  backgroundColor: FacelessTheme.danger,
                  foregroundColor: Colors.white),
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Sign out')),
        ],
      ),
    );
    if (yes != true) return;
    try {
      await Supabase.instance.client.auth.signOut();
    } catch (_) {
      // Supabase not initialized (legacy mode) — nothing to do.
    }
    // The auth-state stream in main.dart will route us back to LoginScreen.
    if (mounted) Navigator.of(context).maybePop();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.transparent,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
        title: const Text('Settings'),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 640),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _AccountCard(email: _email, plan: _plan),
                    const SizedBox(height: 24),
                    _SectionLabel(text: 'Subscription'),
                    const SizedBox(height: 8),
                    _SettingTile(
                      icon: Icons.monetization_on_outlined,
                      title: 'Plan & credits',
                      subtitle: _plan == null
                          ? 'View plans, manage your subscription'
                          : (_plan!.plan == 'free'
                              ? 'You are on the Free plan — subscribe to render videos'
                              : 'Manage your ${_titleCase(_plan!.plan)} plan'),
                      onTap: () => Navigator.of(context).push(
                        MaterialPageRoute(
                            builder: (_) => const BillingScreen()),
                      ),
                    ),
                    const SizedBox(height: 24),
                    _SectionLabel(text: 'Advanced'),
                    const SizedBox(height: 8),
                    _AdvancedCard(
                      expanded: _advancedExpanded,
                      onToggle: () => setState(
                          () => _advancedExpanded = !_advancedExpanded),
                      urlCtrl: _urlCtrl,
                      loading: _loading,
                      testResult: _testResult,
                      onTest: _testConnection,
                      onSave: _save,
                      onReset: FacelessConfig.apiUrl.isNotEmpty
                          ? _resetToDefaults
                          : null,
                      firstLaunch: widget.firstLaunch,
                    ),
                    const SizedBox(height: 24),
                    _SectionLabel(text: 'About'),
                    const SizedBox(height: 8),
                    const _AboutCard(),
                    const SizedBox(height: 32),
                    _DangerButton(
                      icon: Icons.logout,
                      label: 'Sign out',
                      onPressed: _loading ? null : _signOut,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  static String _titleCase(String s) =>
      s.isEmpty ? s : s[0].toUpperCase() + s.substring(1);

  @override
  void dispose() {
    _urlCtrl.dispose();
    super.dispose();
  }
}


// ---------------------------------------------------------------------------
// Section primitives
// ---------------------------------------------------------------------------

class _SectionLabel extends StatelessWidget {
  final String text;
  const _SectionLabel({required this.text});
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: Text(
        text.toUpperCase(),
        style: TextStyle(
          color: FacelessTheme.textSecondary.withValues(alpha: 0.7),
          fontSize: 11,
          fontWeight: FontWeight.w700,
          letterSpacing: 1.2,
        ),
      ),
    );
  }
}

class _SettingTile extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? subtitle;
  final VoidCallback? onTap;
  const _SettingTile({
    required this.icon,
    required this.title,
    this.subtitle,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: FacelessTheme.surface,
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
              color: FacelessTheme.textSecondary.withValues(alpha: 0.12),
            ),
          ),
          child: Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: FacelessTheme.accent.withValues(alpha: 0.14),
                ),
                child: Icon(icon, color: FacelessTheme.accent, size: 20),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        color: FacelessTheme.textPrimary,
                        fontWeight: FontWeight.w600,
                        fontSize: 14,
                      ),
                    ),
                    if (subtitle != null) ...[
                      const SizedBox(height: 2),
                      Text(
                        subtitle!,
                        style: const TextStyle(
                          color: FacelessTheme.textSecondary,
                          fontSize: 12,
                          height: 1.35,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              const Icon(Icons.chevron_right,
                  color: FacelessTheme.textSecondary, size: 20),
            ],
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Account card — top section
// ---------------------------------------------------------------------------

class _AccountCard extends StatelessWidget {
  final String? email;
  final PlanInfo? plan;
  const _AccountCard({required this.email, required this.plan});

  @override
  Widget build(BuildContext context) {
    final initial = (email == null || email!.isEmpty)
        ? '?'
        : email![0].toUpperCase();
    final planLabel = plan == null
        ? '…'
        : (plan!.plan == 'free' ? 'Free plan' : '${_titleCase(plan!.plan)} plan');
    return Container(
      padding: const EdgeInsets.fromLTRB(18, 18, 18, 18),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(18),
        color: FacelessTheme.surface,
        border: Border.all(color: FacelessTheme.border),
        boxShadow: FacelessTheme.softShadow,
      ),
      child: Row(
        children: [
          Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: const LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [FacelessTheme.accent, Color(0xFFB07F1F)],
              ),
              boxShadow: [
                BoxShadow(
                  color: FacelessTheme.accent.withValues(alpha: 0.35),
                  blurRadius: 18,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            alignment: Alignment.center,
            child: Text(
              initial,
              style: const TextStyle(
                color: Colors.black,
                fontWeight: FontWeight.w800,
                fontSize: 22,
              ),
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  email ?? 'Not signed in',
                  style: const TextStyle(
                    color: FacelessTheme.textPrimary,
                    fontWeight: FontWeight.w700,
                    fontSize: 15,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 4),
                Wrap(
                  spacing: 8,
                  runSpacing: 6,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    _ChipLabel(
                      label: planLabel,
                      color: plan?.plan == 'free' || plan == null
                          ? FacelessTheme.textSecondary
                          : FacelessTheme.accent,
                    ),
                    if (plan != null)
                      _ChipLabel(
                        label: '${plan!.balance} credits',
                        color: FacelessTheme.accent2,
                      ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  static String _titleCase(String s) =>
      s.isEmpty ? s : s[0].toUpperCase() + s.substring(1);
}

class _ChipLabel extends StatelessWidget {
  final String label;
  final Color color;
  const _ChipLabel({required this.label, required this.color});
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withValues(alpha: 0.45)),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontSize: 11,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.3,
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Advanced card — collapsible server URL config
// ---------------------------------------------------------------------------

class _AdvancedCard extends StatelessWidget {
  final bool expanded;
  final VoidCallback onToggle;
  final TextEditingController urlCtrl;
  final bool loading;
  final String? testResult;
  final VoidCallback onTest;
  final VoidCallback onSave;
  final VoidCallback? onReset;
  final bool firstLaunch;

  const _AdvancedCard({
    required this.expanded,
    required this.onToggle,
    required this.urlCtrl,
    required this.loading,
    required this.testResult,
    required this.onTest,
    required this.onSave,
    required this.onReset,
    required this.firstLaunch,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: FacelessTheme.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: FacelessTheme.textSecondary.withValues(alpha: 0.12),
        ),
      ),
      child: Column(
        children: [
          InkWell(
            onTap: onToggle,
            borderRadius: BorderRadius.circular(14),
            child: Padding(
              padding: const EdgeInsets.symmetric(
                  horizontal: 16, vertical: 14),
              child: Row(
                children: [
                  Container(
                    width: 36,
                    height: 36,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: FacelessTheme.textSecondary
                          .withValues(alpha: 0.12),
                    ),
                    child: const Icon(Icons.tune,
                        color: FacelessTheme.textPrimary, size: 20),
                  ),
                  const SizedBox(width: 14),
                  const Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Server connection',
                            style: TextStyle(
                              color: FacelessTheme.textPrimary,
                              fontWeight: FontWeight.w600,
                              fontSize: 14,
                            )),
                        SizedBox(height: 2),
                        Text(
                          'Override the API URL — for self-hosters and debugging',
                          style: TextStyle(
                            color: FacelessTheme.textSecondary,
                            fontSize: 12,
                            height: 1.35,
                          ),
                        ),
                      ],
                    ),
                  ),
                  AnimatedRotation(
                    turns: expanded ? 0.5 : 0,
                    duration: const Duration(milliseconds: 200),
                    child: const Icon(Icons.expand_more,
                        color: FacelessTheme.textSecondary, size: 22),
                  ),
                ],
              ),
            ),
          ),
          AnimatedCrossFade(
            duration: const Duration(milliseconds: 200),
            crossFadeState: expanded
                ? CrossFadeState.showSecond
                : CrossFadeState.showFirst,
            firstChild: const SizedBox(width: double.infinity, height: 0),
            secondChild: Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Divider(
                    height: 18,
                    color: FacelessTheme.textSecondary.withValues(alpha: 0.1),
                  ),
                  if (firstLaunch) ...[
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: FacelessTheme.accent.withValues(alpha: 0.10),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: const Row(
                        children: [
                          Icon(Icons.info_outline,
                              color: FacelessTheme.accent, size: 18),
                          SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              "First-time setup. Paste the API URL printed "
                              "by run-app.sh, then tap Test → Save.",
                              style: TextStyle(
                                color: FacelessTheme.textPrimary,
                                fontSize: 12,
                                height: 1.4,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 14),
                  ],
                  TextFormField(
                    controller: urlCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Server URL',
                      hintText: 'https://xyz.example.com',
                      border: OutlineInputBorder(),
                      isDense: true,
                    ),
                    keyboardType: TextInputType.url,
                    autocorrect: false,
                    validator: (v) {
                      if (v == null || v.trim().isEmpty) return 'required';
                      if (!v.startsWith('http')) {
                        return 'must start with http:// or https://';
                      }
                      return null;
                    },
                  ),
                  if (testResult != null) ...[
                    const SizedBox(height: 10),
                    Text(
                      testResult!,
                      style: TextStyle(
                        color: testResult!.startsWith('✓')
                            ? FacelessTheme.success
                            : FacelessTheme.danger,
                        fontSize: 12,
                      ),
                    ),
                  ],
                  const SizedBox(height: 14),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: loading ? null : onTest,
                          icon: const Icon(Icons.wifi_tethering, size: 18),
                          label: const Text('Test'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: FilledButton.icon(
                          onPressed: loading ? null : onSave,
                          icon: const Icon(Icons.save, size: 18),
                          label: const Text('Save'),
                        ),
                      ),
                    ],
                  ),
                  if (onReset != null) ...[
                    const SizedBox(height: 10),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: TextButton.icon(
                        onPressed: loading ? null : onReset,
                        icon: const Icon(Icons.restart_alt,
                            color: FacelessTheme.danger, size: 18),
                        label: const Text(
                          'Reset to launcher defaults',
                          style:
                              TextStyle(color: FacelessTheme.danger),
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// About card
// ---------------------------------------------------------------------------

class _AboutCard extends StatelessWidget {
  const _AboutCard();
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      decoration: BoxDecoration(
        color: FacelessTheme.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: FacelessTheme.textSecondary.withValues(alpha: 0.12),
        ),
      ),
      child: const Column(
        children: [
          _AboutRow(label: 'App',     value: 'Faceless'),
          _AboutRow(label: 'Version', value: '1.0.0'),
          _AboutRow(
            label: 'Made for',
            value: 'Arabic short-form storytelling',
            last: true,
          ),
        ],
      ),
    );
  }
}

class _AboutRow extends StatelessWidget {
  final String label;
  final String value;
  final bool last;
  const _AboutRow({
    required this.label,
    required this.value,
    this.last = false,
  });
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Column(
        children: [
          Row(
            children: [
              Text(label,
                  style: const TextStyle(
                    color: FacelessTheme.textSecondary,
                    fontSize: 12,
                  )),
              const Spacer(),
              Text(value,
                  style: const TextStyle(
                    color: FacelessTheme.textPrimary,
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                  )),
            ],
          ),
          if (!last) ...[
            const SizedBox(height: 8),
            Divider(
              height: 1,
              color: FacelessTheme.textSecondary.withValues(alpha: 0.08),
            ),
          ],
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Danger button — for sign-out
// ---------------------------------------------------------------------------

class _DangerButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback? onPressed;
  const _DangerButton({
    required this.icon,
    required this.label,
    required this.onPressed,
  });
  @override
  Widget build(BuildContext context) {
    return OutlinedButton.icon(
      onPressed: onPressed,
      icon: Icon(icon, color: FacelessTheme.danger),
      label: Text(label,
          style: const TextStyle(
            color: FacelessTheme.danger,
            fontWeight: FontWeight.w600,
          )),
      style: OutlinedButton.styleFrom(
        side: BorderSide(
          color: FacelessTheme.danger.withValues(alpha: 0.5),
        ),
        padding: const EdgeInsets.symmetric(vertical: 14),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
      ),
    );
  }
}


/// Drop-in `FacelessSettings` replacement for the Test Connection flow that
/// keeps the URL in memory only. The Test button must NEVER write to the
/// keychain — a failing test would otherwise persist bad credentials.
class _EphemeralSettings implements FacelessSettings {
  final String _baseUrl;
  _EphemeralSettings({required String baseUrl}) : _baseUrl = baseUrl;

  @override
  Future<String?> baseUrl() async => _baseUrl;
  @override
  Future<String?> tokenForLegacyMode() async =>
      FacelessConfig.apiToken.isNotEmpty ? FacelessConfig.apiToken : null;
  @override
  Future<bool> isConfigured() async => _baseUrl.isNotEmpty;
  @override
  Future<bool> isUsingBakedDefaults() async => false;

  // Writes are no-ops — that's the whole point.
  @override
  Future<void> save({required String baseUrl}) async {}
  @override
  Future<void> clear() async {}
}
