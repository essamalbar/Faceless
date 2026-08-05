/// Wire-format models for the Faceless Pipeline API.
///
/// Field names mirror `pipeline/api.py` Pydantic schemas. Anything optional on
/// the server side is nullable here.
library;

class RunStatus {
  static const creating = 'creating';
  static const awaitingApproval = 'awaiting_approval';
  static const awaitingVeoApproval = 'awaiting_veo_approval';   // NEW
  static const runningPaid = 'running_paid';
  static const complete = 'complete';
  static const failed = 'failed';
}

class RunProgress {
  final String stage;          // "script" | "character_sheet" | "video" | "captions" | "assemble"
  final int clipsDone;
  final int clipsTotal;
  RunProgress({
    required this.stage,
    required this.clipsDone,
    required this.clipsTotal,
  });
  factory RunProgress.fromJson(Map<String, dynamic> j) => RunProgress(
        stage: j['stage'] as String,
        clipsDone: j['clips_done'] as int? ?? 0,
        clipsTotal: j['clips_total'] as int? ?? 0,
      );
  /// 0..1, useable as a LinearProgressIndicator value when in `video` stage.
  /// Returns null for indeterminate (other stages).
  double? get fractional {
    if (stage != 'video' || clipsTotal == 0) return null;
    return (clipsDone / clipsTotal).clamp(0.0, 1.0);
  }
}

class RunSummary {
  final String id;
  final String status;
  final String? title;
  final String? theme;
  final String? premise;
  final String? createdAt;
  final bool hasVideo;
  final String? lastError;
  final String? errorHint;          // human-readable suggested fix
  final RunProgress? progress;

  RunSummary({
    required this.id,
    required this.status,
    this.title,
    this.theme,
    this.premise,
    this.createdAt,
    required this.hasVideo,
    this.lastError,
    this.errorHint,
    this.progress,
  });

  factory RunSummary.fromJson(Map<String, dynamic> j) => RunSummary(
        id: j['id'] as String,
        status: j['status'] as String,
        title: j['title'] as String?,
        theme: j['theme'] as String?,
        premise: j['premise'] as String?,
        createdAt: j['created_at'] as String?,
        hasVideo: j['has_video'] as bool? ?? false,
        lastError: j['last_error'] as String?,
        errorHint: j['error_hint'] as String?,
        progress: j['progress'] == null
            ? null
            : RunProgress.fromJson(j['progress'] as Map<String, dynamic>),
      );

  bool get isComplete => status == RunStatus.complete;
  bool get isAwaitingApproval => status == RunStatus.awaitingApproval;
  bool get isAwaitingVeoApproval => status == RunStatus.awaitingVeoApproval;  // NEW
  bool get isFailed => status == RunStatus.failed;
  bool get isRunning =>
      status == RunStatus.creating || status == RunStatus.runningPaid;
}

class ScriptBeat {
  final String arabic;
  final String englishMotion;
  final String speaker;
  final double clipDurationS;
  final String characterName;

  ScriptBeat({
    required this.arabic,
    required this.englishMotion,
    required this.speaker,
    required this.clipDurationS,
    this.characterName = '',
  });

  factory ScriptBeat.fromJson(Map<String, dynamic> j) => ScriptBeat(
        arabic: j['arabic'] as String? ?? '',
        englishMotion: j['english_motion'] as String? ?? '',
        speaker: j['speaker'] as String? ?? 'narrator',
        clipDurationS: (j['clip_duration_s'] as num?)?.toDouble() ?? 8.0,
        characterName: j['character_name'] as String? ?? '',
      );

  bool get isSilent => arabic.trim().isEmpty;
}

/// Used by the paste-script and freeform new-run flows. Mirrors the wire
/// shape `pipeline.api.PasteScriptBeat`.
class PasteScriptBeat {
  final String arabic;
  final String englishMotion;
  final String speaker;
  final double clipDurationS;
  final String characterName;

  PasteScriptBeat({
    required this.arabic,
    required this.englishMotion,
    required this.speaker,
    required this.clipDurationS,
    this.characterName = '',
  });

