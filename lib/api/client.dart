/// HTTP client for the Faceless Pipeline API.
///
/// Reads base URL + bearer token from FacelessSettings (secure storage).
/// All endpoints except `/healthz` send `Authorization: Bearer <token>`.
library;

import 'dart:convert';
import 'package:http/http.dart' as http;

import 'models.dart';
import 'settings.dart';

class FacelessApiException implements Exception {
  final int? status;
  final String message;
  FacelessApiException(this.message, {this.status});
  @override
  String toString() =>
      status == null ? 'FacelessApiError: $message' : 'FacelessApiError $status: $message';
}

class FacelessApiClient {
  final FacelessSettings _settings;
  final http.Client _http;

  FacelessApiClient(this._settings, {http.Client? httpClient})
      : _http = httpClient ?? http.Client();

  Future<Map<String, String>> _headers({bool authed = true}) async {
    final h = <String, String>{'Accept': 'application/json'};
    if (authed) {
      final token = await _settings.token();
      if (token == null || token.isEmpty) {
        throw FacelessApiException('API token not configured (open Settings)');
      }
      h['Authorization'] = 'Bearer $token';
    }
    return h;
  }

  Future<Uri> _uri(String path) async {
    final base = await _settings.baseUrl();
    if (base == null || base.isEmpty) {
      throw FacelessApiException('Server URL not configured (open Settings)');
    }
    final cleaned = base.endsWith('/') ? base.substring(0, base.length - 1) : base;
    return Uri.parse('$cleaned$path');
  }

  T _parse<T>(http.Response r, T Function(dynamic) decode) {
    if (r.statusCode >= 400) {
      String detail;
      try {
        final body = jsonDecode(r.body);
        detail = body is Map && body['detail'] != null
            ? body['detail'].toString()
            : r.body;
      } catch (_) {
        detail = r.body;
      }
      throw FacelessApiException(detail, status: r.statusCode);
    }
    return decode(jsonDecode(utf8.decode(r.bodyBytes)));
  }

  // ---------- read ----------

  Future<bool> healthz() async {
    final r = await _http.get(await _uri('/healthz'),
        headers: await _headers(authed: false));
    return r.statusCode == 200;
  }

  Future<List<RunSummary>> listRuns() async {
    final r = await _http.get(await _uri('/runs'), headers: await _headers());
    return _parse(r, (j) => (j as List)
        .map((x) => RunSummary.fromJson(x as Map<String, dynamic>))
        .toList());
  }

  Future<RunSummary> getRun(String runId) async {
    final r = await _http.get(await _uri('/runs/$runId'), headers: await _headers());
    return _parse(r, (j) => RunSummary.fromJson(j as Map<String, dynamic>));
  }

  Future<ScriptResponse> getScript(String runId) async {
    final r = await _http.get(await _uri('/runs/$runId/script'),
        headers: await _headers());
    return _parse(r, (j) => ScriptResponse.fromJson(j as Map<String, dynamic>));
  }

  Future<String> getLog(String runId, {int lines = 200}) async {
    final r = await _http.get(await _uri('/runs/$runId/log?lines=$lines'),
        headers: await _headers());
    if (r.statusCode >= 400) {
      throw FacelessApiException(r.body, status: r.statusCode);
    }
    return utf8.decode(r.bodyBytes);
  }

  /// URL for the final.mp4 — token in QUERY STRING, not header.
  ///
  /// Browsers (Chrome web, mobile webview) cannot attach Authorization
  /// headers to a `<video>` element's request, so the URL must be
  /// self-authenticating. The server's `/video` endpoint accepts either
  /// `Authorization: Bearer <t>` OR `?token=<t>`.
  Future<Uri> videoUrl(String runId) async {
    final base = await _settings.baseUrl();
    final token = await _settings.token();
    if (base == null || token == null) {
      throw FacelessApiException('Not configured');
    }
    return Uri.parse('${_stripTrailing(base)}/runs/$runId/video?token=$token');
  }

