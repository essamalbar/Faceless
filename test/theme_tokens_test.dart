import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:faceless/theme.dart';

void main() {
  test('palette is obsidian + champagne, no neon', () {
    expect(FacelessTheme.bg, const Color(0xFF0C0B0E));
    expect(FacelessTheme.accent, const Color(0xFFC9A96E)); // champagne
    expect(FacelessTheme.accent2, const Color(0xFFE4CE9E));
    expect(FacelessTheme.textPrimary, const Color(0xFFEFE9DE));
    // no pure white text
    expect(FacelessTheme.textPrimary, isNot(const Color(0xFFFFFFFF)));
  });

  // NOTE: FacelessTheme.build() resolves GoogleFonts text themes, which touch
  // ServicesBinding.instance (rootBundle) to check for locally-bundled font
  // assets. That binding only exists inside a widget-test zone (as in
  // test/dropdown_theme_test.dart), so these two checks use `testWidgets`
  // instead of a bare `test` — same assertions, just a binding-safe host.
  testWidgets('dropdown ground stays opaque (drop.png invariant)', (_) async {
    expect(FacelessTheme.build().canvasColor.a, 1.0);
    expect(FacelessTheme.surface.a, 1.0);
  });

  testWidgets('build() works for both locales', (_) async {
    expect(FacelessTheme.build(locale: const Locale('en')), isA<ThemeData>());
    expect(FacelessTheme.build(locale: const Locale('ar')), isA<ThemeData>());
  });
}
