/// Faceless brand theme — modern dark "glass" surface with a violet→pink
/// signature gradient, Space Grotesk (display) + Inter (body) type, Cairo
/// fallback for Arabic. A global mesh-gradient background sits behind every
/// screen (see main.dart's MaterialApp.builder + ui/brand.dart MeshBackground).
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class FacelessTheme {
  // --- Palette ----------------------------------------------------------
  static const bg = Color(0xFF07070C); // deep near-black
  static const surface = Color(0xFF14141E); // card / chip fill
  static const surface2 = Color(0xFF1C1C2A); // raised
  static const accent = Color(0xFF8B7CFF); // violet (primary)
  static const accent2 = Color(0xFFFF5C9A); // pink (secondary)
  static const accentMid = Color(0xFFB14BF4); // purple (gradient middle)
  static const textPrimary = Color(0xFFF5F6FA);
  static const textSecondary = Color(0xFF9AA0B4);
  static const faint = Color(0xFF6B7085);
  static const danger = Color(0xFFFF5C6C);
  static const success = Color(0xFF34D399);
  static const warning = Color(0xFFFBBF24);
  static const info = Color(0xFF54E6FF);

  // Signature gradient — logo, headlines, primary buttons, accents.
  static const brandGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF7C5CFF), accentMid, accent2],
  );

  // Glass fill/border used by cards, chips, inputs over the mesh.
  static Color get glass => Colors.white.withValues(alpha: 0.045);
  static Color get glassStrong => Colors.white.withValues(alpha: 0.07);
  static Color get border => Colors.white.withValues(alpha: 0.09);

  /// Space Grotesk display/heading style (with Arabic Cairo fallback).
  static TextStyle display({
    double size = 28,
    FontWeight weight = FontWeight.w700,
    Color? color,
    double height = 1.05,
    double letterSpacing = -0.5,
  }) =>
      GoogleFonts.spaceGrotesk(
        fontSize: size,
        fontWeight: weight,
        height: height,
        letterSpacing: letterSpacing,
        color: color ?? textPrimary,
      ).copyWith(fontFamilyFallback: const ['Cairo']);

  static ThemeData build() {
    final base = ThemeData.dark(useMaterial3: true);
    final scheme = ColorScheme.fromSeed(
      seedColor: accent,
      brightness: Brightness.dark,
      surface: surface,
      primary: accent,
      secondary: accent2,
      error: danger,
    ).copyWith(surfaceContainerHighest: surface2);

    // Body type = Inter, Arabic falls back to Cairo (loaded by google_fonts).
    final cairo = GoogleFonts.cairo().fontFamily;
    final textTheme = GoogleFonts.interTextTheme(base.textTheme).apply(
      bodyColor: textPrimary,
      displayColor: textPrimary,
      fontFamilyFallback: [if (cairo != null) cairo],
    );

    return base.copyWith(
      colorScheme: scheme,
      // Transparent so the global MeshBackground (main.dart) shows through.
      scaffoldBackgroundColor: Colors.transparent,
      canvasColor: Colors.transparent,
      textTheme: textTheme,
      cardTheme: CardThemeData(
        color: glass,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: BorderSide(color: border),
        ),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
      ),
      dividerTheme: DividerThemeData(color: border, thickness: 1),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: accent,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 15),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(13)),
          textStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: accent,
          foregroundColor: Colors.white,
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 15),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(13)),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: textPrimary,
          backgroundColor: Colors.white.withValues(alpha: 0.05),
          side: BorderSide(color: border),
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 13),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(13)),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(foregroundColor: accent),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: glassStrong,
        side: BorderSide(color: border),
        labelStyle: const TextStyle(color: textPrimary, fontSize: 13),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
      ),
      segmentedButtonTheme: SegmentedButtonThemeData(
        style: ButtonStyle(
          backgroundColor: WidgetStateProperty.resolveWith(
            (s) => s.contains(WidgetState.selected)
                ? accent.withValues(alpha: 0.22)
                : Colors.transparent,
          ),
          side: WidgetStateProperty.all(BorderSide(color: border)),
          shape: WidgetStateProperty.all(RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12))),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.black.withValues(alpha: 0.25),
        hintStyle: const TextStyle(color: faint),
        labelStyle: const TextStyle(color: textSecondary),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 15),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(13),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(13),
          borderSide: BorderSide(color: border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(13),
          borderSide: const BorderSide(color: accent, width: 1.6),
        ),
      ),
    );
  }

  // --- Legacy helpers kept for existing screens -------------------------
  static LinearGradient get heroGradient => const LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [Colors.transparent, Color(0xCC07070C), bg],
        stops: [0.0, 0.7, 1.0],
      );

  static BoxDecoration cardGradient({Color? tint}) => BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [(tint ?? accentMid).withValues(alpha: 0.20), surface],
        ),
        border: Border.all(color: border),
      );
}
