import 'package:flutter_test/flutter_test.dart';
import 'package:faceless/ui/song_genres.dart';

void main() {
  test('arabic shows 12 genres, other languages show 6', () {
    expect(genresForLanguage('ar').length, 12);
    expect(genresForLanguage('en').length, 6);
    expect(genresForLanguage('fr').length, 6);
  });

  test('generic is never a tile', () {
    expect(kSongGenres.any((g) => g.key == 'generic'), isFalse);
  });

  test('english excludes arabic-only genres', () {
    final en = genresForLanguage('en').map((g) => g.key).toSet();
    expect(en.contains('khaleeji'), isFalse);
    expect(en.contains('tarab_classic'), isFalse);
    expect(en.contains('pop'), isTrue);
    expect(en.contains('rock'), isTrue);
  });

  test('isGenreValidForLanguage', () {
    expect(isGenreValidForLanguage('khaleeji', 'en'), isFalse);
    expect(isGenreValidForLanguage('khaleeji', 'ar'), isTrue);
    expect(isGenreValidForLanguage(null, 'en'), isTrue); // Auto always valid
  });
}
