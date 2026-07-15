import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:faceless/l10n/l10n.dart';

void main() {
  Widget app(Locale? l) => MaterialApp(
        locale: l,
        supportedLocales: const [Locale('en'), Locale('ar')],
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        home: Builder(
          builder: (c) => Scaffold(
            body: Text(c.l10n.settingsLanguage, key: const Key('probe')),
          ),
        ),
      );

  testWidgets('ar locale renders Arabic + RTL', (t) async {
    await t.pumpWidget(app(const Locale('ar')));
    await t.pumpAndSettle();
    expect(find.text('اللغة'), findsOneWidget);
    final ctx = t.element(find.byKey(const Key('probe')));
    expect(Directionality.of(ctx), TextDirection.rtl);
  });

  testWidgets('en locale renders English + LTR', (t) async {
    await t.pumpWidget(app(const Locale('en')));
    await t.pumpAndSettle();
    expect(find.text('Language'), findsOneWidget);
    final ctx = t.element(find.byKey(const Key('probe')));
    expect(Directionality.of(ctx), TextDirection.ltr);
  });

  testWidgets('statusLabel maps known codes and passes through unknown',
      (t) async {
    late AppLocalizations l10n;
    await t.pumpWidget(app(const Locale('ar')));
    await t.pumpAndSettle();
    l10n = AppLocalizations.of(t.element(find.byKey(const Key('probe'))))!;
    expect(statusLabel(l10n, 'complete'), 'مكتملة');
    expect(statusLabel(l10n, 'weird_code'), 'weird_code');
  });
}
