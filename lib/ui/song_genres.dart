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

const kSongGenres = <SongGenre>[
  SongGenre('arabic_pop', '🎤', [Color(0xFFFFE3D3), Color(0xFFFBD0E0)], arabicOnly: true),
  SongGenre('arabic_ballad', '💔', [Color(0xFFE7DEF9), Color(0xFFD6E4FB)], arabicOnly: true),
  SongGenre('khaleeji', '🌙', [Color(0xFFD8F3E7), Color(0xFFCDECEF)], arabicOnly: true),
  SongGenre('tarab_classic', '🎻', [Color(0xFFFBEFCB), Color(0xFFF6E0C4)], arabicOnly: true),
  SongGenre('arabic_trap', '🔥', [Color(0xFFE4D9FA), Color(0xFFD9DEFB)], arabicOnly: true),
  SongGenre('folk_shaabi', '🪗', [Color(0xFFFCE1EC), Color(0xFFF3D9E9)], arabicOnly: true),
  SongGenre('hiphop_rap', '🎧', [Color(0xFFE1F0E6), Color(0xFFDCEFEA)]),
  SongGenre('rnb_soul', '🎹', [Color(0xFFDEE6F2), Color(0xFFE9E1F1)]),
  SongGenre('pop', '🎶', [Color(0xFFFFE9D8), Color(0xFFF7D9E6)]),
  SongGenre('rock', '🎸', [Color(0xFFE6E1F5), Color(0xFFD9DEFB)]),
  SongGenre('edm_electropop', '🎛️', [Color(0xFFD8F0F3), Color(0xFFCDE8EF)]),
  SongGenre('cinematic_ost', '🎬', [Color(0xFFDEE6F2), Color(0xFFE4DDEF)]),
];

List<SongGenre> genresForLanguage(String language) =>
    language.startsWith('ar')
        ? kSongGenres
        : kSongGenres.where((g) => !g.arabicOnly).toList();

bool isGenreValidForLanguage(String? key, String language) =>
    key == null || genresForLanguage(language).any((g) => g.key == key);
