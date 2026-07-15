import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../l10n/l10n.dart';
import '../theme.dart';
import '../widgets/paywall_dialog.dart';

/// Two modes:
///   - **AI Generate**: theme + premise + controls → AI generates the full
///     script. Pick dialect, art style, character template, and narration style.
///   - **Paste Script** (new): theme + title + per-beat fields. The pipeline
///     uses your text exactly. No LLM rewrite, no $0.05 of LLM spend.
class NewRunScreen extends StatelessWidget {
  final FacelessApiClient client;
  final String? initialTheme;
  const NewRunScreen({super.key, required this.client, this.initialTheme});

  @override
  Widget build(BuildContext context) {
    final l = context.l10n;
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: Text(l.newRunTitle),
          bottom: TabBar(
            indicatorColor: FacelessTheme.accent,
            labelColor: FacelessTheme.accent,
            unselectedLabelColor: FacelessTheme.textSecondary,
            tabs: [
              Tab(icon: const Icon(Icons.tune), text: l.newRunTabAiGenerate),
              Tab(
                  icon: const Icon(Icons.edit_note),
                  text: l.newRunTabPasteScript),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            _AiGenerateTab(client: client, initialTheme: initialTheme),
            _PasteScriptTab(client: client),
          ],
        ),
      ),
    );
  }
}

const _themes = [
  'folkloric', 'domestic', 'urban', 'workplace',
  'travel', 'wilderness', 'tech', 'memory',
];

/// Localized display name for a theme id (the id itself is the API value).
String _themeLabel(AppLocalizations l, String theme) => switch (theme) {
      'folkloric' => l.homeThemeFolkloric,
      'domestic' => l.homeThemeDomestic,
      'urban' => l.homeThemeUrban,
      'workplace' => l.homeThemeWorkplace,
      'travel' => l.homeThemeTravel,
      'wilderness' => l.homeThemeWilderness,
      'tech' => l.homeThemeTech,
      'memory' => l.homeThemeMemory,
      _ => theme,
    };

// Suggestions only — speaker is now a free-form string (PA-1 loosened the
// backend enum). The user can type any role label; these are just quick picks.
const _speakerSuggestions = [
  'narrator', 'mother', 'son', 'father', 'doctor', 'neighbor',
  'grandmother', 'wife', 'daughter', 'friend', 'enemy',
];

// ---------------------------------------------------------------------------
// AI Generate — structured controls, AI-written script
// ---------------------------------------------------------------------------

class _AiGenerateTab extends StatefulWidget {
  final FacelessApiClient client;
  final String? initialTheme;
  const _AiGenerateTab({required this.client, this.initialTheme});
  @override
  State<_AiGenerateTab> createState() => _AiGenerateTabState();
}

class _AiGenerateTabState extends State<_AiGenerateTab> {
  late String _theme = widget.initialTheme ?? 'folkloric';
  String _dialect = 'msa';
  String _artStyle = 'cinematic_photo_real';
  String _characterTemplate = 'ai_choose';
  String _endingType = 'ai_choose';
  String _narrationStyle = 'cinematic';
  int _numBeats = 8;
  int _perBeatSeconds = 8;
  final _premiseCtrl = TextEditingController();
  bool _submitting = false;
  String? _error;

  // (value, displayName) pairs for each dropdown's items — values are the
  // API payload ids, display names are localized.
  List<(String, String)> _dialects(AppLocalizations l) => [
        ('msa', l.newRunDialectMsa),
        ('syrian', l.newRunDialectSyrian),
        ('egyptian', l.newRunDialectEgyptian),
        ('khaliji', l.newRunDialectKhaliji),
        ('maghrebi', l.newRunDialectMaghrebi),
        ('iraqi', l.newRunDialectIraqi),
      ];
  List<(String, String)> _artStyles(AppLocalizations l) => [
        ('pixar_3d', l.newRunArtPixar3d),
        ('anime_2d', l.newRunArtAnime2d),
        ('cinematic_photo_real', l.newRunArtCinematic),
        ('claymation', l.newRunArtClaymation),
        ('hand_drawn', l.newRunArtHandDrawn),
        ('ghibli', l.newRunArtGhibli),
      ];
  List<(String, String)> _characterTemplates(AppLocalizations l) => [
        ('ai_choose', l.newRunAiChoose),
        ('human', l.newRunCharHuman),
        ('fruit_sunstoriz', l.newRunCharFruit),
        ('animal', l.newRunCharAnimal),
        ('surreal', l.newRunCharSurreal),
      ];
  List<(String, String)> _endingTypes(AppLocalizations l) => [
        ('ai_choose', l.newRunAiChoose),
        ('open', l.newRunEndingOpen),
        ('closed_tragic', l.newRunEndingClosedTragic),
        ('closed_happy', l.newRunEndingClosedHappy),
        ('twist', l.newRunEndingTwist),
      ];
  List<(String, String)> _narrationStyles(AppLocalizations l) => [
        ('cinematic', l.newRunNarrCinematic),
        ('first_person_monologue', l.newRunNarrFirstPerson),
        ('ai_choose', l.newRunAiChoose),
      ];

