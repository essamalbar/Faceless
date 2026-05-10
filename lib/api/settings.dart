/// Encrypted local store for the API base URL.
///
/// Auth tokens are now managed by Supabase (since B2). The legacy bearer
/// token is kept ONLY for backwards-compatibility with launches that don't
/// pass `--dart-define=SUPABASE_URL/_ANON_KEY` — in that mode, the app
/// falls back to the dart-define `FACELESS_API_TOKEN` baked in by the
/// launcher script. Once every dev launches via run-app.sh with Supabase
/// configured, the legacy path can be removed.
///
/// Resolution order for baseUrl:
///   1. user-saved value in secure storage (override)
///   2. compile-time default from `--dart-define` (zero-config launch)
///   3. null (forces Settings screen)
library;

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../config.dart';

class FacelessSettings {
  static const _kBaseUrl = 'faceless.base_url';

  final FlutterSecureStorage _store;

  FacelessSettings({FlutterSecureStorage? store})
      : _store = store ?? const FlutterSecureStorage();

  Future<String?> baseUrl() async {
    final saved = await _store.read(key: _kBaseUrl);
    if (saved != null && saved.isNotEmpty) return saved;
    return FacelessConfig.apiUrl.isNotEmpty ? FacelessConfig.apiUrl : null;
  }

  /// Legacy fallback used by FacelessApiClient when Supabase isn't initialized.
  /// Returns the dart-define-baked FACELESS_API_TOKEN if present; otherwise null.
  /// Once Supabase is fully wired in production, this and the FacelessConfig
  /// constant can be removed.
  Future<String?> tokenForLegacyMode() async {
    return FacelessConfig.apiToken.isNotEmpty
        ? FacelessConfig.apiToken
        : null;
  }

  Future<void> save({required String baseUrl}) async {
    await _store.write(key: _kBaseUrl, value: baseUrl.trim());
  }

  Future<bool> isConfigured() async {
    final b = await baseUrl();
    return b != null && b.isNotEmpty;
  }

  /// True when settings come purely from --dart-define (no user override
  /// saved). Used by the Settings screen to show "(provisioned by launcher)".
  Future<bool> isUsingBakedDefaults() async {
    final savedUrl = await _store.read(key: _kBaseUrl);
    final noOverride = savedUrl == null || savedUrl.isEmpty;
    return noOverride && FacelessConfig.apiUrl.isNotEmpty;
  }

  Future<void> clear() async {
    await _store.delete(key: _kBaseUrl);
  }
}
