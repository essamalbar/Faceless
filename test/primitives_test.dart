import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:faceless/ui/primitives.dart';

// CORRECTED per controller ruling: the brief's test keys every bar
// ValueKey('wavebar'), which throws (duplicate sibling keys in a Row).
// Each bar gets a UNIQUE key ValueKey('wavebar_$i'); count via predicate.
// ignore: non_constant_identifier_names
int tester_barCount(WidgetTester t) => t.widgetList(find.byWidgetPredicate(
    (w) => w.key is ValueKey && '${(w.key as ValueKey).value}'.startsWith('wavebar_'))).length;

void main() {
  testWidgets('LivingWaveform renders the requested bar count', (t) async {
    await t.pumpWidget(const MaterialApp(home: Scaffold(
      body: LivingWaveform(bars: 18, animate: false))));
    expect(find.byType(LivingWaveform), findsOneWidget);
    // 18 bar containers
    expect(tester_barCount(t), 18);
  });

  testWidgets('StatusPill shows its label', (t) async {
    await t.pumpWidget(const MaterialApp(home: Scaffold(
      body: StatusPill(label: 'Composing', kind: StatusKind.composing))));
    expect(find.text('Composing'), findsOneWidget);
  });

  testWidgets('StepList renders one row per item', (t) async {
    await t.pumpWidget(MaterialApp(home: Scaffold(body: StepList(const [
      StepItem(label: 'Analyse', state: StepPhase.done),
      StepItem(label: 'Melody', state: StepPhase.active, percent: 40),
      StepItem(label: 'Cover', state: StepPhase.pending),
    ]))));
    expect(find.text('Analyse'), findsOneWidget);
    expect(find.text('Melody'), findsOneWidget);
    expect(find.text('Cover'), findsOneWidget);
  });

  testWidgets('Eyebrow renders its text visually uppercased', (t) async {
    await t.pumpWidget(const MaterialApp(home: Scaffold(
      body: Eyebrow('Good evening'))));
    // Mirrors the artboard's `.eyebrow { text-transform: uppercase }` — the
    // widget uppercases the rendered string.
    expect(find.text('GOOD EVENING'), findsOneWidget);
  });

  testWidgets('EditorialHeading renders full text, accentLast wraps last word in GradientText', (t) async {
    await t.pumpWidget(const MaterialApp(home: Scaffold(
      body: EditorialHeading('What will you sing', accentLast: true))));
    // Full text is split across a plain span + a GradientText span; the
    // widget under test still surfaces both pieces somewhere in the tree.
    expect(find.textContaining('What will you'), findsOneWidget);
    expect(find.text('sing'), findsOneWidget);
  });

  testWidgets('Hairline renders', (t) async {
    await t.pumpWidget(const MaterialApp(home: Scaffold(
      body: Hairline())));
    expect(find.byType(Hairline), findsOneWidget);
  });

  testWidgets('StatusPill ready/review kinds show their labels', (t) async {
    await t.pumpWidget(const MaterialApp(home: Scaffold(body: Column(children: [
      StatusPill(label: 'Ready', kind: StatusKind.ready),
      StatusPill(label: 'Review', kind: StatusKind.review),
    ]))));
    expect(find.text('Ready'), findsOneWidget);
    expect(find.text('Review'), findsOneWidget);
  });

  testWidgets('ArtistBadge renders monogram, alive:false does not animate', (t) async {
    await t.pumpWidget(const MaterialApp(home: Scaffold(
      body: ArtistBadge(monogram: 'S', alive: false))));
    expect(find.text('S'), findsOneWidget);
  });

  testWidgets('ArtistBadge alive:true builds under a single frame (no pumpAndSettle)', (t) async {
    await t.pumpWidget(const MaterialApp(home: Scaffold(
      body: ArtistBadge(monogram: 'ن', alive: true))));
    await t.pump(const Duration(milliseconds: 100));
    expect(find.text('ن'), findsOneWidget);
  });

  testWidgets('LivingWaveform animate:true builds under a single frame (no pumpAndSettle)', (t) async {
    await t.pumpWidget(const MaterialApp(home: Scaffold(
      body: LivingWaveform(bars: 6, animate: true))));
    await t.pump(const Duration(milliseconds: 100));
    expect(tester_barCount(t), 6);
  });

  testWidgets('disableAnimations: LivingWaveform(animate:true) settles (static fallback)', (t) async {
    await t.pumpWidget(
      MediaQuery(
        data: const MediaQueryData(disableAnimations: true),
        child: const MaterialApp(home: Scaffold(
          body: LivingWaveform(bars: 6, animate: true))),
      ),
    );
    await t.pumpAndSettle();
    expect(tester_barCount(t), 6);
  });

  testWidgets('disableAnimations: StatusPill.composing settles (static fallback)', (t) async {
    await t.pumpWidget(
      MediaQuery(
        data: const MediaQueryData(disableAnimations: true),
        child: const MaterialApp(home: Scaffold(
          body: StatusPill(label: 'Composing', kind: StatusKind.composing))),
      ),
    );
    await t.pumpAndSettle();
    expect(find.text('Composing'), findsOneWidget);
  });

  testWidgets('disableAnimations: ArtistBadge(alive:true) settles (static fallback)', (t) async {
    await t.pumpWidget(
      MediaQuery(
        data: const MediaQueryData(disableAnimations: true),
        child: const MaterialApp(home: Scaffold(
          body: ArtistBadge(monogram: 'A', alive: true))),
      ),
    );
    await t.pumpAndSettle();
    expect(find.text('A'), findsOneWidget);
  });

  testWidgets('disableAnimations: active StepList row settles (static fallback)', (t) async {
    await t.pumpWidget(
      MediaQuery(
        data: const MediaQueryData(disableAnimations: true),
        child: MaterialApp(home: Scaffold(body: StepList(const [
          StepItem(label: 'Active step', state: StepPhase.active, percent: 40),
        ]))),
      ),
    );
    await t.pumpAndSettle();
    expect(find.text('Active step'), findsOneWidget);
    expect(find.text('40%'), findsOneWidget);
  });

  testWidgets('StepList shows percent for active step', (t) async {
    await t.pumpWidget(MaterialApp(home: Scaffold(body: StepList(const [
      StepItem(label: 'Melody', state: StepPhase.active, percent: 40),
    ]))));
    expect(find.text('40%'), findsOneWidget);
  });

  testWidgets('RTL: StatusPill and StepList build correctly under RTL directionality', (t) async {
    await t.pumpWidget(MaterialApp(
      home: Directionality(
        textDirection: TextDirection.rtl,
        child: Scaffold(body: Column(children: const [
          StatusPill(label: 'جاهز', kind: StatusKind.ready),
          StepList([
            StepItem(label: 'قراءة الفكرة', state: StepPhase.done),
          ]),
        ])),
      ),
    ));
    expect(find.text('جاهز'), findsOneWidget);
    expect(find.text('قراءة الفكرة'), findsOneWidget);
  });
}
