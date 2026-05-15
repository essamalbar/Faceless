// 401 handling on the API client. The real sign-out side-effect needs
// Supabase, which we can't initialize from a pure unit test — but the
// client's `_handleAuthFailure` wraps that call in a try/catch, so
// asserting the *exception shape* still verifies the new code path
// (and proves we don't crash when Supabase is uninitialized).
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
  test('401 from JSON endpoint surfaces as "Session expired"', () async {
    final mock = MockClient((req) async => http.Response('{"detail":"x"}', 401));
    final client = FacelessApiClient(_FixedSettings(), httpClient: mock);

    await expectLater(
      client.listRuns(),
      throwsA(
        isA<FacelessApiException>()
            .having((e) => e.status, 'status', 401)
            .having((e) => e.message, 'message',
                contains('Session expired')),
      ),
    );
  });

  test('401 on raw-body endpoint (logs) also goes through _checkOk',
      () async {
    final mock = MockClient((req) async => http.Response('not json', 401));
    final client = FacelessApiClient(_FixedSettings(), httpClient: mock);

    await expectLater(
      client.getLog('any-run'),
      throwsA(isA<FacelessApiException>()
          .having((e) => e.status, 'status', 401)
          .having((e) => e.message, 'message', contains('Session expired'))),
    );
  });
}