  Future<Uri> thumbnailUrl(String runId) async {
    final base = await _settings.baseUrl();
    final token = await _settings.token();
    if (base == null || token == null) {
      throw FacelessApiException('Not configured');
    }
    return Uri.parse('${_stripTrailing(base)}/runs/$runId/thumbnail?token=$token');
  }

  /// First-frame JPG of a specific clip in a run. Used by the run-detail
  /// script panel so each beat shows what its rendered clip looks like.
  Future<Uri> clipThumbnailUrl(String runId, int clipIndex) async {
    final base = await _settings.baseUrl();
    final token = await _settings.token();
    if (base == null || token == null) {
      throw FacelessApiException('Not configured');
    }
    return Uri.parse(
      '${_stripTrailing(base)}/runs/$runId/clips/$clipIndex/thumbnail?token=$token',
    );
  }

  /// URL for a single clip's mp4 with the auth token in the query string.
  /// Used by the run-detail beat tile's tap-to-play UX. Token in query
  /// because the Flutter video_player plugin on web silently drops
  /// `httpHeaders` (same workaround as `videoUrl`).
  Future<Uri> clipVideoUrl(String runId, int clipIndex) async {
    final base = await _settings.baseUrl();
    final token = await _settings.token();
    if (base == null || token == null) {
      throw FacelessApiException('Not configured');
    }
    return Uri.parse(
      '${_stripTrailing(base)}/runs/$runId/clips/$clipIndex/video?token=$token',
    );
  }

  static String _stripTrailing(String s) =>
      s.endsWith('/') ? s.substring(0, s.length - 1) : s;

  // ---------- write ----------

