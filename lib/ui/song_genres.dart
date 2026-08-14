import 'package:flutter/material.dart';

import '../l10n/l10n.dart';

/// A selectable genre tile for the create screen.
///
/// [key] MUST equal a GENRE_RECIPES key in pipeline/song_style.py — it is sent
/// to the backend as the forced genre. `generic` is intentionally NOT a tile
/// (it stays the inference fallback). Gradient colours are cosmetic.
class SongGenre {
  final String key;
  final String emoji;
  final List<Color> gradient;
  final bool arabicOnly;
  const SongGenre(this.key, this.emoji, this.gradient,
      {this.arabicOnly = false});

  String label(AppLocalizations l) => switch (key) {
        'arabic_pop' => l.genreArabicPop,
        'arabic_ballad' => l.genreArabicBallad,
        'khaleeji' => l.genreKhaleeji,
        'tarab_classic' => l.genreTarab,
        'arabic_trap' => l.genreArabicTrap,
        'folk_shaabi' => l.genreShaabi,
        'hiphop_rap' => l.genreHipHop,
        'rnb_soul' => l.genreRnb,
        'pop' => l.genrePop,
        'rock' => l.genreRock,
        'edm_electropop' => l.genreEdm,
        'cinematic_ost' => l.genreCinematic,
        _ => key,
      };
}

// Dark saturated neon gradient pairs (glassy dark-neon theme). Cosmetic only.
const kSongGenres = <SongGenre>[
  SongGenre('arabic_pop', '🎤', [Color(0xFF3A2352), Color(0xFF7A2E6E)], arabicOnly: true),
  SongGenre('arabic_ballad', '💔', [Color(0xFF2B2352), Color(0xFF5A3AA6)], arabicOnly: true),
  SongGenre('khaleeji', '🌙', [Color(0xFF1F3A5C), Color(0xFF2E7A6E)], arabicOnly: true),
  SongGenre('tarab_classic', '🎻', [Color(0xFF5C3A1F), Color(0xFFA2762E)], arabicOnly: true),
  SongGenre('arabic_trap', '🔥', [Color(0xFF5C1F3A), Color(0xFFA2405B)], arabicOnly: true),
  SongGenre('folk_shaabi', '🪗', [Color(0xFF5A1F52), Color(0xFF9E2E7A)], arabicOnly: true),
  SongGenre('hiphop_rap', '🎧', [Color(0xFF1F5C4A), Color(0xFF2EA27A)]),
  SongGenre('rnb_soul', '🎹', [Color(0xFF3A1F52), Color(0xFF6E2E7A)]),
  SongGenre('pop', '🎶', [Color(0xFF5C1F45), Color(0xFFA2406B)]),
  SongGenre('rock', '🎸', [Color(0xFF23264A), Color(0xFF3A3AA6)]),
  SongGenre('edm_electropop', '🎛️', [Color(0xFF1F4A5C), Color(0xFF2E8AA2)]),
  SongGenre('cinematic_ost', '🎬', [Color(0xFF2A2440), Color(0xFF4A3A6E)]),
];

List<SongGenre> genresForLanguage(String language) =>
    language.startsWith('ar')
        ? kSongGenres
        : kSongGenres.where((g) => !g.arabicOnly).toList();

bool isGenreValidForLanguage(String? key, String language) =>
    key == null || genresForLanguage(language).any((g) => g.key == key);
