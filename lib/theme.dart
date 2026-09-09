/// Faceless brand theme — Obsidian & Champagne. Warm near-black grounds lit by
/// a soft champagne wash, frosted translucent cards with warm hairline edges,
/// a champagne gradient for accents/CTAs, Cormorant Garamond (Amiri for
/// Arabic) editorial display / Manrope (Tajawal for Arabic) body. A global
/// ambient background sits behind every screen (main.dart's MaterialApp.builder +
/// ui/brand.dart MeshBackground).
///
/// Token + widget NAMES are kept stable so screens inherit the look through
/// the shared layer without edits — only the VALUES + fonts changed from the
/// dark-neon system. See
/// docs/superpowers/specs/2026-09-09-luxury-redesign-design-system.md
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class FacelessTheme {
  // --- Palette (obsidian + champagne) ------------------------------------
  static const bg = Color(0xFF0C0B0E); // warm near-black base (mesh paints wash)
  static const surface = Color(0xFF16151A); // SOLID dark card / menu ground
  static const surface2 = Color(0xFF1E1C22); // slightly lighter dark
  static const accent = Color(0xFFC9A96E); // champagne (the one metallic accent)
  static const accent2 = Color(0xFFE4CE9E); // accent bright (gradient top)
  static const accentMid = Color(0xFFD4B483); // 3-stop gradient middle
  static const accentDeep = Color(0xFFB4915A); // gradient bottom
  static const ink = surface; // solid obsidian ground (no gold-fill buttons)
  static const textPrimary = Color(0xFFEFE9DE); // warm off-white, never pure white
  static const textSecondary = Color(0xFFA39C8E); // muted warm grey
  static const faint = Color(0xFF6E685D);
  static const danger = Color(0xFFC6564E); // muted brick red
  static const success = Color(0xFF9DBB9C); // muted sage
  static const warning = accent; // champagne outline (review state)
  static const info = Color(0xFF6E8BA6); // muted steel

  // Champagne gradient used for the logo mark, accent headline words, primary CTA.
  static const brandGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [accent2, accentDeep],
  );

  // Frosted translucent surfaces + warm hairline borders over the ambient wash.
  static Color get glass => Colors.white.withValues(alpha: 0.03);
  static Color get glassStrong => Colors.white.withValues(alpha: 0.06);
  static Color get border => const Color(0xFFEEE9DE).withValues(alpha: 0.10);
  static Color get borderAccent => const Color(0xFFC9A96E).withValues(alpha: 0.35);
  static List<BoxShadow> get softShadow => [
        BoxShadow(
          color: Colors.black.withValues(alpha: 0.38),
          blurRadius: 28,
          offset: const Offset(0, 8),
        ),
      ];

  /// Cormorant Garamond (EN) / Amiri (AR) editorial display style, warm
  /// off-white text, with the other script as fallback so mixed strings
  /// still shape correctly.
  static TextStyle display({
    double size = 28,
    FontWeight weight = FontWeight.w700,
    Color? color,
    double height = 1.05,
    double letterSpacing = -0.5,
    Locale? locale,
  }) {
    final isArabic = locale?.languageCode == 'ar';
    final style = isArabic
        ? GoogleFonts.amiri(
            fontSize: size,
            fontWeight: weight,
            height: height,
            letterSpacing: letterSpacing,
            color: color ?? textPrimary,
          )
        : GoogleFonts.cormorantGaramond(
            fontSize: size,
            fontWeight: weight,
            height: height,
            letterSpacing: letterSpacing,
            color: color ?? textPrimary,
          );
    final fallback = isArabic
        ? GoogleFonts.cormorantGaramond().fontFamily
        : GoogleFonts.amiri().fontFamily;
    return style.copyWith(
      fontFamilyFallback: [?fallback],
    );
  }

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

    // Arabic UI: Tajawal primary (Manrope fallback for Latin snippets).
    // English UI: Manrope primary (Tajawal fallback for Arabic content).
    final manrope = GoogleFonts.manrope().fontFamily;
    final tajawal = GoogleFonts.tajawal().fontFamily;
    final textTheme = (isArabic
            ? GoogleFonts.tajawalTextTheme(base.textTheme)
            : GoogleFonts.manropeTextTheme(base.textTheme))
        .apply(
      bodyColor: textPrimary,
      displayColor: textPrimary,
      fontFamilyFallback: [
        if (isArabic && manrope != null) manrope,
        if (!isArabic && tajawal != null) tajawal,
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
          backgroundColor: surface,
          foregroundColor: accent2,
          side: BorderSide(color: borderAccent),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 15),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(13)),
          textStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: surface,
          foregroundColor: accent2,
          side: BorderSide(color: borderAccent),
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
            (s) => s.contains(WidgetState.selected) ? bg : textSecondary,
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
