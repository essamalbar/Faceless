import 'package:faceless/api/client.dart';
import 'package:faceless/api/settings.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _FixedSettings extends FacelessSettings {
  @override
  Future<String?> baseUrl() async => 'http://localhost:9999';
  @override
  Future<String?> tokenForLegacyMode() async => 'fake-dev-token';
}

void main() {
  test('createSong includes genre in body when set', () async {
    late String sent;
    final mock = MockClient((req) async {
      sent = req.body;
      return http.Response('{"run_id":"r1"}', 201);
    });
    final client = FacelessApiClient(_FixedSettings(), httpClient: mock);
    final id = await client.createSong(
        theme: 'x', genre: 'rock', ownershipAttested: true);
    expect(id, 'r1');
    expect(sent, contains('"genre":"rock"'));
  });

  test('createSong omits genre when null', () async {
    late String sent;
    final mock = MockClient((req) async {
      sent = req.body;
      return http.Response('{"run_id":"r1"}', 201);
    });
    final client = FacelessApiClient(_FixedSettings(), httpClient: mock);
    await client.createSong(theme: 'x', ownershipAttested: true);
    expect(sent.contains('genre'), isFalse);
  });
}
