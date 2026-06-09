/// HTTP client for the Faceless Pipeline API.
///
/// Reads base URL from FacelessSettings (secure storage). The bearer token
/// is the Supabase session JWT (preferred) or a legacy dart-define-baked
/// token (fallback for dev/local-only mode).
/// All endpoints except `/healthz` send `Authorization: Bearer <token>`.
library;

import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:supabase_flutter/supabase_flutter.dart';

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

class InsufficientCreditsException extends FacelessApiException {
  final int balance;
  final int required;
  InsufficientCreditsException({required this.balance, required this.required})
      : super('Insufficient credits: have $balance, need $required', status: 402);
}

class FacelessApiClient {
  final FacelessSettings _settings;
  final http.Client _http;

  FacelessApiClient(this._settings, {http.Client? httpClient})
      : _http = httpClient ?? http.Client();

  Future<Map<String, String>> _headers({bool authed = true}) async {
    final h = <String, String>{'Accept': 'application/json'};
    if (authed) {
      final token = await _resolveToken();
      if (token == null || token.isEmpty) {
        throw FacelessApiException('Not signed in');
      }
      h['Authorization'] = 'Bearer $token';
    }
    return h;
  }

  /// Returns the bearer token to send. Prefers the Supabase access token; falls
  /// back to a settings-baked token only when Supabase isn't initialized (e.g.
  /// dev mode without --dart-define values, or legacy local-only deployments).
  ///
  /// Refreshes the session synchronously if the cached access token has
  /// expired — otherwise users who leave the tab open overnight come back
  /// to 401s on every authed request, even though the refresh token is
  /// still valid.
  Future<String?> _resolveToken() async {
    try {
      final auth = Supabase.instance.client.auth;
      final initial = auth.currentSession;
      if (initial == null) return _settings.tokenForLegacyMode();
      // Promote to a non-nullable local — Dart's flow analysis loses
      // the null-narrowing across the reassignment below, and dart2js
      // hard-fails on `session.accessToken` if the declared type is
      // still `Session?`.
      var session = initial;
      if (session.isExpired) {
        try {
          final res = await auth.refreshSession();
          final refreshed = res.session;
          if (refreshed != null) session = refreshed;
        } catch (_) {
          // Refresh failed (refresh token also expired, or network down).
          // Let the request go out with the stale token; the 401 will
          // bubble up to the UI as "Sign in again" rather than a hang.
        }
      }
      return session.accessToken;
    } catch (_) {
      // Supabase not initialized — fall through to settings.
    }
    return _settings.tokenForLegacyMode();
  }

  Future<Uri> _uri(String path) async {
    final base = await _settings.baseUrl();
    if (base == null || base.isEmpty) {
      throw FacelessApiException('Server URL not configured (open Settings)');
    }
    final cleaned = base.endsWith('/') ? base.substring(0, base.length - 1) : base;
    return Uri.parse('$cleaned$path');
  }

  /// Sign-out side-effect when the server says our token is dead. The auth
  /// state stream in main.dart watches `onAuthStateChange` and swaps the
  /// home widget back to LandingScreen automatically — we just have to
  /// burn the session here. Guarded by a flag so a burst of parallel
  /// failing requests doesn't pile up sign-out calls.
  static bool _signingOut = false;
  Future<void> _handleAuthFailure() async {
    if (_signingOut) return;
    _signingOut = true;
    try {
      await Supabase.instance.client.auth.signOut();
    } catch (_) {
      // Supabase not initialized (legacy dart-define mode) — nothing to sign
      // out of. The thrown exception will still bubble up to the UI.
    } finally {
      _signingOut = false;
    }
  }

  /// Status guard for endpoints that return raw bodies (logs, video, etc).
  /// Use instead of an open-coded `if (r.statusCode >= 400) throw` so the
  /// 401 sign-out side-effect fires consistently.
  void _checkOk(http.Response r) {
    if (r.statusCode == 401) {
      _handleAuthFailure();
      throw FacelessApiException('Session expired — please sign in again',
          status: 401);
    }
    if (r.statusCode >= 400) {
      throw FacelessApiException(r.body, status: r.statusCode);
    }
  }

  T _parse<T>(http.Response r, T Function(dynamic) decode) {
    if (r.statusCode == 401) {
      _handleAuthFailure();
      throw FacelessApiException('Session expired — please sign in again',
          status: 401);
    }
    // Special case: 402 with a structured insufficient_credits detail.
    // Surface as a typed exception so the UI can route to the paywall.
    if (r.statusCode == 402) {
      try {
        final body = jsonDecode(r.body);
        final detailMap = body is Map ? body['detail'] : null;
        if (detailMap is Map && detailMap['code'] == 'insufficient_credits') {
          throw InsufficientCreditsException(
            balance: (detailMap['balance'] ?? 0) as int,
            required: (detailMap['required'] ?? 0) as int,
          );
        }
      } on InsufficientCreditsException {
        rethrow;
      } catch (_) {
        // jsonDecode failed or shape wasn't what we expected — fall through to generic.
      }
    }

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
    _checkOk(r);
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
    final token = await _resolveToken();
    if (base == null || token == null) {
      throw FacelessApiException('Not configured');
    }
    return Uri.parse('${_stripTrailing(base)}/runs/$runId/video?token=$token');
  }

