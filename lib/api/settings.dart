/// Encrypted local store for the API base URL + bearer token.
///
/// Uses flutter_secure_storage so the bearer token is stored in iOS Keychain
/// / Android Keystore (encrypted at rest) rather than SharedPreferences.
///
/// Resolution order when reading:
///   1. user-saved value in secure storage (override)
///   2. compile-time default from `--dart-define` (zero-config launch)
///   3. null (forces Settings screen)
library;

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../config.dart';

class FacelessSettings {
  static const _kBaseUrl = 'faceless.base_url';
  static const _kToken = 'faceless.token';

  final FlutterSecureStorage _store;

  FacelessSettings({FlutterSecureStorage? store})
      : _store = store ?? const FlutterSecureStorage();

  Future<String?> baseUrl() async {
    final saved = await _store.read(key: _kBaseUrl);
    if (saved != null && saved.isNotEmpty) return saved;
    return FacelessConfig.apiUrl.isNotEmpty ? FacelessConfig.apiUrl : null;
  }

  Future<String?> token() async {
    final saved = await _store.read(key: _kToken);
    if (saved != null && saved.isNotEmpty) return saved;
    return FacelessConfig.apiToken.isNotEmpty ? FacelessConfig.apiToken : null;
  }

  Future<void> save({required String baseUrl, required String token}) async {
    await _store.write(key: _kBaseUrl, value: baseUrl.trim());
    await _store.write(key: _kToken, value: token.trim());
  }

  Future<bool> isConfigured() async {
    final b = await baseUrl();
    final t = await token();
    return b != null && b.isNotEmpty && t != null && t.isNotEmpty;
  }

  /// True when settings come purely from --dart-define (no user override
  /// saved). Used by the Settings screen to show "(provisioned by launcher)".
  Future<bool> isUsingBakedDefaults() async {
    final savedUrl = await _store.read(key: _kBaseUrl);
    final savedToken = await _store.read(key: _kToken);
    final noOverride = (savedUrl == null || savedUrl.isEmpty) &&
        (savedToken == null || savedToken.isEmpty);
    return noOverride && FacelessConfig.hasBakedDefaults;
  }

  Future<void> clear() async {
    await _store.delete(key: _kBaseUrl);
    await _store.delete(key: _kToken);
  }
}
