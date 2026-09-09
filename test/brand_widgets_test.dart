import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:faceless/ui/brand.dart';

const _forbidden = [0xFFFF4D8D, 0xFFA25BFF, 0xFF7C3AED, 0xFFCF54C0]; // old neon

// The jewel set from the brief, verbatim (teal / bronze / garnet / emerald).
// A positive allow-list, not just a negative check against `_forbidden` —
// `_forbidden` alone can't distinguish the jewel palette from the old
// dark-neon `coverGradient` (its plum/indigo entries never matched those
// exact hex values), so this is what actually pins the requirement down.
const _jewelSet = [
  0xFF233A44, 0xFF2E7A6E, // teal
  0xFF3E2E1C, 0xFFA0762E, // bronze
  0xFF3A1E1C, 0xFF7A3A2E, // garnet
  0xFF1F3A30, 0xFF2E7A5C, // emerald
];

void main() {
  testWidgets('brand widgets build', (t) async {
    await t.pumpWidget(const MaterialApp(home: Scaffold(body: MeshBackground(
      child: GlassCard(child: Text('x'))))));
    expect(find.text('x'), findsOneWidget);
  });

  testWidgets('disableAnimations: MeshBackground settles (static fallback, no ticker)',
      (t) async {
    await t.pumpWidget(
      MediaQuery(
        data: const MediaQueryData(disableAnimations: true),
        child: const MaterialApp(
          home: Scaffold(body: MeshBackground(child: Text('static'))),
        ),
      ),
    );
    // pumpAndSettle only completes if no ticker is left running — this is
    // the regression guard for the static fallback Tasks 4-8 rely on.
    await t.pumpAndSettle();
    expect(find.text('static'), findsOneWidget);
  });

  testWidgets('animations enabled: MeshBackground still builds its child',
      (t) async {
    await t.pumpWidget(const MaterialApp(
      home: Scaffold(body: MeshBackground(child: Text('animated'))),
    ));
    // Must NOT use pumpAndSettle here — the breathe animation runs an
    // infinite repeating ticker and pumpAndSettle would hang waiting for
    // the frame schedule to go idle.
    await t.pump(const Duration(milliseconds: 100));
    expect(find.text('animated'), findsOneWidget);
  });

  testWidgets('GradientButton exposes button semantics (enabled)', (t) async {
    final handle = t.ensureSemantics();
    await t.pumpWidget(MaterialApp(home: Scaffold(body: GradientButton(
      label: 'Go', onPressed: () {}))));
    expect(
      t.getSemantics(find.text('Go')),
      isSemantics(
        isButton: true,
        hasEnabledState: true,
        isEnabled: true,
        hasTapAction: true,
      ),
    );
    handle.dispose();
  });

  testWidgets('GradientButton exposes button semantics (disabled)', (t) async {
    final handle = t.ensureSemantics();
    await t.pumpWidget(const MaterialApp(home: Scaffold(body: GradientButton(
      label: 'Go', onPressed: null))));
    expect(
      t.getSemantics(find.text('Go')),
      isSemantics(
        isButton: true,
        hasEnabledState: true,
        isEnabled: false,
      ),
    );
    handle.dispose();
  });

  test('coverGradient uses jewel set, never violet/pink', () {
    for (final s in ['a','song','رحلة','xyz','12','artist']) {
      final g = coverGradient(s);
      for (final c in g.colors) {
        expect(_forbidden.contains(c.toARGB32()), isFalse,
          reason: 'no neon in cover gradients');
        expect(_jewelSet.contains(c.toARGB32()), isTrue,
          reason: 'coverGradient must use only the jewel set from the brief');
      }
    }
  });
}
