/// Faceless brand theme — light, premium, calm. Soft pastel gradient
/// background (warm cream → cool lavender), frosted white cards with soft
/// shadows, dark ink text, a restrained green accent, charcoal buttons.
/// Modeled on the approved reference. A global pastel background sits behind
/// every screen (main.dart's MaterialApp.builder + ui/brand.dart MeshBackground).
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class FacelessTheme {
  // --- Palette (light) --------------------------------------------------
  static const bg = Color(0xFFF4F1F7); // light base (mesh paints the gradient)
  static const surface = Color(0xFFFFFFFF); // white card
  static const surface2 = Color(0xFFF4F2EC); // soft warm/sand secondary
  static const accent = Color(0xFF2FA36B); // restrained green (primary accent)
  static const accent2 = Color(0xFF38BFA6); // teal (gradient/wave secondary)
  static const accentMid = Color(0xFF33AF89); // between (gradient middle)
  static const ink = Color(0xFF232636); // charcoal — primary buttons
  static const textPrimary = Color(0xFF1B1E28); // near-black
  static const textSecondary = Color(0xFF767C8C);
  static const faint = Color(0xFFA2A7B4);
  static const danger = Color(0xFFE5484D);
  static const success = Color(0xFF2FA36B);
  static const warning = Color(0xFFE39A2B);
  static const info = Color(0xFF3B82F6);

  // Soft green→teal used for the logo mark, accent headline words, dots.
  static const brandGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF34A473), accent2],
  );

  // Frosted-white surfaces + hairline borders over the pastel background.
  static Color get glass => Colors.white.withValues(alpha: 0.72);
  static Color get glassStrong => Colors.white.withValues(alpha: 0.86);
  static Color get border => Colors.black.withValues(alpha: 0.07);
  static List<BoxShadow> get softShadow => [
        BoxShadow(
          color: const Color(0xFF1E2046).withValues(alpha: 0.08),
          blurRadius: 34,
          offset: const Offset(0, 12),
        ),
      ];

  /// Space Grotesk display/heading style (dark ink, Cairo fallback for Arabic).
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

  static ThemeData build({Locale? locale}) {
    final isArabic = locale?.languageCode == 'ar';
    final base = ThemeData.light(useMaterial3: true);
    final scheme = ColorScheme.fromSeed(
      seedColor: accent,
      brightness: Brightness.light,
      surface: surface,
      primary: ink,
      secondary: accent,
      error: danger,
    ).copyWith(surfaceContainerHighest: surface2);

    // Arabic UI: Cairo primary (Inter fallback for Latin snippets).
    // English UI: Inter primary (Cairo fallback for Arabic content).
    final cairo = GoogleFonts.cairo().fontFamily;
    final inter = GoogleFonts.inter().fontFamily;
    final textTheme = (isArabic
            ? GoogleFonts.cairoTextTheme(base.textTheme)
            : GoogleFonts.interTextTheme(base.textTheme))
        .apply(
      bodyColor: textPrimary,
      displayColor: textPrimary,
      fontFamilyFallback: [
        if (isArabic && inter != null) inter,
        if (!isArabic && cairo != null) cairo,
      ],
    );

    return base.copyWith(
      colorScheme: scheme,
      // Transparent so the global MeshBackground (main.dart) shows through.
      scaffoldBackgroundColor: Colors.transparent,
      canvasColor: Colors.transparent,
      textTheme: textTheme,
      cardTheme: CardThemeData(
        color: surface,
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
        foregroundColor: textPrimary,
        iconTheme: IconThemeData(color: textPrimary),
        titleTextStyle: TextStyle(
            color: textPrimary, fontSize: 18, fontWeight: FontWeight.w600),
      ),
      iconTheme: const IconThemeData(color: textPrimary),
      dividerTheme: DividerThemeData(color: border, thickness: 1),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: ink,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 15),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(13)),
          textStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: ink,
          foregroundColor: Colors.white,
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 15),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(13)),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: textPrimary,
          backgroundColor: Colors.white,
          side: BorderSide(color: border),
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 13),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(13)),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(foregroundColor: ink),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: Colors.white,
        side: BorderSide(color: border),
        labelStyle: const TextStyle(color: textPrimary, fontSize: 13),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
      ),
      segmentedButtonTheme: SegmentedButtonThemeData(
        style: ButtonStyle(
          backgroundColor: WidgetStateProperty.resolveWith(
            (s) => s.contains(WidgetState.selected) ? ink : Colors.white,
          ),
          foregroundColor: WidgetStateProperty.resolveWith(
            (s) => s.contains(WidgetState.selected) ? Colors.white : textSecondary,
          ),
          side: WidgetStateProperty.all(BorderSide(color: border)),
          shape: WidgetStateProperty.all(RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12))),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
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
        colors: [Colors.transparent, Color(0x11000000), Color(0x22000000)],
        stops: [0.0, 0.7, 1.0],
      );

  static BoxDecoration cardGradient({Color? tint}) => BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        color: surface,
        border: Border.all(color: border),
        boxShadow: softShadow,
      );
}