  factory PasteScriptBeat.fromJson(Map<String, dynamic> j) => PasteScriptBeat(
        arabic: j['arabic'] as String? ?? '',
        englishMotion: j['english_motion'] as String? ?? '',
        speaker: j['speaker'] as String? ?? 'mother',
        clipDurationS: (j['clip_duration_s'] as num?)?.toDouble() ?? 8.0,
        characterName: j['character_name'] as String? ?? '',
      );

  Map<String, dynamic> toJson() => {
        'arabic': arabic,
        'english_motion': englishMotion,
        'speaker': speaker,
        'clip_duration_s': clipDurationS,
        'character_name': characterName,
      };
}

enum ParseMethod { regex, llmSplit, naiveFallback }

ParseMethod parseMethodFromString(String s) => switch (s) {
      'regex' => ParseMethod.regex,
      'llm_split' => ParseMethod.llmSplit,
      'naive_fallback' => ParseMethod.naiveFallback,
      _ => ParseMethod.regex,
    };

class ParseScriptResponse {
  final String title;
  final List<PasteScriptBeat> beats;
  final ParseMethod parseMethod;

  ParseScriptResponse({
    required this.title,
    required this.beats,
    required this.parseMethod,
  });

  factory ParseScriptResponse.fromJson(Map<String, dynamic> j) =>
      ParseScriptResponse(
        title: j['title'] as String? ?? '',
        beats: ((j['beats'] as List?) ?? [])
            .map((b) => PasteScriptBeat.fromJson(b as Map<String, dynamic>))
            .toList(),
        parseMethod:
            parseMethodFromString(j['parse_method'] as String? ?? 'regex'),
      );
}

class ScriptResponse {
  final String title;
  final List<ScriptBeat> beats;
  final double targetDurationS;
  final double estimatedCostUsd;

  ScriptResponse({
    required this.title,
    required this.beats,
    required this.targetDurationS,
    required this.estimatedCostUsd,
  });

  factory ScriptResponse.fromJson(Map<String, dynamic> j) => ScriptResponse(
        title: j['title'] as String? ?? '',
        beats: ((j['beats'] as List?) ?? [])
            .map((b) => ScriptBeat.fromJson(b as Map<String, dynamic>))
            .toList(),
        targetDurationS: (j['target_duration_s'] as num?)?.toDouble() ?? 0.0,
        estimatedCostUsd: (j['estimated_cost_usd'] as num?)?.toDouble() ?? 0.0,
      );
}

class SpendRow {
  final String runId;
  final String? title;
  final double usd;
  SpendRow({required this.runId, this.title, required this.usd});
  factory SpendRow.fromJson(Map<String, dynamic> j) => SpendRow(
        runId: j['run_id'] as String,
        title: j['title'] as String?,
        usd: (j['usd'] as num).toDouble(),
      );
}

class SpendSummary {
  final double totalUsd;
  final int runCount;
  final List<SpendRow> byRun;
  SpendSummary({
    required this.totalUsd,
    required this.runCount,
    required this.byRun,
  });
  factory SpendSummary.fromJson(Map<String, dynamic> j) => SpendSummary(
        totalUsd: (j['total_usd'] as num).toDouble(),
        runCount: j['run_count'] as int? ?? 0,
        byRun: ((j['by_run'] as List?) ?? [])
            .map((r) => SpendRow.fromJson(r as Map<String, dynamic>))
            .toList(),
      );
}


class ApprovalAck {
  final String runId;
  final String status;
  final bool startedPaidStages;

  ApprovalAck({
    required this.runId,
    required this.status,
    required this.startedPaidStages,
  });

  factory ApprovalAck.fromJson(Map<String, dynamic> j) => ApprovalAck(
        runId: j['run_id'] as String,
        status: j['status'] as String,
        startedPaidStages: j['started_paid_stages'] as bool? ?? false,
      );
}

class Balance {
  final int balance;
  Balance({required this.balance});
  factory Balance.fromJson(Map<String, dynamic> j) => Balance(balance: j['balance'] as int);
}

