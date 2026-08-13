import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:faceless/l10n/l10n.dart';
import 'package:faceless/theme.dart';
import 'package:faceless/widgets/genre_grid.dart';

Widget _host(Widget child, {Locale locale = const Locale('en')}) => MaterialApp(
      locale: locale,
      theme: FacelessTheme.build(),
      supportedLocales: const [Locale('en'), Locale('ar')],
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      home: Scaffold(body: SingleChildScrollView(child: child)),
    );

void main() {
  testWidgets('renders Auto + universal genres for English', (t) async {
    await t.pumpWidget(_host(GenreGrid(
      selectedKey: null, language: 'en', onChanged: (_) {},
    )));
    await t.pumpAndSettle();
    expect(find.text('Auto'), findsOneWidget);
    expect(find.text('Pop'), findsOneWidget);
    expect(find.text('Khaleeji'), findsNothing); // arabic-only hidden for en
  });

  testWidgets('shows arabic-only genres for Arabic', (t) async {
    await t.pumpWidget(_host(
      GenreGrid(selectedKey: null, language: 'ar', onChanged: (_) {}),
      locale: const Locale('ar'),
    ));
    await t.pumpAndSettle();
    expect(find.text('خليجي'), findsOneWidget);
  });

  testWidgets('tapping a genre fires onChanged with its key', (t) async {
    String? picked = 'sentinel';
    await t.pumpWidget(_host(GenreGrid(
      selectedKey: null, language: 'en', onChanged: (k) => picked = k,
    )));
    await t.pumpAndSettle();
    await t.tap(find.text('Rock'));
    expect(picked, 'rock');
  });

  testWidgets('tapping Auto fires onChanged with null', (t) async {
    String? picked = 'rock';
    await t.pumpWidget(_host(GenreGrid(
      selectedKey: 'rock', language: 'en', onChanged: (k) => picked = k,
    )));
    await t.pumpAndSettle();
    await t.tap(find.text('Auto'));
    expect(picked, isNull);
  });
}