  Future<void> _submit() async {
    final premise = _premiseCtrl.text.trim();
    if (premise.length < 4) {
      setState(() => _error = context.l10n.newRunPremiseTooShort);
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final run = await widget.client.createFreeformRun(
        theme: _theme,
        premise: premise,
        dialect: _dialect,
        artStyle: _artStyle,
        characterTemplate: _characterTemplate,
        endingType: _endingType,
        numBeats: _numBeats,
        perBeatSeconds: _perBeatSeconds,
        narrationStyle: _narrationStyle,
      );
      if (!mounted) return;
      Navigator.of(context).pop<RunSummary?>(run);
    } on InsufficientCreditsException catch (e) {
      if (mounted) {
        setState(() => _submitting = false);
        await PaywallDialog.show(context, balance: e.balance, required: e.required);
      }
    } catch (e) {
      setState(() {
        _error = e.toString();
        _submitting = false;
      });
    }
  }

  Widget _kvDropdown<T>({
    required String label,
    required T value,
    required List<(T, String)> items,
    required ValueChanged<T?> onChanged,
  }) =>
      DropdownButtonFormField<T>(
        initialValue: value,
        decoration: InputDecoration(
            labelText: label, border: const OutlineInputBorder()),
        items: items
            .map((p) => DropdownMenuItem<T>(value: p.$1, child: Text(p.$2)))
            .toList(),
        onChanged: onChanged,
      );

  @override
  Widget build(BuildContext context) {
    final l = context.l10n;
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Card(
            color: FacelessTheme.surface2,
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Text(l.newRunAiExplainer),
            ),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _premiseCtrl,
            decoration: InputDecoration(
              labelText: l.newRunPremiseLabel,
              border: const OutlineInputBorder(),
              alignLabelWithHint: true,
            ),
            textDirection: TextDirection.rtl,
            maxLines: 4,
          ),
          const SizedBox(height: 12),
          _kvDropdown<String>(
            label: l.newRunThemeLabel,
            value: _theme,
            items: _themes.map((t) => (t, _themeLabel(l, t))).toList(),
            onChanged: (v) => setState(() => _theme = v ?? 'folkloric'),
          ),
          const SizedBox(height: 12),
          _kvDropdown<String>(
            label: l.newRunDialectLabel,
            value: _dialect,
            items: _dialects(l),
            onChanged: (v) => setState(() => _dialect = v ?? 'msa'),
          ),
          const SizedBox(height: 12),
          _kvDropdown<String>(
            label: l.newRunArtStyleLabel,
            value: _artStyle,
            items: _artStyles(l),
            onChanged: (v) =>
                setState(() => _artStyle = v ?? 'cinematic_photo_real'),
          ),
          const SizedBox(height: 12),
          _kvDropdown<String>(
            label: l.newRunCharacterTemplateLabel,
            value: _characterTemplate,
            items: _characterTemplates(l),
            onChanged: (v) =>
                setState(() => _characterTemplate = v ?? 'ai_choose'),
          ),
          const SizedBox(height: 12),
          _kvDropdown<String>(
            label: l.newRunEndingTypeLabel,
            value: _endingType,
            items: _endingTypes(l),
            onChanged: (v) =>
                setState(() => _endingType = v ?? 'ai_choose'),
          ),
          const SizedBox(height: 12),
          _kvDropdown<String>(
            label: l.newRunNarrationStyleLabel,
            value: _narrationStyle,
            items: _narrationStyles(l),
            onChanged: (v) =>
                setState(() => _narrationStyle = v ?? 'cinematic'),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Text(l.newRunBeatsLabel),
              Expanded(
                child: Slider(
                  min: 4, max: 15, divisions: 11,
                  value: _numBeats.toDouble(),
                  label: '$_numBeats',
                  onChanged: (v) => setState(() => _numBeats = v.round()),
                ),
              ),
              Text('$_numBeats'),
            ],
          ),
          Row(
            children: [
              Text(l.newRunSecPerBeatLabel),
              Expanded(
                child: Slider(
                  min: 4, max: 10, divisions: 6,
                  value: _perBeatSeconds.toDouble(),
                  label: '${_perBeatSeconds}s',
                  onChanged: (v) =>
                      setState(() => _perBeatSeconds = v.round()),
                ),
              ),
              Text('${_perBeatSeconds}s'),
            ],
          ),
          const SizedBox(height: 16),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text(_error!,
                  style: TextStyle(
                      color: Theme.of(context).colorScheme.error)),
            ),
          FilledButton.icon(
            onPressed: _submitting ? null : _submit,
            icon: _submitting
                ? const SizedBox(
                    width: 16, height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.tune),
            label:
                Text(_submitting ? l.newRunWriting : l.newRunGenerateScript),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _premiseCtrl.dispose();
    super.dispose();
  }
}

