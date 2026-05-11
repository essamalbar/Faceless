import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../api/client.dart';
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

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final url = await _settings.baseUrl();
    if (mounted) {
      _urlCtrl.text = url ?? '';
      setState(() {});
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
    // Reload to show the dart-define default if any
    final url = await _settings.baseUrl();
    if (mounted) {
      _urlCtrl.text = url ?? '';
      setState(() => _testResult = '✓ Reset — using launcher defaults');
    }
  }

  Future<void> _signOut() async {
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
      appBar: AppBar(
        title: const Text('Settings'),
        leading: widget.firstLaunch ? null : null,
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (widget.firstLaunch)
                  Card(
                    color: Theme.of(context).colorScheme.secondaryContainer,
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Text(
                        'First-time setup. Paste your Cloudflare Tunnel URL '
                        '(or Mac LAN IP if on home WiFi).',
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                    ),
                  ),
                const SizedBox(height: 16),
                TextFormField(
                  controller: _urlCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Server URL',
                    hintText: 'https://xyz.trycloudflare.com',
                    border: OutlineInputBorder(),
                  ),
                  keyboardType: TextInputType.url,
                  autocorrect: false,
                  validator: (v) {
                    if (v == null || v.trim().isEmpty) return 'required';
                    if (!v.startsWith('http')) return 'must start with http:// or https://';
                    return null;
                  },
                ),
                const SizedBox(height: 24),
                if (_testResult != null)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Text(
                      _testResult!,
                      style: TextStyle(
                        color: _testResult!.startsWith('✓')
                            ? Colors.green
                            : Theme.of(context).colorScheme.error,
                      ),
                    ),
                  ),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: _loading ? null : _testConnection,
                        icon: const Icon(Icons.wifi_tethering),
                        label: const Text('Test'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: FilledButton.icon(
                        onPressed: _loading ? null : _save,
                        icon: const Icon(Icons.save),
                        label: const Text('Save'),
                      ),
                    ),
                  ],
                ),
                if (FacelessConfig.apiUrl.isNotEmpty) ...[
                  const SizedBox(height: 16),
                  const Divider(height: 1),
                  const SizedBox(height: 12),
                  TextButton.icon(
                    onPressed: _loading ? null : _resetToDefaults,
                    icon: const Icon(Icons.restart_alt,
                        color: FacelessTheme.danger),
                    label: const Text(
                      'Reset to launcher defaults',
                      style: TextStyle(color: FacelessTheme.danger),
                    ),
                  ),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                    child: Text(
                      'Use this when the tunnel URL has changed. Clears '
                      'the saved value; next launch will use whatever '
                      'run-app.sh provides via --dart-define.',
                      style: TextStyle(
                        color: Theme.of(context)
                            .colorScheme
                            .onSurfaceVariant
                            .withValues(alpha: 0.7),
                        fontSize: 11,
                      ),
                    ),
                  ),
                ],
                const SizedBox(height: 24),
                const Divider(),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.monetization_on,
                                     color: FacelessTheme.accent),
                  title: const Text('Billing'),
                  subtitle: const Text('Manage your subscription and credits'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => const BillingScreen()),
                  ),
                ),
                const SizedBox(height: 16),
                OutlinedButton.icon(
                  icon: const Icon(Icons.logout),
                  label: const Text('Sign out'),
                  onPressed: _loading ? null : _signOut,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    _urlCtrl.dispose();
    super.dispose();
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
