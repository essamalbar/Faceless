/// Autonomous Artist Agent: the reasoning trace sheet — the full "what it
/// considered" observability view (spec §9, §10) behind a proposal card's
/// "Why?" affordance. Modal bottom sheet, mirrors `PerformSheet`'s shape
/// (GlassCard content, close button, `showModalBottomSheet` caller).
///
/// The trace JSON shape comes straight from `pipeline/agent.py`'s
/// `AgentRunner.run_cycle` (`trace["steps"]` — a list of `{"type": ...}`
/// dicts: `thinking`, `text`, `tool_call` {name,input}, `tool_result`
/// {name,result}, `error` {text}). Rendered generically by `type` so a new
/// step kind the backend adds later still shows *something* instead of
/// crashing the sheet.
library;

import 'dart:convert';

import 'package:flutter/material.dart';

import '../../api/client.dart';
import '../../l10n/l10n.dart';
import '../../theme.dart';
import '../../ui/brand.dart';
import '../../ui/primitives.dart';

class ReasoningTraceSheet extends StatefulWidget {
  final FacelessApiClient client;
  final String runId;
  /// Proposal title, shown as context above the sheet's own heading.
  final String title;
  const ReasoningTraceSheet({
    super.key,
    required this.client,
    required this.runId,
    required this.title,
  });

  @override
  State<ReasoningTraceSheet> createState() => _ReasoningTraceSheetState();
}

class _ReasoningTraceSheetState extends State<ReasoningTraceSheet> {
  late final Future<Map<String, dynamic>> _future =
      widget.client.agentTrace(widget.runId);

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final height =
        (MediaQuery.sizeOf(context).height * 0.85).clamp(360.0, 720.0);
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.viewInsetsOf(context).bottom,
          left: 16,
          right: 16,
          top: 16,
        ),
        child: SizedBox(
          height: height,
          child: GlassCard(
            child: FutureBuilder<Map<String, dynamic>>(
              future: _future,
              builder: (context, snap) {
                final header = _SheetHeader(title: widget.title);

                if (snap.connectionState == ConnectionState.waiting) {
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      header,
                      const Expanded(
                        child: Center(
                          child: CircularProgressIndicator(
                              color: FacelessTheme.accent),
                        ),
                      ),
                    ],
                  );
                }
                if (snap.hasError) {
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      header,
                      const SizedBox(height: 16),
                      Text(
                        l10n.agentFeedTraceLoadError('${snap.error}'),
                        style: const TextStyle(
                            color: FacelessTheme.danger, fontSize: 13),
                      ),
                    ],
                  );
                }

                final data = snap.data ?? const <String, dynamic>{};
                final available = data['available'] == true;
                final trace = data['trace'] as Map<String, dynamic>?;
                if (!available || trace == null) {
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      header,
                      Expanded(
                        child: Center(
                          child: Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 12),
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                const Icon(Icons.history_toggle_off,
                                    size: 34, color: FacelessTheme.faint),
                                const SizedBox(height: 10),
                                Text(
                                  l10n.agentFeedTraceUnavailableTitle,
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w700,
                                    color: FacelessTheme.textPrimary,
                                  ),
                                ),
                                const SizedBox(height: 6),
                                Text(
                                  l10n.agentFeedTraceUnavailableBody,
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(
                                    color: FacelessTheme.textSecondary,
                                    fontSize: 12.5,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ],
                  );
                }

                final steps = (trace['steps'] as List?) ?? const [];
                final stopped = trace['stopped'] as String?;
                final iterationsRaw = trace['iterations'];
                final iterations = iterationsRaw is num
                    ? iterationsRaw.toInt()
                    : steps.length;

                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    header,
                    const SizedBox(height: 10),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        BrandPill(l10n.agentFeedTraceIterations(iterations)),
                        if (stopped != null)
                          BrandPill(_stoppedLabel(l10n, stopped)),
                      ],
                    ),
                    const SizedBox(height: 12),
                    const Hairline(),
                    const SizedBox(height: 10),
                    Expanded(
                      child: steps.isEmpty
                          ? Center(
                              child: Text(
                                l10n.agentFeedTraceUnavailableBody,
                                style: const TextStyle(
                                    color: FacelessTheme.textSecondary),
                              ),
                            )
                          : ListView.separated(
                              padding: const EdgeInsets.only(bottom: 8),
                              itemCount: steps.length,
                              separatorBuilder: (_, _) =>
                                  const SizedBox(height: 10),
                              itemBuilder: (context, i) => _TraceStepTile(
                                step: (steps[i] as Map?)
                                        ?.cast<String, dynamic>() ??
                                    const <String, dynamic>{},
                              ),
                            ),
                    ),
                  ],
                );
              },
            ),
          ),
        ),
      ),
    );
  }

  String _stoppedLabel(AppLocalizations l10n, String stopped) {
    switch (stopped) {
      case 'finished':
        return l10n.agentFeedTraceStoppedFinished;
      case 'budget':
        return l10n.agentFeedTraceStoppedBudget;
      case 'max_iterations':
        return l10n.agentFeedTraceStoppedMaxIterations;
      case 'error':
        return l10n.agentFeedTraceStoppedError;
      default:
        return stopped;
    }
  }
}

