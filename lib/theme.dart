/// Shahid-style dark theme — deep navy backgrounds, accent gold for premium
/// feel, Cairo Arabic font, generous spacing, soft elevation.
library;

import 'package:flutter/material.dart';

class FacelessTheme {
  // Palette — inspired by Shahid VIP / Netflix dark
  static const bg = Color(0xFF0A0E1A);          // near-black navy
  static const surface = Color(0xFF141A2A);     // card / chip
  static const surface2 = Color(0xFF1E2638);    // raised
  static const accent = Color(0xFFE7B53C);      // warm gold
  static const accent2 = Color(0xFF8B5CF6);     // violet
  static const textPrimary = Color(0xFFEDEEF3);
  static const textSecondary = Color(0xFF9AA3B7);
  static const danger = Color(0xFFEF4444);
  static const success = Color(0xFF10B981);
  static const warning = Color(0xFFF59E0B);
  static const info = Color(0xFF3B82F6);

  static ThemeData build() {
    final base = ThemeData.dark(useMaterial3: true);
    final scheme = ColorScheme.fromSeed(
      seedColor: accent,
      brightness: Brightness.dark,
      surface: surface,
      primary: accent,
      secondary: accent2,
      error: danger,
    ).copyWith(
      surfaceContainerHighest: surface2,
    );
    return base.copyWith(
      colorScheme: scheme,
      scaffoldBackgroundColor: bg,
      canvasColor: bg,
      cardTheme: CardThemeData(
        color: surface,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: accent,
          foregroundColor: Colors.black,
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          textStyle: const TextStyle(fontWeight: FontWeight.w600),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: textPrimary,
          side: BorderSide(color: textSecondary.withValues(alpha: 0.3)),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surface,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide(color: textSecondary.withValues(alpha: 0.2)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: accent, width: 2),
        ),
      ),
      // System default Arabic-capable font on each platform. Adding the
      // Cairo TTF as a bundled asset is a future improvement.
      textTheme: base.textTheme
          .apply(
            bodyColor: textPrimary,
            displayColor: textPrimary,
            fontFamily: 'system-ui',
          ),
    );
  }

  static LinearGradient get heroGradient => const LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [Colors.transparent, Color(0xCC0A0E1A), bg],
        stops: [0.0, 0.7, 1.0],
      );

  static BoxDecoration cardGradient({Color? tint}) => BoxDecoration(
        borderRadius: BorderRadius.circular(14),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            (tint ?? accent2).withValues(alpha: 0.18),
            surface,
          ],
        ),
      );
}
