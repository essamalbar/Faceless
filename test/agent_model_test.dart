import 'package:flutter_test/flutter_test.dart';
import 'package:faceless/api/models.dart';

// Autonomous Artist Agent (Task 9): AgentProposal.fromJson + Artist.agentEnabled
// parsing. Mirrors the snake_case wire shape from pipeline/api.py
// (AgentProposalSummary, ArtistOut.agent_enabled).
void main() {
  group('AgentProposal.fromJson', () {
    test('parses a full proposal', () {
      final p = AgentProposal.fromJson({
        'run_id': 'r1',
        'artist_id': 'a1',
        'title': 'Desert Night',
        'rationale': 'No release in 9 days; trend fits the artist voice.',
        'self_score': 0.82,
        'created_at': '2026-09-25T00:00:00Z',
        'cost_credits': 12,
        'cost_usd': 1.2,
      });
      expect(p.runId, 'r1');
      expect(p.artistId, 'a1');
      expect(p.title, 'Desert Night');
      expect(p.rationale, contains('trend fits'));
      expect(p.selfScore, 0.82);
      expect(p.createdAt, '2026-09-25T00:00:00Z');
      expect(p.costCredits, 12);
      expect(p.costUsd, 1.2);
    });

    test('defaults nullable fields when absent', () {
      final p = AgentProposal.fromJson({
        'run_id': 'r2',
        'cost_credits': 0,
        'cost_usd': 0.0,
      });
      expect(p.runId, 'r2');
      expect(p.artistId, '');
      expect(p.title, '');
      expect(p.rationale, '');
      expect(p.selfScore, 0.0);
      expect(p.createdAt, '');
    });
  });

  group('Artist.agentEnabled', () {
    test('parses true from the wire field', () {
      final a = Artist.fromJson({
        'id': 'a1',
        'name': 'Layla',
        'handle': 'layla',
        'created_at': '2026-09-25T00:00:00Z',
        'agent_enabled': true,
      });
      expect(a.agentEnabled, isTrue);
    });

    test('defaults to false when absent (older backend / new artist)', () {
      final a = Artist.fromJson({
        'id': 'a2',
        'name': 'Omar',
        'handle': 'omar',
        'created_at': '2026-09-25T00:00:00Z',
      });
      expect(a.agentEnabled, isFalse);
    });
  });
}
