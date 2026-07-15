import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// Enforces full bilingualism: both ARB files expose exactly the same keys
/// and no translation is empty. A missing Arabic string is a broken build,
/// not a mixed-language UI.
void main() {
  test('ARB files have identical keys and no empty values', () {
    final en = jsonDecode(File('lib/l10n/app_en.arb').readAsStringSync())
        as Map<String, dynamic>;
    final ar = jsonDecode(File('lib/l10n/app_ar.arb').readAsStringSync())
        as Map<String, dynamic>;

    Set<String> keys(Map<String, dynamic> m) =>
        m.keys.where((k) => !k.startsWith('@')).toSet();

    expect(keys(ar), keys(en),
        reason: 'app_ar.arb and app_en.arb must define the same keys');

    for (final m in [en, ar]) {
      for (final e in m.entries) {
        if (e.key.startsWith('@')) continue;
        expect((e.value as String).trim(), isNotEmpty,
            reason: 'translation for "${e.key}" is empty');
      }
    }
  });
}