class PlanInfo {
  final String plan;            // 'free' | 'starter' | 'creator' | 'pro'
  final String? currentPeriodEnd;
  final bool cancelAtPeriodEnd;
  final String paymentStatus;   // 'active' | 'past_due' (dunning flag)
  final int balance;
  PlanInfo({
    required this.plan,
    required this.currentPeriodEnd,
    required this.balance,
    this.cancelAtPeriodEnd = false,
    this.paymentStatus = 'active',
  });
  bool get isPastDue => paymentStatus == 'past_due';
  factory PlanInfo.fromJson(Map<String, dynamic> j) => PlanInfo(
        plan: j['plan'] as String,
        currentPeriodEnd: j['current_period_end'] as String?,
        cancelAtPeriodEnd: (j['cancel_at_period_end'] as bool?) ?? false,
        paymentStatus: (j['payment_status'] as String?) ?? 'active',
        balance: j['balance'] as int,
      );
}

class CreditTx {
  final String id;
  final int amount;
  final String kind;
  final String? referenceId;
  final String? description;
  final String createdAt;
  CreditTx({
    required this.id,
    required this.amount,
    required this.kind,
    this.referenceId,
    this.description,
    required this.createdAt,
  });
  factory CreditTx.fromJson(Map<String, dynamic> j) => CreditTx(
        id: j['id'] as String,
        amount: j['amount'] as int,
        kind: j['kind'] as String,
        referenceId: j['reference_id'] as String?,
        description: j['description'] as String?,
        createdAt: j['created_at'] as String,
      );
}

// ---------- song models ----------

class SongSummary {
  final String id;
  final String status;
  final String? title;
  final String? theme;
  final String createdAt;
  final bool hasVideo;
  final int? chosenTake;
  final String? lastError;
  // generating_song / generating_cover / assembling — when status
  // is "failed", tells the UI which stage was running so it can
  // show an actionable retry hint (e.g. "Suno failed — retry will
  // re-charge" vs "Cover failed — retry is free").
  final String? failureStage;
  // True when the song's final.mp4 was assembled with the brand-mark
  // watermark + MP4 metadata. Songs from before that feature land here
  // as false; the song-detail screen surfaces an "Apply watermark"
  // CTA in that case so the user can backfill on demand without us
  // rerunning the whole bucket sweep.
  final bool watermarked;
  final String videoMode;
  // Artist Core: which artist this song belongs to (null = unassigned).
  final String? artistId;
  final String? artistName;
  // Morning drafts: origin + the brief's "why now" line.
  final String? source;
  final String? trendRationale;
  // Distribution: manual "live on stores" flag toggled by the user
  // after uploading the release package to a distributor.
  final bool released;
  // YouTube publish: watch URL once the song was uploaded (manually or
  // via artist auto-publish). Null = not on YouTube yet.
  final String? youtubeUrl;

  SongSummary({
    required this.id,
    required this.status,
    required this.title,
    required this.theme,
    required this.createdAt,
    required this.hasVideo,
    required this.chosenTake,
    required this.lastError,
    this.failureStage,
    this.watermarked = false,
    this.videoMode = 'static',
    this.artistId,
    this.artistName,
    this.released = false,
    this.youtubeUrl,
    this.source,
    this.trendRationale,
  });

  factory SongSummary.fromJson(Map<String, dynamic> j) => SongSummary(
        id: j['id'] as String,
        status: j['status'] as String,
        title: j['title'] as String?,
        theme: j['theme'] as String?,
        createdAt: (j['created_at'] as String?) ?? '',
        hasVideo: (j['has_video'] as bool?) ?? false,
        chosenTake: j['chosen_take'] as int?,
        lastError: j['last_error'] as String?,
        failureStage: j['failure_stage'] as String?,
        watermarked: (j['watermarked'] as bool?) ?? false,
        videoMode: (j['video_mode'] as String?) ?? 'static',
        artistId: j['artist_id'] as String?,
        artistName: j['artist_name'] as String?,
        released: (j['released'] as bool?) ?? false,
        youtubeUrl: j['youtube_url'] as String?,
        source: j['source'] as String?,
        trendRationale: j['trend_rationale'] as String?,
      );
}

/// Artist Core: a virtual artist — identity wrapper around a persona voice.
class Artist {
  final String id;
  final String name;
  final String handle;
  final String bio;
  final String? personaId;
  final String? avatarRunId;
  final String? avatarUpload;
  final String defaultStyle;
  final String defaultLanguage;
  final String defaultVocalGender;
  // Arabic quality: preferred dialect for new songs ('' = unset).
  final String defaultDialect;
  final String createdAt;
  final int songCount;
  // YouTube: when true, finished songs by this artist are uploaded to
  // the connected channel automatically.
  final bool autoPublishYoutube;
  final bool morningDrafts;

