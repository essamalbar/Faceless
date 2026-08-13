import 'package:flutter/material.dart';

import '../l10n/l10n.dart';
import '../theme.dart';
import '../ui/song_genres.dart';

/// Soft-gradient genre picker for the create screen. First tile is Auto
/// (selectedKey == null); the rest come from [genresForLanguage].
class GenreGrid extends StatelessWidget {
  final String? selectedKey;
  final String language;
  final ValueChanged<String?> onChanged;
  const GenreGrid({
    super.key,
    required this.selectedKey,
    required this.language,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final genres = genresForLanguage(language);
    return GridView.count(
      crossAxisCount: 3,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 8,
      crossAxisSpacing: 8,
      childAspectRatio: 1.5,
      children: [
        _AutoTile(
          selected: selectedKey == null,
          label: l10n.genreAuto,
          onTap: () => onChanged(null),
        ),
        for (final g in genres)
          _GenreTile(
            genre: g,
            label: g.label(l10n),
            selected: selectedKey == g.key,
            onTap: () => onChanged(g.key),
          ),
      ],
    );
  }
}

class _TileShell extends StatelessWidget {
  final Widget child;
  final Gradient gradient;
  final bool selected;
  final VoidCallback onTap;
  const _TileShell({
    required this.child,
    required this.gradient,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: Container(
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          gradient: gradient,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: selected ? FacelessTheme.accent : Colors.white.withValues(alpha: 0.6),
            width: selected ? 2.5 : 1,
          ),
        ),
        child: child,
      ),
    );
  }
}

class _AutoTile extends StatelessWidget {
  final bool selected;
  final String label;
  final VoidCallback onTap;
  const _AutoTile({required this.selected, required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) => _TileShell(
        selected: selected,
        onTap: onTap,
        gradient: const LinearGradient(colors: [Color(0xFFEAF7F0), Color(0xFFE4F3F4)]),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Text('✨', style: TextStyle(fontSize: 16)),
            Text(label,
                style: const TextStyle(
                    fontWeight: FontWeight.w600, fontSize: 12, color: FacelessTheme.accent)),
          ],
        ),
      );
}

class _GenreTile extends StatelessWidget {
  final SongGenre genre;
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _GenreTile({
    required this.genre,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) => _TileShell(
        selected: selected,
        onTap: onTap,
        gradient: LinearGradient(
          colors: genre.gradient,
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(genre.emoji, style: const TextStyle(fontSize: 16)),
            Text(label,
                style: const TextStyle(
                    fontWeight: FontWeight.w600, fontSize: 12, color: Color(0xFF3A2F36))),
          ],
        ),
      );
}
