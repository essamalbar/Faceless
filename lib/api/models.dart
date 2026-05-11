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
  final int balance;
  PlanInfo({required this.plan, required this.currentPeriodEnd, required this.balance});
  factory PlanInfo.fromJson(Map<String, dynamic> j) => PlanInfo(
        plan: j['plan'] as String,
        currentPeriodEnd: j['current_period_end'] as String?,
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