class _SheetHeader extends StatelessWidget {
  final String title;
  const _SheetHeader({required this.title});

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Eyebrow(title),
              const SizedBox(height: 4),
              Text(l10n.agentFeedTraceTitle,
                  style: FacelessTheme.display(size: 18)),
            ],
          ),
        ),
        IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ],
    );
  }
}

/// One reasoning-trace step, rendered by `step['type']`. Unknown types fall
/// back to a compact JSON dump so the sheet never silently drops a step the
/// backend adds later.
class _TraceStepTile extends StatelessWidget {
  final Map<String, dynamic> step;
  const _TraceStepTile({required this.step});

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final type = step['type'] as String? ?? '';
    switch (type) {
      case 'thinking':
        return _StepCard(
          icon: Icons.psychology_outlined,
          color: FacelessTheme.accent2,
          label: l10n.agentFeedTraceStepThinking,
          body: (step['text'] as String?) ?? '',
          italic: true,
        );
      case 'text':
        return _StepCard(
          icon: Icons.chat_bubble_outline,
          color: FacelessTheme.textSecondary,
          label: l10n.agentFeedTraceStepMessage,
          body: (step['text'] as String?) ?? '',
        );
      case 'tool_call':
        return _StepCard(
          icon: Icons.build_outlined,
          color: FacelessTheme.accent,
          label: _humanizeTool(step['name'] as String? ?? ''),
          sublabel: l10n.agentFeedTraceStepRequest,
          body: _compactJson(step['input']),
        );
      case 'tool_result':
        return _StepCard(
          icon: Icons.check_circle_outline,
          color: FacelessTheme.success,
          label: _humanizeTool(step['name'] as String? ?? ''),
          sublabel: l10n.agentFeedTraceStepResult,
          body: _compactJson(step['result']),
        );
      case 'error':
        return _StepCard(
          icon: Icons.error_outline,
          color: FacelessTheme.danger,
          label: l10n.agentFeedTraceStepError,
          body: (step['text'] as String?) ?? '',
        );
      default:
        return _StepCard(
          icon: Icons.circle_outlined,
          color: FacelessTheme.faint,
          label: type.isEmpty ? '?' : _humanizeTool(type),
          body: _compactJson(step),
        );
    }
  }
}

class _StepCard extends StatelessWidget {
  final IconData icon;
  final Color color;
  final String label;
  final String? sublabel;
  final String body;
  final bool italic;
  const _StepCard({
    required this.icon,
    required this.color,
    required this.label,
    this.sublabel,
    required this.body,
    this.italic = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: FacelessTheme.glass,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: FacelessTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 15, color: color),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 11.5,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0.2,
                    color: color,
                  ),
                ),
              ),
              if (sublabel != null)
                Text(sublabel!,
                    style: const TextStyle(
                        fontSize: 10.5, color: FacelessTheme.faint)),
            ],
          ),
          if (body.trim().isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(
              body,
              style: TextStyle(
                fontSize: 12,
                height: 1.4,
                color: FacelessTheme.textSecondary,
                fontStyle: italic ? FontStyle.italic : FontStyle.normal,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// snake_case tool identifier -> "Title case with spaces" (e.g.
/// `queue_proposal` -> "Queue proposal"). Not localized — these are the
/// agent's internal tool names (`pipeline/agent.py:TOOLS`), developer
/// identifiers rather than user-facing copy, shown humanized for
/// readability in the observability view.
String _humanizeTool(String raw) {
  if (raw.isEmpty) return raw;
  final words = raw.split('_').where((w) => w.isNotEmpty);
  return words
      .map((w) => '${w[0].toUpperCase()}${w.substring(1)}')
      .join(' ');
}

/// Pretty-prints an arbitrary JSON-ish value (Map/List/primitive/null) for
/// display, capped so one enormous tool payload can't blow up the sheet.
String _compactJson(dynamic value) {
  if (value == null) return '';
  String text;
  try {
    text = const JsonEncoder.withIndent('  ').convert(value);
  } catch (_) {
    text = value.toString();
  }
  const cap = 800;
  return text.length > cap ? '${text.substring(0, cap)}…' : text;
}