// ---------------------------------------------------------------------------
// Paste Script — your dialogue, verbatim
// ---------------------------------------------------------------------------

class _PasteBeat {
  final TextEditingController arabicCtrl;
  final TextEditingController englishCtrl;
  final TextEditingController characterNameCtrl;
  String speaker;
  double clipDuration;
  _PasteBeat({String speaker = 'mother', double clip = 8.0,
              String characterName = ''})
      : arabicCtrl = TextEditingController(),
        englishCtrl = TextEditingController(),
        characterNameCtrl = TextEditingController(text: characterName),
        speaker = speaker,
        clipDuration = clip;
  Map<String, dynamic> toJson() => {
        'arabic': arabicCtrl.text,
        'english_motion': englishCtrl.text,
        'speaker': speaker,
        'clip_duration_s': clipDuration,
        'character_name': characterNameCtrl.text,
      };
  void dispose() {
    arabicCtrl.dispose();
    englishCtrl.dispose();
    characterNameCtrl.dispose();
  }
}

class _PasteScriptTab extends StatefulWidget {
  final FacelessApiClient client;
  const _PasteScriptTab({required this.client});

  @override
  State<_PasteScriptTab> createState() => _PasteScriptTabState();
}

class _PasteScriptTabState extends State<_PasteScriptTab> {
  final _titleCtrl = TextEditingController();
  final _premiseCtrl = TextEditingController();
  String _theme = 'folkloric';
  final List<_PasteBeat> _beats = [_PasteBeat()];
  bool _submitting = false;
  String? _error;
  ParseMethod? _lastParseMethod;

  void _addBeat() {
    setState(() => _beats.add(_PasteBeat()));
  }

  void _removeBeat(int i) {
    setState(() {
      _beats[i].dispose();
      _beats.removeAt(i);
    });
  }

