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

  // ---------- youtube ----------

  /// Google OAuth consent URL — the app opens it via url_launcher and the
  /// flow finishes in the browser (server callback stores the token).
  /// Throws a 503 [FacelessApiException] with the operator's message when
  /// the OAuth client isn't configured server-side yet.
  Future<Uri> youtubeAuthStart() async {
    final r = await _http.get(await _uri('/auth/youtube/start'),
        headers: await _headers());
    return _parse(
        r, (j) => Uri.parse((j as Map<String, dynamic>)['url'] as String));
  }

  /// Connection status. `channelTitle` is null when disconnected.
  Future<({bool connected, String? channelTitle})> youtubeStatus() async {
    final r = await _http.get(await _uri('/auth/youtube/status'),
        headers: await _headers());
    return _parse(r, (j) {
      final m = j as Map<String, dynamic>;
      return (
        connected: (m['connected'] as bool?) ?? false,
        channelTitle: m['channel_title'] as String?,
      );
    });
  }

  Future<void> youtubeDisconnect() async {
    final r = await _http.delete(await _uri('/auth/youtube'),
        headers: await _headers());
    _checkOk(r); // 204 expected
  }

  /// Upload the song's final.mp4 to the connected channel. Returns the
  /// watch URL. Idempotent: a 409 "already published" (whose detail
  /// carries the existing URL) resolves to that URL instead of throwing.
  /// Other 409s ("youtube not connected", "song has no finished video
  /// yet") and 502 upload failures surface as [FacelessApiException]
  /// with the server's message.
  Future<String> publishYoutube(String runId) async {
    final r = await _http.post(
      await _uri('/songs/$runId/publish-youtube'),
      headers: await _headers(),
    );
    if (r.statusCode == 409) {
      // detail can be a plain string OR {detail, video_url} when the
      // song is already on YouTube — treat the latter as success.
      try {
        final body = jsonDecode(utf8.decode(r.bodyBytes));
        final detail = body is Map ? body['detail'] : null;
        if (detail is Map && detail['video_url'] is String) {
          return detail['video_url'] as String;
        }
      } catch (_) {
        // Fall through to the generic error path below.
      }
    }
    return _parse(
        r, (j) => (j as Map<String, dynamic>)['video_url'] as String);
  }

  // ---------- songs ----------

  Future<String> createSong({
    required String theme,
    String? customLyrics,
    String? styleHint,
    String language = 'ar',
    String? personaId,
    String vocalGender = 'm',
    String? sunoModel,
    String videoMode = 'static',
    String? artistId,
  }) async {
    final body = <String, dynamic>{
      'theme': theme,
      if (customLyrics != null && customLyrics.isNotEmpty) 'custom_lyrics': customLyrics,
      if (styleHint != null && styleHint.isNotEmpty) 'style_hint': styleHint,
      'language': language,
      if (personaId != null && personaId.isNotEmpty) 'persona_id': personaId,
      'vocal_gender': vocalGender,
      if (sunoModel != null) 'suno_model': sunoModel,
      'video_mode': videoMode,
      if (artistId != null) 'artist_id': artistId,
    };
    final r = await _http.post(
      await _uri('/songs'),
      headers: {...await _headers(), 'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );
    return _parse(r, (j) => (j as Map<String, dynamic>)['run_id'] as String);
  }

  /// Faithful cover from an UPLOADED audio file. Multipart POST — Suno's
  /// upload-cover endpoint keeps the source's melody and sings the (reviewed)
  /// words. Returns the new run id (status `analyzing`).
  Future<String> uploadCoverSong({
    required List<int> bytes,
    required String filename,
    String? instruction,
    String language = 'ar',
    String videoMode = 'static',
    String vocalGender = 'm',
    String? artistId,
  }) async {
    final req = http.MultipartRequest('POST', await _uri('/songs/upload-cover'));
    req.headers.addAll(await _headers()); // Authorization + Accept (no Content-Type)
    req.fields['language'] = language;
    req.fields['video_mode'] = videoMode;
    req.fields['vocal_gender'] = vocalGender;
    if (instruction != null && instruction.isNotEmpty) {
      req.fields['instruction'] = instruction;
    }
    if (artistId != null) req.fields['artist_id'] = artistId;
    req.files.add(http.MultipartFile.fromBytes('file', bytes, filename: filename));
    final r = await http.Response.fromStream(await _http.send(req));
    return _parse(r, (j) => (j as Map<String, dynamic>)['run_id'] as String);
  }

  // --- Artists (Artist Core) ---------------------------------------------

  Future<List<Artist>> listArtists() async {
    final r = await _http.get(await _uri('/artists'), headers: await _headers());
    return _parse(r, (j) => (j as List)
        .map((x) => Artist.fromJson(x as Map<String, dynamic>))
        .toList());
  }

  Future<Artist> createArtist({
    required String name,
    String? handle,
    String bio = '',
    String defaultStyle = '',
    String defaultLanguage = 'ar',
    String defaultVocalGender = 'm',
  }) async {
    final r = await _http.post(
      await _uri('/artists'),
      headers: {...await _headers(), 'Content-Type': 'application/json'},
      body: jsonEncode({
        'name': name,
        if (handle != null && handle.isNotEmpty) 'handle': handle,
        'bio': bio,
        'default_style': defaultStyle,
        'default_language': defaultLanguage,
        'default_vocal_gender': defaultVocalGender,
      }),
    );
    return _parse(r, (j) => Artist.fromJson(j as Map<String, dynamic>));
  }

  Future<Artist> patchArtist(String id, Map<String, dynamic> fields) async {
    final r = await _http.patch(
      await _uri('/artists/$id'),
      headers: {...await _headers(), 'Content-Type': 'application/json'},
      body: jsonEncode(fields),
    );
    return _parse(r, (j) => Artist.fromJson(j as Map<String, dynamic>));
  }

  Future<void> deleteArtist(String id) async {
    final r = await _http.delete(await _uri('/artists/$id'),
        headers: await _headers());
    if (r.statusCode != 204) {
      throw FacelessApiException('delete artist failed: ${r.body}',
          status: r.statusCode);
    }
  }

  /// One-step door: save the song take's voice as a persona AND create the
  /// artist wrapping it. The source song joins the discography.
  Future<Artist> createArtistFromSong({
    required String runId,
    required String name,
    String? handle,
    int? take,
  }) async {
    final r = await _http.post(
      await _uri('/artists/from-song'),
      headers: {...await _headers(), 'Content-Type': 'application/json'},
      body: jsonEncode({
        'run_id': runId,
        'name': name,
        if (handle != null && handle.isNotEmpty) 'handle': handle,
        if (take != null) 'take': take,
      }),
    );
    return _parse(r, (j) => Artist.fromJson(j as Map<String, dynamic>));
  }

  Future<Artist> uploadArtistAvatar({
    required String artistId,
    required List<int> bytes,
    required String filename,
  }) async {
    final req =
        http.MultipartRequest('POST', await _uri('/artists/$artistId/avatar'));
    req.headers.addAll(await _headers());
    req.files.add(http.MultipartFile.fromBytes('file', bytes, filename: filename));
    final r = await http.Response.fromStream(await _http.send(req));
    return _parse(r, (j) => Artist.fromJson(j as Map<String, dynamic>));
  }

  Future<Uri> artistAvatarUrl(String artistId) async {
    final base = await _settings.baseUrl();
    final token = await _resolveToken();
    return Uri.parse(
        '${_stripTrailing(base ?? '')}/artists/$artistId/avatar?token=$token');
  }

  /// Public artist page URL (shareable, no auth).
  Future<Uri> publicArtistUrl(String handle) async {
    final base = await _settings.baseUrl();
    return Uri.parse('${_stripTrailing(base ?? '')}/a/$handle');
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

  /// On-demand watermark backfill. Blocks the caller for ~3-6 minutes
  /// while ffmpeg re-assembles the song's final.mp4 with the brand
  /// mark PNG + container metadata. Returns the duration in seconds
  /// on success. UI should surface a long-wait banner.
  Future<double> reAssembleSong(String id) async {
    final r = await _http.post(
      await _uri('/songs/$id/re-assemble'),
      headers: await _headers(),
    );
    final j = _parse(r, (j) => j as Map<String, dynamic>);
    return (j['duration_s'] as num?)?.toDouble() ?? 0;
  }

  /// Server-Sent Events stream of song-status updates. Yields one
  /// map per state transition; the stream completes when the run
  /// reaches a terminal status (complete/failed/canceled). Returns
  /// `null` for the keys not present in a given event.
  ///
  /// Replaces the manual poll loop in song_detail_screen with a
  /// push channel — status flips arrive within ~200ms instead of
  /// 1.5s avg.
  Stream<Map<String, dynamic>> songEvents(String id) async* {
    final base = await _settings.baseUrl();
    final token = await _resolveToken();
    if (base == null || token == null) {
      throw FacelessApiException('Not configured');
    }
    final uri = Uri.parse(
      '${_stripTrailing(base)}/songs/$id/events?token=$token',
    );
    final req = http.Request('GET', uri);
    req.headers['Accept'] = 'text/event-stream';
    req.headers['Cache-Control'] = 'no-cache';
    final streamed = await _http.send(req);
    if (streamed.statusCode >= 400) {
      throw FacelessApiException(
        'SSE failed: ${streamed.statusCode}',
        status: streamed.statusCode,
      );
    }
    var buffer = '';
    await for (final chunk in streamed.stream.transform(utf8.decoder)) {
      buffer += chunk;
      // SSE events are separated by blank lines (\n\n).
      while (buffer.contains('\n\n')) {
        final idx = buffer.indexOf('\n\n');
        final block = buffer.substring(0, idx);
        buffer = buffer.substring(idx + 2);
        final dataLines = <String>[];
        String? eventName;
        for (final line in block.split('\n')) {
          if (line.startsWith('data: ')) {
            dataLines.add(line.substring(6));
          } else if (line.startsWith('event: ')) {
            eventName = line.substring(7);
          }
        }
        if (eventName == 'done' || eventName == 'timeout') return;
        if (dataLines.isEmpty) continue;
        try {
          final parsed = jsonDecode(dataLines.join('\n'));
          if (parsed is Map<String, dynamic>) yield parsed;
        } catch (_) {
          // Skip malformed events rather than break the stream
        }
      }
    }
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

  Future<ShareInfo> shareSong(String id) async {
    final r = await _http.post(
      await _uri('/songs/$id/share'),
      headers: await _headers(),
    );
    return _parse(r, (j) => ShareInfo.fromJson(j as Map<String, dynamic>));
  }

  Future<void> unshareSong(String id) async {
    final r = await _http.delete(
      await _uri('/songs/$id/share'),
      headers: await _headers(),
    );
    _checkOk(r);
  }

  Future<void> rerollSongTakes(String id) async {
    final r = await _http.post(
      await _uri('/songs/$id/reroll-takes'),
      headers: await _headers(),
    );
    _checkOk(r);
  }

  Future<void> regenerateSongCover(String id) async {
    final r = await _http.post(
      await _uri('/songs/$id/regenerate-cover'),
      headers: await _headers(),
    );
    _checkOk(r);
  }

  /// MP3 download URL with the bearer token in the query string.
  /// Browsers can't set Authorization headers on a plain link click;
  /// this URL is self-authenticating so url_launcher can hand it off
  /// to the OS download handler.
  Future<Uri> songAudioDownloadUrl(String id, {int? take}) async {
    final base = await _settings.baseUrl();
    final token = await _resolveToken();
    if (base == null || token == null) {
      throw FacelessApiException('Not configured');
    }
    final takeParam = take != null ? '&take=$take' : '';
    return Uri.parse(
      '${_stripTrailing(base)}/songs/$id/audio'
      '?token=$token&download=1$takeParam',
    );
  }

  /// Store-ready release package (zip: audio + cover + metadata + lyrics
  /// + checklist). Token in the query string — same browser-download
  /// pattern as [songDownloadUrl] / [scriptPdfUrl] so url_launcher can
  /// hand the URL straight to the OS/browser download handler.
  Future<Uri> releasePackageUrl(String runId) async {
    final base = await _settings.baseUrl();
    final token = await _resolveToken();
    if (base == null || token == null) {
      throw FacelessApiException('Not configured');
    }
    return Uri.parse(
      '${_stripTrailing(base)}/songs/$runId/release-package?token=$token',
    );
  }

  /// Toggle the manual "released" flag (the user confirms after uploading
  /// the package to a distributor). Returns the new value from the server.
  Future<bool> markReleased(String runId, bool released) async {
    final r = await _http.post(
      await _uri('/songs/$runId/mark-released'),
      headers: {...await _headers(), 'Content-Type': 'application/json'},
      body: jsonEncode({'released': released}),
    );
    return _parse(
        r, (j) => ((j as Map<String, dynamic>)['released'] as bool?) ?? false);
  }

  Future<void> deleteSong(String id) async {
    final r = await _http.delete(
      await _uri('/songs/$id'),
      headers: await _headers(),
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

  /// Cover URL. Pass thumb=true to get the small 256px JPEG variant
  /// (15-25 KB) for fast list rendering instead of the full 1.2 MB
  /// PNG. Used by the song-list home screen — full-size is reserved
  /// for the detail screen.
  Future<Uri> songCoverUrl(String id, {bool thumb = false}) async {
    final base = await _settings.baseUrl();
    final token = await _resolveToken();
    if (base == null || token == null) {
      throw FacelessApiException('Not configured');
    }
    final suffix = thumb ? '&thumb=1' : '';
    return Uri.parse(
      '${_stripTrailing(base)}/songs/$id/cover?token=$token$suffix',
    );
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