  Future<RunSummary> createRun({
    required String theme,
    required String premise,
    int? maxBeats,
  }) async {
    final body = <String, dynamic>{
      'theme': theme,
      'premise': premise,
      if (maxBeats != null) 'max_beats': maxBeats,
    };
    final r = await _http.post(
      await _uri('/runs'),
      headers: {...await _headers(), 'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );
    return _parse(r, (j) => RunSummary.fromJson(j as Map<String, dynamic>));
  }

  /// Create a run using the freeform script writer. The user supplies the
  /// premise plus a set of style controls; the writer is NOT locked to the
  /// Sunstoriz template.
  Future<RunSummary> createFreeformRun({
    required String theme,
    required String premise,
    required String dialect,
    required String artStyle,
    required String characterTemplate,
    required String endingType,
    required int numBeats,
    required int perBeatSeconds,
  }) async {
    final body = <String, dynamic>{
      'theme': theme,
      'premise': premise,
      'dialect': dialect,
      'art_style': artStyle,
      'character_template': characterTemplate,
      'ending_type': endingType,
      'num_beats': numBeats,
      'per_beat_seconds': perBeatSeconds,
    };
    final r = await _http.post(
      await _uri('/runs/freeform'),
      headers: {...await _headers(), 'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );
    return _parse(r, (j) => RunSummary.fromJson(j as Map<String, dynamic>));
  }

  /// Parse a markdown episode script (Arabic, with **SPEAKER:** "dialogue"
  /// blocks) into structured beats. Hybrid: regex first; LLM split on miss;
  /// naive sentence-split as last resort. Verbatim — your Arabic is never
  /// rewritten.
  Future<ParseScriptResponse> parseScript(String rawText,
      {int targetBeats = 8}) async {
    final r = await _http.post(
      await _uri('/runs/parse-script'),
      headers: {...await _headers(), 'Content-Type': 'application/json'},
      body: jsonEncode({'raw_text': rawText, 'target_beats': targetBeats}),
    );
    return _parse(r, (j) => ParseScriptResponse.fromJson(j as Map<String, dynamic>));
  }

  /// Create a run from a HAND-WRITTEN script — no LLM rewrite. Use when the
  /// user already has the exact dialogue (e.g. continuing an episodic series).
  Future<RunSummary> createRunFromScript({
    required String title,
    required String theme,
    String premise = '',
    String musicMood = 'dread',
    String? globalSetting,
    required List<Map<String, dynamic>> beats,
  }) async {
    final body = <String, dynamic>{
      'title': title,
      'theme': theme,
      'premise': premise,
      'music_mood': musicMood,
      if (globalSetting != null) 'global_setting': globalSetting,
      'beats': beats,
    };
    final r = await _http.post(
      await _uri('/runs/from-script'),
      headers: {...await _headers(), 'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );
    return _parse(r, (j) => RunSummary.fromJson(j as Map<String, dynamic>));
  }

  Future<ApprovalAck> approveRun(String runId) async {
    final r = await _http.post(await _uri('/runs/$runId/approve'),
        headers: await _headers());
    return _parse(r, (j) => ApprovalAck.fromJson(j as Map<String, dynamic>));
  }

  /// Second approval gate. Allowed only when status=awaiting_veo_approval
  /// — confirms the user is OK with the Flux character sheet and wants
  /// Veo to start spending.
  Future<ApprovalAck> approveVeoRun(String runId) async {
    final r = await _http.post(await _uri('/runs/$runId/approve-veo'),
        headers: await _headers());
    return _parse(r, (j) => ApprovalAck.fromJson(j as Map<String, dynamic>));
  }

  /// Throw away the current Flux character sheet and regenerate it. Costs
  /// another $0.05 of Flux. Allowed only from awaiting_veo_approval.
  Future<ApprovalAck> rerollCharacterSheet(String runId) async {
    final r = await _http.post(
        await _uri('/runs/$runId/character-sheet/reroll'),
        headers: await _headers());
    return _parse(r, (j) => ApprovalAck.fromJson(j as Map<String, dynamic>));
  }

  Future<ApprovalAck> resumeRun(String runId) async {
    final r = await _http.post(await _uri('/runs/$runId/resume'),
        headers: await _headers());
    return _parse(r, (j) => ApprovalAck.fromJson(j as Map<String, dynamic>));
  }

  Future<void> cancelRun(String runId) async {
    final r = await _http.post(await _uri('/runs/$runId/cancel'),
        headers: await _headers());
    if (r.statusCode >= 400) {
      throw FacelessApiException(r.body, status: r.statusCode);
    }
  }

  /// Replace beats in script.json — only allowed when status=awaiting_approval.
  Future<ScriptResponse> editScript(
    String runId, {
    String? title,
    required List<Map<String, dynamic>> beats,
  }) async {
    final body = {
      if (title != null) 'title': title,
      'beats': beats,
    };
    final r = await _http.put(
      await _uri('/runs/$runId/script'),
      headers: {...await _headers(), 'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );
    return _parse(r, (j) => ScriptResponse.fromJson(j as Map<String, dynamic>));
  }

  /// Regenerate specific clips without losing the others. Use when one
  /// clip rendered in English / has a visual error / etc. — pays only for
  /// the rerolled clips, not the whole episode.
  Future<ApprovalAck> rerollClips(String runId, List<int> clips) async {
    final r = await _http.post(
      await _uri('/runs/$runId/reroll'),
      headers: {...await _headers(), 'Content-Type': 'application/json'},
      body: jsonEncode({'clips': clips}),
    );
    return _parse(r, (j) => ApprovalAck.fromJson(j as Map<String, dynamic>));
  }

  /// Bulk-discard every run currently in `failed` status. Returns the IDs
  /// of runs that were deleted.
  Future<List<String>> cleanupFailedRuns() async {
    final r = await _http.post(await _uri('/runs/cleanup-failed'),
        headers: await _headers());
    return _parse(r, (j) {
      final list = (j as Map<String, dynamic>)['deleted_run_ids'] as List;
      return list.map((x) => x as String).toList();
    });
  }

  Future<SpendSummary> getSpendSummary() async {
    final r = await _http.get(await _uri('/spend'), headers: await _headers());
    return _parse(r, (j) => SpendSummary.fromJson(j as Map<String, dynamic>));
  }

  /// Permanently delete a run dir (only when no subprocess is running).
  Future<void> deleteRun(String runId) async {
    final r = await _http.delete(await _uri('/runs/$runId'),
        headers: await _headers());
    if (r.statusCode >= 400) {
      throw FacelessApiException(r.body, status: r.statusCode);
    }
  }

  void close() => _http.close();
}
