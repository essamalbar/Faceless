/// l10n access + persisted locale choice.
///
/// `context.l10n` returns the generated AppLocalizations. LocaleController
/// holds the app-wide language override (null = follow device), persisted in
/// shared_preferences, and is bound to MaterialApp.locale in main.dart so a
/// change rebuilds the whole app instantly (no restart).
library;

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app_localizations.dart';

export 'app_localizations.dart';

extension L10nX on BuildContext {
  AppLocalizations get l10n => AppLocalizations.of(this)!;
}

/// App-wide locale override. null = follow device. Persisted.
class LocaleController extends ValueNotifier<Locale?> {
  LocaleController._(super.value);
  static const _prefsKey = 'faceless.locale';
  static final LocaleController instance = LocaleController._(null);

  static Future<void> load() async {
    try {
      final sp = await SharedPreferences.getInstance();
      final code = sp.getString(_prefsKey);
      if (code == 'ar' || code == 'en') {
        instance.value = Locale(code!);
      }
    } catch (_) {
      // Corrupt/unavailable prefs → follow device.
    }
  }

  Future<void> set(Locale? locale) async {
    value = locale;
    try {
      final sp = await SharedPreferences.getInstance();
      if (locale == null) {
        await sp.remove(_prefsKey);
      } else {
        await sp.setString(_prefsKey, locale.languageCode);
      }
    } catch (_) {
      // Persisting is best-effort; the in-memory switch already applied.
    }
  }
}

/// Localized label for a backend run/song status code. Unknown codes render
/// raw — they're debug text by definition.
String statusLabel(AppLocalizations l10n, String status) => switch (status) {
      'analyzing' => l10n.statusAnalyzing,
      'awaiting_approval' => l10n.statusAwaitingApproval,
      'generating_song' => l10n.statusGeneratingSong,
      'generating_cover' => l10n.statusGeneratingCover,
      'assembling' => l10n.statusAssembling,
      'complete' => l10n.statusComplete,
      'failed' => l10n.statusFailed,
      'running' => l10n.statusRunning,
      'cancelled' => l10n.statusCancelled,
      _ => status,
    };