  Future<Uri> thumbnailUrl(String runId) async {
    final base = await _settings.baseUrl();
    final token = await _resolveToken();
    if (base == null || token == null) {
      throw FacelessApiException('Not configured');
    }
    return Uri.parse('${_stripTrailing(base)}/runs/$runId/thumbnail?token=$token');
  }

  /// PDF export of the script — free-tier feature, no credit charge.
  /// Returns a URL with the bearer token in the query string so a plain
  /// browser navigation (or url_launcher) can stream the PDF without
  /// needing to attach headers.
  Future<Uri> scriptPdfUrl(String runId) async {
    final base = await _settings.baseUrl();
    final token = await _resolveToken();
    if (base == null || token == null) {
      throw FacelessApiException('Not configured');
    }
    return Uri.parse(
      '${_stripTrailing(base)}/runs/$runId/script.pdf?token=$token',
    );
  }

  /// First-frame JPG of a specific clip in a run. Used by the run-detail
  /// script panel so each beat shows what its rendered clip looks like.
  Future<Uri> clipThumbnailUrl(String runId, int clipIndex) async {
    final base = await _settings.baseUrl();
    final token = await _resolveToken();
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
    final token = await _resolveToken();
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
    String narrationStyle = 'cinematic',
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
      'narration_style': narrationStyle,
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
    _checkOk(r);
  }

  /// Re-mux an existing final.mp4 with `+faststart` for browser playback.
  /// Use when an older run shows "demuxer could not open" in the player —
  /// no Veo spend, no re-encode, takes a second or two server-side.
  Future<void> repairVideo(String runId) async {
    final r = await _http.post(await _uri('/runs/$runId/repair-video'),
        headers: await _headers());
    _checkOk(r);
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
    _checkOk(r);
  }

  // ---------- billing ----------

  Future<Balance> getBalance() async {
    final r = await _http.get(await _uri('/billing/balance'), headers: await _headers());
    return _parse(r, (j) => Balance.fromJson(j as Map<String, dynamic>));
  }

  Future<PlanInfo> getPlan() async {
    final r = await _http.get(await _uri('/billing/plan'), headers: await _headers());
    return _parse(r, (j) => PlanInfo.fromJson(j as Map<String, dynamic>));
  }

  Future<List<CreditTx>> getTransactions({int limit = 50}) async {
    final r = await _http.get(
      await _uri('/billing/transactions?limit=$limit'),
      headers: await _headers(),
    );
    return _parse(r, (j) => (j as List)
        .map((x) => CreditTx.fromJson(x as Map<String, dynamic>))
        .toList());
  }

  Future<String> createSubscriptionCheckout({
    required String plan,
    required String successUrl,
    required String cancelUrl,
  }) async {
    final r = await _http.post(
      await _uri('/billing/checkout-subscription'),
      headers: {...await _headers(), 'Content-Type': 'application/json'},
      body: jsonEncode({'plan': plan, 'success_url': successUrl, 'cancel_url': cancelUrl}),
    );
    return _parse(r, (j) => (j as Map)['url'] as String);
  }

  Future<String> createTopupCheckout({
    required String pack,
    required String successUrl,
    required String cancelUrl,
  }) async {
    final r = await _http.post(
      await _uri('/billing/checkout-topup'),
      headers: {...await _headers(), 'Content-Type': 'application/json'},
      body: jsonEncode({'pack': pack, 'success_url': successUrl, 'cancel_url': cancelUrl}),
    );
    return _parse(r, (j) => (j as Map)['url'] as String);
  }

  Future<String> createPortalSession({required String returnUrl}) async {
    final r = await _http.post(
      await _uri('/billing/portal'),
      headers: {...await _headers(), 'Content-Type': 'application/json'},
      body: jsonEncode({'return_url': returnUrl}),
    );
    return _parse(r, (j) => (j as Map)['url'] as String);
  }

  // ---------- songs ----------