  Future<void> _openMarkdownPaster() async {
    final parsed = await showDialog<ParseScriptResponse>(
      context: context,
      barrierDismissible: false,
      builder: (_) => _MarkdownPasteDialog(client: widget.client),
    );
    if (parsed == null || !mounted) return;
    final title = parsed.title;
    final beatsRaw = parsed.beats;
    setState(() {
      if (title.isNotEmpty) _titleCtrl.text = title;
      // Replace existing beats with parsed ones
      for (final b in _beats) {
        b.dispose();
      }
      _beats.clear();
      for (final raw in beatsRaw) {
        final b = _PasteBeat(
          speaker: raw.speaker,
          clip: raw.clipDurationS,
          characterName: raw.characterName,
        );
        b.arabicCtrl.text = raw.arabic;
        b.englishCtrl.text = raw.englishMotion;
        _beats.add(b);
      }
      if (_beats.isEmpty) _beats.add(_PasteBeat());
      _error = null;
      _lastParseMethod = parsed.parseMethod;
    });
    final l = context.l10n;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(
        l.newRunParsedBeats(
          beatsRaw.length,
          switch (parsed.parseMethod) {
            ParseMethod.regex => l.newRunMethodRegex,
            ParseMethod.llmSplit => l.newRunMethodAiSplit,
            ParseMethod.naiveFallback => l.newRunMethodAuto,
          },
        ),
      )),
    );
  }

  Future<void> _submit() async {
    final l = context.l10n;
    final title = _titleCtrl.text.trim();
    if (title.isEmpty) {
      setState(() => _error = l.newRunTitleRequired);
      return;
    }
    if (_beats.isEmpty) {
      setState(() => _error = l.newRunBeatRequired);
      return;
    }
    for (final b in _beats) {
      if (b.englishCtrl.text.trim().isEmpty) {
        setState(() => _error = l.newRunVisualRequired);
        return;
      }
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final run = await widget.client.createRunFromScript(
        title: title,
        theme: _theme,
        premise: _premiseCtrl.text.trim(),
        beats: _beats.map((b) => b.toJson()).toList(),
      );
      if (!mounted) return;
      Navigator.of(context).pop<RunSummary?>(run);
    } on InsufficientCreditsException catch (e) {
      if (mounted) {
        setState(() => _submitting = false);
        await PaywallDialog.show(context, balance: e.balance, required: e.required);
      }
    } catch (e) {
      setState(() {
        _error = e.toString();
        _submitting = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = context.l10n;
    return Column(
      children: [
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Card(
                color: FacelessTheme.surface2,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Text(l.newRunPasteExplainer),
                ),
              ),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: _openMarkdownPaster,
                icon: const Icon(Icons.content_paste),
                label: Text(l.newRunPasteFromMarkdown),
                style: OutlinedButton.styleFrom(
                  side: BorderSide(
                      color: FacelessTheme.accent.withValues(alpha: 0.5)),
                  foregroundColor: FacelessTheme.accent,
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _titleCtrl,
                decoration: InputDecoration(
                  labelText: l.newRunTitleLabel,
                  hintText: l.newRunTitleHint,
                  border: const OutlineInputBorder(),
                ),
                textDirection: TextDirection.rtl,
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                initialValue: _theme,
                decoration: InputDecoration(
                    labelText: l.newRunThemeLabel,
                    border: const OutlineInputBorder()),
                items: _themes
                    .map((t) => DropdownMenuItem(
                        value: t, child: Text(_themeLabel(l, t))))
                    .toList(),
                onChanged: (v) => setState(() => _theme = v ?? 'folkloric'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _premiseCtrl,
                decoration: InputDecoration(
                  labelText: l.newRunStoryContextLabel,
                  hintText: l.newRunStoryContextHint,
                  border: const OutlineInputBorder(),
                ),
                textDirection: TextDirection.rtl,
                maxLines: 2,
              ),
              const SizedBox(height: 24),
              if (_lastParseMethod != null) ...[
                Padding(
                  padding: const EdgeInsets.only(top: 4, bottom: 12, left: 4),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    decoration: BoxDecoration(
                      color: switch (_lastParseMethod!) {
                        ParseMethod.regex =>
                            Colors.green.withValues(alpha: 0.15),
                        ParseMethod.llmSplit =>
                            Colors.orange.withValues(alpha: 0.18),
                        ParseMethod.naiveFallback =>
                            Colors.amber.withValues(alpha: 0.22),
                      },
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          switch (_lastParseMethod!) {
                            ParseMethod.regex => Icons.check_circle,
                            ParseMethod.llmSplit => Icons.smart_toy_outlined,
                            ParseMethod.naiveFallback => Icons.warning_amber,
                          },
                          size: 16,
                          color: switch (_lastParseMethod!) {
                            ParseMethod.regex => Colors.green,
                            ParseMethod.llmSplit => Colors.orange,
                            ParseMethod.naiveFallback => Colors.amber.shade700,
                          },
                        ),
                        const SizedBox(width: 6),
                        Text(
                          switch (_lastParseMethod!) {
                            ParseMethod.regex => l.newRunBadgeParsedMarkdown,
                            ParseMethod.llmSplit => l.newRunBadgeAiSplit,
                            ParseMethod.naiveFallback =>
                                l.newRunBadgeAutoSegmented,
                          },
                          style: const TextStyle(
                              fontSize: 11, fontWeight: FontWeight.w600),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 4),
                child: Text(l.newRunBeatsSection,
                    style: const TextStyle(
                        color: FacelessTheme.textSecondary,
                        fontWeight: FontWeight.w700,
                        fontSize: 12,
                        letterSpacing: 1.2)),
              ),
              const SizedBox(height: 8),
              ..._beats.asMap().entries.map((e) => _PasteBeatEditor(
                    index: e.key + 1,
                    beat: e.value,
                    onRemove:
                        _beats.length > 1 ? () => _removeBeat(e.key) : null,
                    onChanged: () => setState(() {}),
                  )),
              OutlinedButton.icon(
                onPressed: _addBeat,
                icon: const Icon(Icons.add),
                label: Text(l.newRunAddBeat(_beats.length + 1)),
              ),
              const SizedBox(height: 80),
            ],
          ),
        ),
        Container(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
          decoration: BoxDecoration(
            color: FacelessTheme.surface,
            border: Border(
                top: BorderSide(
                    color: Colors.white.withValues(alpha: 0.05))),
          ),
          child: Column(
            children: [
              if (_error != null) ...[
                Text(_error!,
                    style: TextStyle(
                        color: Theme.of(context).colorScheme.error)),
                const SizedBox(height: 8),
              ],
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: _submitting ? null : _submit,
                  icon: _submitting
                      ? const SizedBox(
                          width: 16, height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.check),
                  label: Text(_submitting
                      ? l.newRunSaving
                      : l.newRunUseScript(
                          _beats.length,
                          '\$${_estimatedCost().toStringAsFixed(2)}',
                        )),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  double _estimatedCost() {
    final secs = _beats.fold<double>(0, (sum, b) => sum + b.clipDuration);
    return secs * 0.10 + 0.05;
  }

  @override
  void dispose() {
    _titleCtrl.dispose();
    _premiseCtrl.dispose();
    for (final b in _beats) {
      b.dispose();
    }
    super.dispose();
  }
}

class _MarkdownPasteDialog extends StatefulWidget {
  final FacelessApiClient client;
  const _MarkdownPasteDialog({required this.client});
  @override
  State<_MarkdownPasteDialog> createState() => _MarkdownPasteDialogState();
}

class _MarkdownPasteDialogState extends State<_MarkdownPasteDialog> {
  final _ctrl = TextEditingController();
  bool _parsing = false;
  String? _error;
  int _targetBeats = 8;

  Future<void> _parse() async {
    final raw = _ctrl.text.trim();
    if (raw.length < 20) {
      setState(() => _error = context.l10n.newRunPasteRealScript);
      return;
    }
    setState(() {
      _parsing = true;
      _error = null;
    });
    try {
      final ParseScriptResponse result = await widget.client.parseScript(raw, targetBeats: _targetBeats);
      if (!mounted) return;
      Navigator.of(context).pop<ParseScriptResponse>(result);
    } catch (e) {
      setState(() {
        _error = e.toString();
        _parsing = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = context.l10n;
    return Dialog(
      insetPadding: const EdgeInsets.all(16),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 720, maxHeight: 700),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(l.newRunPasteDialogTitle,
                        style: const TextStyle(
                            fontWeight: FontWeight.w700, fontSize: 18)),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.of(context).pop(),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                l.newRunPasteFormatHelp,
                style: const TextStyle(
                    color: FacelessTheme.textSecondary, fontSize: 12),
              ),
              const SizedBox(height: 12),
              Expanded(
                child: TextField(
                  controller: _ctrl,
                  decoration: InputDecoration(
                    border: const OutlineInputBorder(),
                    hintText: l.newRunPasteHint,
                    alignLabelWithHint: true,
                  ),
                  textDirection: TextDirection.rtl,
                  maxLines: null,
                  expands: true,
                  style: const TextStyle(fontSize: 13, height: 1.5),
                ),
              ),
              if (_error != null) ...[
                const SizedBox(height: 8),
                Text(_error!,
                    style: TextStyle(
                        color: Theme.of(context).colorScheme.error)),
              ],
              const SizedBox(height: 8),
              Row(
                children: [
                  Text(l.newRunTargetBeats),
                  Expanded(
                    child: Slider(
                      min: 4, max: 15, divisions: 11,
                      value: _targetBeats.toDouble(),
                      label: '$_targetBeats',
                      onChanged: (v) => setState(() => _targetBeats = v.round()),
                    ),
                  ),
                  Text('$_targetBeats'),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: _parsing
                          ? null
                          : () => Navigator.of(context).pop(),
                      child: Text(l.commonCancel),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    flex: 2,
                    child: FilledButton.icon(
                      onPressed: _parsing ? null : _parse,
                      icon: _parsing
                          ? const SizedBox(
                              width: 16, height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2))
                          : const Icon(Icons.auto_fix_high),
                      label: Text(
                          _parsing ? l.newRunParsing : l.newRunParseToBeats),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }
}

class _PasteBeatEditor extends StatelessWidget {
  final int index;
  final _PasteBeat beat;
  final VoidCallback? onRemove;
  final VoidCallback onChanged;
  const _PasteBeatEditor({
    required this.index,
    required this.beat,
    required this.onRemove,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final l = context.l10n;
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: FacelessTheme.accent.withValues(alpha: 0.18),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    l.newRunBeatBadge(index.toString().padLeft(2, '0')),
                    style: const TextStyle(
                        color: FacelessTheme.accent,
                        fontWeight: FontWeight.w700,
                        fontSize: 11),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Autocomplete<String>(
                    initialValue: TextEditingValue(text: beat.speaker),
                    optionsBuilder: (TextEditingValue textEditingValue) {
                      final query = textEditingValue.text.toLowerCase();
                      if (query.isEmpty) return _speakerSuggestions;
                      return _speakerSuggestions.where(
                        (s) => s.toLowerCase().contains(query),
                      );
                    },
                    fieldViewBuilder:
                        (context, controller, focusNode, onFieldSubmitted) {
                      return TextField(
                        controller: controller,
                        focusNode: focusNode,
                        decoration: InputDecoration(
                          labelText: l.newRunSpeakerLabel,
                          hintText: l.newRunSpeakerHint,
                          contentPadding: const EdgeInsets.symmetric(
                              horizontal: 10, vertical: 0),
                        ),
                        onChanged: (v) {
                          beat.speaker = v.trim();
                          onChanged();
                        },
                      );
                    },
                    onSelected: (s) {
                      beat.speaker = s;
                      onChanged();
                    },
                  ),
                ),
                if (onRemove != null)
                  IconButton(
                    icon: const Icon(Icons.close),
                    color: FacelessTheme.danger,
                    onPressed: onRemove,
                  ),
              ],
            ),
            const SizedBox(height: 12),
            TextField(
              controller: beat.characterNameCtrl,
              decoration: InputDecoration(
                labelText: l.newRunCharacterNameLabel,
                hintText: l.newRunCharacterNameHint,
                border: const OutlineInputBorder(),
              ),
              textDirection: TextDirection.rtl,
              style: const TextStyle(fontSize: 15),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: beat.arabicCtrl,
              decoration: InputDecoration(
                labelText: l.newRunArabicDialogueLabel,
                border: const OutlineInputBorder(),
                alignLabelWithHint: true,
              ),
              textDirection: TextDirection.rtl,
              maxLines: 3,
              style: const TextStyle(fontSize: 16, height: 1.6),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: beat.englishCtrl,
              decoration: InputDecoration(
                labelText: l.newRunVisualDescLabel,
                hintText: l.newRunVisualDescHint,
                border: const OutlineInputBorder(),
                alignLabelWithHint: true,
              ),
              maxLines: 3,
              style: const TextStyle(fontSize: 12),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Text(l.newRunClipDurationLabel,
                    style:
                        const TextStyle(color: FacelessTheme.textSecondary)),
                Expanded(
                  child: Slider(
                    min: 4, max: 12, divisions: 16,
                    value: beat.clipDuration.clamp(4, 12),
                    label: '${beat.clipDuration.toStringAsFixed(1)}s',
                    onChanged: (v) {
                      beat.clipDuration = v;
                      onChanged();
                    },
                  ),
                ),
                Text('${beat.clipDuration.toStringAsFixed(0)}s',
                    style: const TextStyle(
                        fontFeatures: [FontFeature.tabularFigures()])),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