  Artist({
    required this.id,
    required this.name,
    required this.handle,
    this.bio = '',
    this.personaId,
    this.avatarRunId,
    this.avatarUpload,
    this.defaultStyle = '',
    this.defaultLanguage = 'ar',
    this.defaultVocalGender = 'm',
    this.defaultDialect = '',
    required this.createdAt,
    this.songCount = 0,
    this.autoPublishYoutube = false,
    this.morningDrafts = false,
  });

  bool get hasAvatar => avatarUpload != null || avatarRunId != null;

  factory Artist.fromJson(Map<String, dynamic> j) => Artist(
        id: j['id'] as String,
        name: j['name'] as String,
        handle: j['handle'] as String,
        bio: (j['bio'] as String?) ?? '',
        personaId: j['persona_id'] as String?,
        avatarRunId: j['avatar_run_id'] as String?,
        avatarUpload: j['avatar_upload'] as String?,
        defaultStyle: (j['default_style'] as String?) ?? '',
        defaultLanguage: (j['default_language'] as String?) ?? 'ar',
        defaultVocalGender: (j['default_vocal_gender'] as String?) ?? 'm',
        defaultDialect: (j['default_dialect'] as String?) ?? '',
        createdAt: (j['created_at'] as String?) ?? '',
        songCount: (j['song_count'] as int?) ?? 0,
        autoPublishYoutube: (j['auto_publish_youtube'] as bool?) ?? false,
        morningDrafts: (j['morning_drafts'] as bool?) ?? false,
      );
}

class SongScript {
  final String title;
  final String lyrics;
  final String stylePrompt;
  final String coverPrompt;
  final String language;
  final int costCredits;
  final double costUsd;
  final String videoMode;

  SongScript({
    required this.title,
    required this.lyrics,
    required this.stylePrompt,
    required this.coverPrompt,
    required this.language,
    required this.costCredits,
    required this.costUsd,
    this.videoMode = 'static',
  });

  factory SongScript.fromJson(Map<String, dynamic> j) => SongScript(
        title: j['title'] as String,
        lyrics: j['lyrics'] as String,
        stylePrompt: j['style_prompt'] as String,
        coverPrompt: j['cover_prompt'] as String,
        language: j['language'] as String,
        costCredits: j['cost_credits'] as int,
        costUsd: (j['cost_usd'] as num).toDouble(),
        videoMode: (j['video_mode'] as String?) ?? 'static',
      );
}

class ShareInfo {
  final String token;
  final String url;

  ShareInfo({required this.token, required this.url});

  factory ShareInfo.fromJson(Map<String, dynamic> j) => ShareInfo(
        token: j['token'] as String,
        url: j['url'] as String,
      );
}

class Persona {
  final String id;
  final String name;
  final String description;
  final String sourceRunId;
  final int sourceTake;
  final String createdAt;

  Persona({
    required this.id,
    required this.name,
    required this.description,
    required this.sourceRunId,
    required this.sourceTake,
    required this.createdAt,
  });

  factory Persona.fromJson(Map<String, dynamic> j) => Persona(
        id: j['id'] as String,
        name: j['name'] as String,
        description: j['description'] as String,
        sourceRunId: j['source_run_id'] as String,
        sourceTake: j['source_take'] as int,
        createdAt: (j['created_at'] as String?) ?? '',
      );
}

/// Trend Engine: a timely, ready-to-approve song brief.
class TrendBrief {
  final String id;
  final String titleIdea;
  final String theme;
  final String styleHint;
  final String language;
  final String rationale;

  TrendBrief({
    required this.id,
    required this.titleIdea,
    required this.theme,
    required this.styleHint,
    required this.language,
    required this.rationale,
  });

  factory TrendBrief.fromJson(Map<String, dynamic> j) => TrendBrief(
        id: j['id'] as String,
        titleIdea: (j['title_idea'] as String?) ?? '',
        theme: (j['theme'] as String?) ?? '',
        styleHint: (j['style_hint'] as String?) ?? '',
        language: (j['language'] as String?) ?? 'ar',
        rationale: (j['rationale'] as String?) ?? '',
      );
}
