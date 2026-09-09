import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:faceless/l10n/l10n.dart';
import 'package:faceless/ui/primitives.dart';
import 'package:faceless/widgets/composing_view.dart';

void main() {
  // ComposingView is always used inside a scrollable (run_detail_screen's
  // ListView) — wrap it the same way here, or its natural height overflows
  // the fixed 600px test viewport.
  Widget app(Locale locale, Widget child) => MaterialApp(
        locale: locale,
        supportedLocales: const [Locale('en'), Locale('ar')],
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        home: Scaffold(body: SingleChildScrollView(child: child)),
      );

  const steps = [
    StepItem(label: 'Reading the idea', state: StepPhase.done),
    StepItem(label: 'Writing lyrics', state: StepPhase.done),
    StepItem(label: 'Generating melody', state: StepPhase.active, percent: 40),
    StepItem(label: 'Designing cover', state: StepPhase.pending),
    StepItem(label: 'Final assembly', state: StepPhase.pending),
  ];

  // ComposingView embeds several infinite-animation primitives (LivingWaveform,
  // ArtistBadge(alive:true), the active StepList row) — always `pump()`, never
  // `pumpAndSettle()` (it would hang waiting for an animation that never ends).
  testWidgets('renders hero, subtitle, steps and footer in English (LTR)',
      (t) async {
    await t.pumpWidget(app(
      const Locale('en'),
      const ComposingView(
        monogram: 'N',
        artistName: 'Nour Al-Layl',
        title: 'Night in the Neighborhood',
        steps: steps,
      ),
    ));
    await t.pump(const Duration(milliseconds: 100));

    expect(find.text('N'), findsOneWidget);
    expect(find.text('NOW'), findsOneWidget); // Eyebrow uppercases "Now"
    expect(find.textContaining('Nour Al-Layl'), findsOneWidget);
    expect(find.textContaining('Night in the Neighborhood'), findsOneWidget);
    expect(find.text('Generating melody'), findsOneWidget);
    expect(find.text('40%'), findsOneWidget);
  });

  testWidgets('renders under Arabic RTL and wires the cancel action',
      (t) async {
    var cancelled = false;
    await t.pumpWidget(app(
      const Locale('ar'),
      ComposingView(
        monogram: 'ن',
        title: 'ليلة في الحي',
        steps: steps,
        onCancel: () => cancelled = true,
      ),
    ));
    await t.pump(const Duration(milliseconds: 100));

    final ctx = t.element(find.byType(ComposingView));
    expect(Directionality.of(ctx), TextDirection.rtl);
    expect(find.text('ن'), findsOneWidget);
    expect(find.text('ليلة في الحي'), findsOneWidget);

    // The cancel button sits below the fold of the fixed test viewport
    // (ComposingView is long — hero + waveform + 5 steps + footer), same
    // as it would in a short real device window inside the ListView.
    await t.ensureVisible(find.byIcon(Icons.delete_forever));
    await t.pump();
    await t.tap(find.byIcon(Icons.delete_forever));
    await t.pump();
    expect(cancelled, isTrue);
  });

  testWidgets('omits the subtitle line and cancel button when not provided',
      (t) async {
    await t.pumpWidget(app(
      const Locale('en'),
      const ComposingView(monogram: 'X', steps: steps),
    ));
    await t.pump(const Duration(milliseconds: 100));

    expect(find.byIcon(Icons.delete_forever), findsNothing);
  });

  testWidgets('disableAnimations: settles without a real cancel wired',
      (t) async {
    await t.pumpWidget(
      MediaQuery(
        data: const MediaQueryData(disableAnimations: true),
        child: app(
          const Locale('en'),
          const ComposingView(monogram: 'N', steps: steps),
        ),
      ),
    );
    await t.pumpAndSettle();
    expect(find.byType(ComposingView), findsOneWidget);
  });
}
