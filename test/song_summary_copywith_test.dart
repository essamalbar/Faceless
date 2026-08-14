import 'package:flutter_test/flutter_test.dart';
import 'package:faceless/api/models.dart';

// Finding 5 regression: hand-rebuilding SongSummary silently dropped fields
// (source/trendRationale). copyWith must override only what's passed and
// preserve everything else.
void main() {
  SongSummary full() => SongSummary(
        id: 'r1',
        status: 'complete',
        title: 'T',
        theme: 'th',
        createdAt: '2026-01-01',
        hasVideo: true,
        chosenTake: 2,
        lastError: null,
        failureStage: null,
        watermarked: true,
        videoMode: 'cinematic',
        artistId: 'a1',
        artistName: 'Layla',
        released: false,
        youtubeUrl: null,
        source: 'trend',
        trendRationale: 'why now',
        performStatus: null,
        performVideo: null,
      );

  test('copyWith overrides one field and preserves ALL others', () {
    final s = full().copyWith(released: true);
    expect(s.released, isTrue);
    // the fields the old hand-rebuild dropped:
    expect(s.source, 'trend');
    expect(s.trendRationale, 'why now');
    // and everything else is intact:
    expect(s.id, 'r1');
    expect(s.title, 'T');
    expect(s.artistName, 'Layla');
    expect(s.videoMode, 'cinematic');
    expect(s.watermarked, isTrue);
    expect(s.chosenTake, 2);
  });

  test('copyWith perform fields preserve source/trendRationale', () {
    final s = full().copyWith(performStatus: 'rendering');
    expect(s.performStatus, 'rendering');
    expect(s.source, 'trend');
    expect(s.trendRationale, 'why now');
  });

  test('copyWith youtubeUrl preserves the rest', () {
    final s = full().copyWith(youtubeUrl: 'https://youtu.be/x');
    expect(s.youtubeUrl, 'https://youtu.be/x');
    expect(s.source, 'trend');
    expect(s.trendRationale, 'why now');
    expect(s.released, isFalse);
  });
}
