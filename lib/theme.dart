/// Faceless brand theme — glassy dark-neon. Near-black background lit by
/// blurred pink/purple/cyan glow, frosted translucent cards with bright glass
/// edges, a pink→purple gradient for primary actions + selection, Space
/// Grotesk display / Inter (Cairo for Arabic) body. A global neon-lit
/// background sits behind every screen (main.dart's MaterialApp.builder +
/// ui/brand.dart MeshBackground).
///
/// Token + widget NAMES are kept stable so screens inherit the look through
/// the shared layer without edits — only the VALUES changed from the old
/// light theme. See docs/superpowers/specs/2026-08-14-dark-neon-glass-design-system-design.md
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class FacelessTheme {
  // --- Palette (dark-neon) ----------------------------------------------
  static const bg = Color(0xFF0B0810); // near-black base (mesh paints glow)
  static const surface = Color(0xFF1A1327); // SOLID dark card / menu ground
  static const surface2 = Color(0xFF211830); // slightly lighter dark
  static const accent = Color(0xFFFF4D8D); // neon pink (primary accent)
  static const accent2 = Color(0xFFA25BFF); // neon purple (gradient secondary)
  static const accentMid = Color(0xFFCF54C0); // between (3-stop gradient middle)
  static const ink = Color(0xFF7C3AED); // deep neon violet — solid filled buttons
  static const textPrimary = Color(0xFFF5F0FB); // near-white
  static const textSecondary = Color(0xFFBEB0D6); // muted lavender
  static const faint = Color(0xFF84769C);
  static const danger = Color(0xFFFF5A67);
  static const success = Color(0xFF3FE0D0); // cyan-green, readable on dark
  static const warning = Color(0xFFFFC94D);
  static const info = Color(0xFF4D8DFF);

  // Pink→purple used for the logo mark, accent headline words, primary CTA.
  static const brandGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [accent, accent2],
  );

  // Frosted translucent surfaces + bright hairline borders over the neon glow.
  static Color get glass => Colors.white.withValues(alpha: 0.055);
  static Color get glassStrong => Colors.white.withValues(alpha: 0.10);
  static Color get border => Colors.white.withValues(alpha: 0.14);
  static List<BoxShadow> get softShadow => [
        BoxShadow(
          color: Colors.black.withValues(alpha: 0.38),
          blurRadius: 28,
          offset: const Offset(0, 8),
        ),
      ];

  /// Space Grotesk display/heading style (near-white text, Cairo fallback).
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
    final base = ThemeData.dark(useMaterial3: true);
    final scheme = ColorScheme.fromSeed(
      seedColor: accent,
      brightness: Brightness.dark,
      surface: surface,
      primary: accent,
      secondary: accent2,
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
      // canvasColor must stay SOLID: dropdown/popup menus paint on it — a
      // transparent canvas makes open dropdowns overlap the page behind
      // them (drop.png bug).
      scaffoldBackgroundColor: Colors.transparent,
      canvasColor: surface,
      popupMenuTheme: PopupMenuThemeData(
        color: surface,
        elevation: 6,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: BorderSide(color: border),
        ),
        textStyle: const TextStyle(color: textPrimary),
      ),
      dropdownMenuTheme: DropdownMenuThemeData(
        menuStyle: MenuStyle(
          backgroundColor: WidgetStateProperty.all(surface),
          elevation: WidgetStateProperty.all(6),
        ),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: surface,
        surfaceTintColor: Colors.transparent,
      ),
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
          backgroundColor: glass,
          side: BorderSide(color: border),
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 13),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(13)),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(foregroundColor: accent),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: glass,
        side: BorderSide(color: border),
        labelStyle: const TextStyle(color: textPrimary, fontSize: 13),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
      ),
      segmentedButtonTheme: SegmentedButtonThemeData(
        style: ButtonStyle(
          backgroundColor: WidgetStateProperty.resolveWith(
            (s) => s.contains(WidgetState.selected) ? accent : glass,
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
        fillColor: surface2,
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
        colors: [Colors.transparent, Color(0x33000000), Color(0x66000000)],
        stops: [0.0, 0.7, 1.0],
      );

  static BoxDecoration cardGradient({Color? tint}) => BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        color: surface,
        border: Border.all(color: border),
        boxShadow: softShadow,
      );
}
