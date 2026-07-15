/// Circular artist avatar. Shows the uploaded/run-cover image when the
/// artist has one (served by GET /artists/{id}/avatar), else a deterministic
/// pastel gradient seeded by the artist's name with their initial centered.
/// Always clipped to a circle with a hairline border.
library;

import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../theme.dart';
import '../ui/brand.dart';

class ArtistAvatar extends StatelessWidget {
  final Artist artist;
  final FacelessApiClient client;
  final double size;
  const ArtistAvatar({
    super.key,
    required this.artist,
    required this.client,
    this.size = 56,
  });

  Widget _gradientFallback() {
    final name = artist.name.trim();
    final initial = name.isEmpty ? '?' : name.characters.first;
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        gradient: coverGradient(artist.name),
        shape: BoxShape.circle,
      ),
      alignment: Alignment.center,
      child: Text(
        initial,
        style: TextStyle(
          color: Colors.white,
          fontWeight: FontWeight.w700,
          fontSize: size * 0.42,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    Widget content;
    if (artist.hasAvatar) {
      // artistAvatarUrl is async (reads base URL + token), hence the
      // FutureBuilder; the gradient shows until the Uri resolves.
      content = FutureBuilder<Uri>(
        future: client.artistAvatarUrl(artist.id),
        builder: (ctx, snap) {
          if (!snap.hasData) return _gradientFallback();
          return Image.network(
            snap.data!.toString(),
            width: size,
            height: size,
            fit: BoxFit.cover,
            errorBuilder: (ctx2, err, stack) => _gradientFallback(),
          );
        },
      );
    } else {
      content = _gradientFallback();
    }
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        border: Border.all(color: FacelessTheme.border),
      ),
      child: ClipOval(child: content),
    );
  }
}