  Future<String> createSong({
    required String theme,
    String? customLyrics,
    String? styleHint,
    String language = 'ar',
    String? personaId,
    String vocalGender = 'm',
  }) async {
    final body = <String, dynamic>{
      'theme': theme,
      if (customLyrics != null && customLyrics.isNotEmpty) 'custom_lyrics': customLyrics,
      if (styleHint != null && styleHint.isNotEmpty) 'style_hint': styleHint,
      'language': language,
      if (personaId != null && personaId.isNotEmpty) 'persona_id': personaId,
      'vocal_gender': vocalGender,
    };
    final r = await _http.post(
      await _uri('/songs'),
      headers: {...await _headers(), 'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );
    return _parse(r, (j) => (j as Map<String, dynamic>)['run_id'] as String);
  }

  Future<List<SongSummary>> listSongs() async {
    final r = await _http.get(await _uri('/songs'), headers: await _headers());
    return _parse(r, (j) => (j as List)
        .map((x) => SongSummary.fromJson(x as Map<String, dynamic>))
        .toList());
  }

  Future<SongSummary> getSong(String id) async {
    final r = await _http.get(await _uri('/songs/$id'), headers: await _headers());
    return _parse(r, (j) => SongSummary.fromJson(j as Map<String, dynamic>));
  }

  Future<SongScript> getSongScript(String id) async {
    final r = await _http.get(await _uri('/songs/$id/script'), headers: await _headers());
    return _parse(r, (j) => SongScript.fromJson(j as Map<String, dynamic>));
  }

  Future<void> approveSong(String id) async {
    final r = await _http.post(await _uri('/songs/$id/approve'), headers: await _headers());
    _checkOk(r);
  }

  Future<void> regenerateSongLyrics(String id) async {
    final r = await _http.post(
      await _uri('/songs/$id/regenerate-lyrics'),
      headers: await _headers(),
    );
    _checkOk(r);
  }

  Future<void> regenerateSongCoverPrompt(String id) async {
    final r = await _http.post(
      await _uri('/songs/$id/regenerate-cover-prompt'),
      headers: await _headers(),
    );
    _checkOk(r);
  }

  Future<void> editSong(
    String id, {
    String? lyrics,
    String? stylePrompt,
    String? coverPrompt,
  }) async {
    final body = <String, dynamic>{
      if (lyrics != null) 'lyrics': lyrics,
      if (stylePrompt != null) 'style_prompt': stylePrompt,
      if (coverPrompt != null) 'cover_prompt': coverPrompt,
    };
    final r = await _http.post(
      await _uri('/songs/$id/edit'),
      headers: {...await _headers(), 'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );
    _checkOk(r);
  }

  Future<void> swapTake(String id, int take) async {
    final r = await _http.post(
      await _uri('/songs/$id/swap-take'),
      headers: {...await _headers(), 'Content-Type': 'application/json'},
      body: jsonEncode({'take': take}),
    );
    _checkOk(r);
  }

  Future<void> cancelSong(String id) async {
    final r = await _http.post(await _uri('/songs/$id/cancel'), headers: await _headers());
    _checkOk(r);
  }

  Future<void> resumeSong(String id) async {
    final r = await _http.post(await _uri('/songs/$id/resume'), headers: await _headers());
    _checkOk(r);
  }

  /// Video URL with the bearer token in the query string — same browser-
  /// header-restriction workaround as `videoUrl(runId)` above.
  Future<Uri> songVideoUrl(String id) async {
    final base = await _settings.baseUrl();
    final token = await _resolveToken();
    if (base == null || token == null) {
      throw FacelessApiException('Not configured');
    }
    return Uri.parse('${_stripTrailing(base)}/songs/$id/video?token=$token');
  }

  /// Download URL — same as songVideoUrl but with `download=1` so the
  /// server sends Content-Disposition: attachment. The browser saves
  /// the file instead of playing it inline.
  Future<Uri> songDownloadUrl(String id) async {
    final base = await _settings.baseUrl();
    final token = await _resolveToken();
    if (base == null || token == null) {
      throw FacelessApiException('Not configured');
    }
    return Uri.parse(
      '${_stripTrailing(base)}/songs/$id/video?token=$token&download=1',
    );
  }

  Future<Uri> songCoverUrl(String id) async {
    final base = await _settings.baseUrl();
    final token = await _resolveToken();
    if (base == null || token == null) {
      throw FacelessApiException('Not configured');
    }
    return Uri.parse('${_stripTrailing(base)}/songs/$id/cover?token=$token');
  }

  Future<Uri> songAudioUrl(String id, {int? take}) async {
    final base = await _settings.baseUrl();
    final token = await _resolveToken();
    if (base == null || token == null) {
      throw FacelessApiException('Not configured');
    }
    final takeParam = take != null ? '&take=$take' : '';
    return Uri.parse('${_stripTrailing(base)}/songs/$id/audio?token=$token$takeParam');
  }

  // ---------- personas ----------

  Future<List<Persona>> listPersonas() async {
    final r = await _http.get(await _uri('/personas'), headers: await _headers());
    return _parse(r, (j) => (j as List)
        .map((x) => Persona.fromJson(x as Map<String, dynamic>))
        .toList());
  }

  Future<Persona> createPersonaFromSong(
    String runId, {
    required String name,
    required String description,
    int? take,
  }) async {
    final body = <String, dynamic>{
      'name': name,
      'description': description,
      if (take != null) 'take': take,
    };
    final r = await _http.post(
      await _uri('/songs/$runId/save-persona'),
      headers: {...await _headers(), 'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );
    return _parse(r, (j) => Persona.fromJson(j as Map<String, dynamic>));
  }

  Future<void> deletePersona(String personaId) async {
    final r = await _http.delete(
      await _uri('/personas/$personaId'),
      headers: await _headers(),
    );
    _checkOk(r);
  }

  void close() => _http.close();
}
