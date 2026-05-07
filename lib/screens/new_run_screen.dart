import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../theme.dart';

/// Two modes:
///   - **AI Generate**: theme + premise + controls → AI generates the full
///     script. Pick dialect, art style, character template, and narration style.
///   - **Paste Script** (new): theme + title + per-beat fields. The pipeline
///     uses your text exactly. No LLM rewrite, no $0.05 of LLM spend.
class NewRunScreen extends StatelessWidget {
  final FacelessApiClient client;
  const NewRunScreen({super.key, required this.client});

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('New Episode'),
          bottom: const TabBar(
            indicatorColor: FacelessTheme.accent,
            labelColor: FacelessTheme.accent,
            unselectedLabelColor: FacelessTheme.textSecondary,
            tabs: [
              Tab(icon: Icon(Icons.tune), text: 'AI Generate'),
              Tab(icon: Icon(Icons.edit_note), text: 'Paste Script'),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            _AiGenerateTab(client: client),
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

const _validSpeakers = [
  'mother', 'son', 'father', 'doctor', 'neighbor',
  'grandmother', 'wife', 'daughter', 'friend', 'enemy',
];

// ---------------------------------------------------------------------------
// AI Generate — structured controls, AI-written script
// ---------------------------------------------------------------------------

class _AiGenerateTab extends StatefulWidget {
  final FacelessApiClient client;
  const _AiGenerateTab({required this.client});
  @override
  State<_AiGenerateTab> createState() => _AiGenerateTabState();
}

class _AiGenerateTabState extends State<_AiGenerateTab> {
  String _theme = 'folkloric';
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

  // (label, displayName) pairs for each dropdown's items
  static const _dialects = [
    ('msa', 'MSA (الفصحى)'),
    ('syrian', 'Syrian / Levantine'),
    ('egyptian', 'Egyptian'),
    ('khaliji', 'Khaliji / Gulf'),
    ('maghrebi', 'Maghrebi'),
    ('iraqi', 'Iraqi'),
  ];
  static const _artStyles = [
    ('pixar_3d', '3D Pixar'),
    ('anime_2d', '2D Anime'),
    ('cinematic_photo_real', 'Cinematic photo-real'),
    ('claymation', 'Claymation'),
    ('hand_drawn', 'Hand-drawn'),
    ('ghibli', 'Studio Ghibli'),
  ];
  static const _characterTemplates = [
    ('ai_choose', 'Let the AI choose'),
    ('human', 'Human cast'),
    ('fruit_sunstoriz', 'Fruit cast (Sunstoriz)'),
    ('animal', 'Animal cast'),
    ('surreal', 'Surreal creatures'),
  ];
  static const _endingTypes = [
    ('ai_choose', 'Let the AI choose'),
    ('open', 'Open-ended'),
    ('closed_tragic', 'Closed tragic'),
    ('closed_happy', 'Closed happy'),
    ('twist', 'Twist'),
  ];
  static const _narrationStyles = [
    ('cinematic', 'Cinematic (recommended)'),
    ('first_person_monologue', 'First-person monologue (TikTok)'),
    ('ai_choose', 'Let the AI choose'),
  ];

  Future<void> _submit() async {
    final premise = _premiseCtrl.text.trim();
    if (premise.length < 4) {
      setState(() => _error = 'Premise too short');
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
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Card(
            color: FacelessTheme.surface2,
            child: const Padding(
              padding: EdgeInsets.all(16),
              child: Text(
                'AI generates a script from your premise. Pick the dialect, art style, '
                'character template, and narration style; the writer follows your choices.',
              ),
            ),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _premiseCtrl,
            decoration: const InputDecoration(
              labelText: 'Premise (Arabic)',
              border: OutlineInputBorder(),
              alignLabelWithHint: true,
            ),
            textDirection: TextDirection.rtl,
            maxLines: 4,
          ),
          const SizedBox(height: 12),
          _kvDropdown<String>(
            label: 'Theme',
            value: _theme,
            items: _themes.map((t) => (t, t)).toList(),
            onChanged: (v) => setState(() => _theme = v ?? 'folkloric'),
          ),
          const SizedBox(height: 12),
          _kvDropdown<String>(
            label: 'Dialect',
            value: _dialect,
            items: _dialects,
            onChanged: (v) => setState(() => _dialect = v ?? 'msa'),
          ),
          const SizedBox(height: 12),
          _kvDropdown<String>(
            label: 'Art style',
            value: _artStyle,
            items: _artStyles,
            onChanged: (v) =>
                setState(() => _artStyle = v ?? 'cinematic_photo_real'),
          ),
          const SizedBox(height: 12),
          _kvDropdown<String>(
            label: 'Character template',
            value: _characterTemplate,
            items: _characterTemplates,
            onChanged: (v) =>
                setState(() => _characterTemplate = v ?? 'ai_choose'),
          ),
          const SizedBox(height: 12),
          _kvDropdown<String>(
            label: 'Ending type',
            value: _endingType,
            items: _endingTypes,
            onChanged: (v) =>
                setState(() => _endingType = v ?? 'ai_choose'),
          ),
          const SizedBox(height: 12),
          _kvDropdown<String>(
            label: 'Narration style',
            value: _narrationStyle,
            items: _narrationStyles,
            onChanged: (v) =>
                setState(() => _narrationStyle = v ?? 'cinematic'),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              const Text('Beats:'),
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
              const Text('Sec / beat:'),
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
            label: Text(_submitting ? 'Writing…' : 'Generate Script'),
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
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(
        'Parsed ${beatsRaw.length} beats '
        '(${switch (parsed.parseMethod) {
          ParseMethod.regex => "regex",
          ParseMethod.llmSplit => "AI split",
          ParseMethod.naiveFallback => "auto-segmented",
        }})',
      )),
    );
  }

  Future<void> _submit() async {
    final title = _titleCtrl.text.trim();
    if (title.isEmpty) {
      setState(() => _error = 'Title is required');
      return;
    }
    if (_beats.isEmpty) {
      setState(() => _error = 'At least one beat is required');
      return;
    }
    for (final b in _beats) {
      if (b.englishCtrl.text.trim().isEmpty) {
        setState(() => _error = 'Every beat needs a visual description (English)');
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
    } catch (e) {
      setState(() {
        _error = e.toString();
        _submitting = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Card(
                color: FacelessTheme.surface2,
                child: const Padding(
                  padding: EdgeInsets.all(16),
                  child: Text(
                    'Your dialogue is used VERBATIM — no LLM rewrite. Use '
                    'this for episode continuations where you want to control '
                    'every line.',
                  ),
                ),
              ),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: _openMarkdownPaster,
                icon: const Icon(Icons.content_paste),
                label: const Text('Paste from Markdown Script'),
                style: OutlinedButton.styleFrom(
                  side: BorderSide(
                      color: FacelessTheme.accent.withValues(alpha: 0.5)),
                  foregroundColor: FacelessTheme.accent,
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _titleCtrl,
                decoration: const InputDecoration(
                  labelText: 'Title (Arabic)',
                  hintText: 'مثلاً: العقد المقدس - الحلقة 4',
                  border: OutlineInputBorder(),
                ),
                textDirection: TextDirection.rtl,
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                initialValue: _theme,
                decoration: const InputDecoration(
                    labelText: 'Theme', border: OutlineInputBorder()),
                items: _themes
                    .map((t) => DropdownMenuItem(value: t, child: Text(t)))
                    .toList(),
                onChanged: (v) => setState(() => _theme = v ?? 'folkloric'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _premiseCtrl,
                decoration: const InputDecoration(
                  labelText: 'Story context (optional, Arabic)',
                  hintText: 'الحلقة الرابعة من سلسلة العقد',
                  border: OutlineInputBorder(),
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
                            ParseMethod.regex => 'Parsed from your markdown',
                            ParseMethod.llmSplit => 'Split by AI — review before saving',
                            ParseMethod.naiveFallback => 'Auto-segmented — review carefully',
                          },
                          style: const TextStyle(
                              fontSize: 11, fontWeight: FontWeight.w600),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: 4),
                child: Text('Beats',
                    style: TextStyle(
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
                label: Text('Add Beat (${_beats.length + 1})'),
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
                      ? 'Saving…'
                      : 'Use This Script (${_beats.length} beats, '
                          '~\$${_estimatedCost().toStringAsFixed(2)})'),
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
      setState(() => _error = 'Paste a real script (at least a few scenes).');
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
                  const Expanded(
                    child: Text('Paste Markdown Script',
                        style: TextStyle(
                            fontWeight: FontWeight.w700, fontSize: 18)),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.of(context).pop(),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              const Text(
                'Recognised format: **العنوان: ...** title, **المشهد N – ...** scene '
                'headings, and **SPEAKER:**\\n"dialogue" blocks. Stage directions '
                'in plain prose are kept as silent context. Your Arabic is '
                'preserved character-for-character.',
                style: TextStyle(
                    color: FacelessTheme.textSecondary, fontSize: 12),
              ),
              const SizedBox(height: 12),
              Expanded(
                child: TextField(
                  controller: _ctrl,
                  decoration: const InputDecoration(
                    border: OutlineInputBorder(),
                    hintText: '**العنوان: القلادة المقدسة – الحلقة 4**\n\n'
                        '**المشهد 1 – الفراغ**\nسكون مطلق...\n\n'
                        '**الشاب (بهمس):**\n"أنا… وين…؟"\n\n...',
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
                  const Text('Target beats:'),
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
                      child: const Text('Cancel'),
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
                      label: Text(_parsing ? 'Parsing…' : 'Parse to Beats'),
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
                    'BEAT ${index.toString().padLeft(2, "0")}',
                    style: const TextStyle(
                        color: FacelessTheme.accent,
                        fontWeight: FontWeight.w700,
                        fontSize: 11),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: DropdownButtonFormField<String>(
                    initialValue: _validSpeakers.contains(beat.speaker)
                        ? beat.speaker
                        : _validSpeakers.first,
                    decoration: const InputDecoration(
                      labelText: 'Speaker',
                      contentPadding: EdgeInsets.symmetric(
                          horizontal: 10, vertical: 0),
                    ),
                    isDense: true,
                    items: _validSpeakers
                        .map((s) =>
                            DropdownMenuItem(value: s, child: Text(s)))
                        .toList(),
                    onChanged: (v) {
                      if (v != null) {
                        beat.speaker = v;
                        onChanged();
                      }
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
              decoration: const InputDecoration(
                labelText: 'Character name (Arabic, optional)',
                hintText: 'e.g. خالد، فاطمة، أم يوسف',
                border: OutlineInputBorder(),
              ),
              textDirection: TextDirection.rtl,
              style: const TextStyle(fontSize: 15),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: beat.arabicCtrl,
              decoration: const InputDecoration(
                labelText: 'Arabic dialogue (leave empty for silent action beat)',
                border: OutlineInputBorder(),
                alignLabelWithHint: true,
              ),
              textDirection: TextDirection.rtl,
              maxLines: 3,
              style: const TextStyle(fontSize: 16, height: 1.6),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: beat.englishCtrl,
              decoration: const InputDecoration(
                labelText: 'Visual description (English) — required',
                hintText: 'e.g. Strawberry son in stone room, golden light, '
                    'looking at necklace',
                border: OutlineInputBorder(),
                alignLabelWithHint: true,
              ),
              maxLines: 3,
              style: const TextStyle(fontSize: 12),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                const Text('Clip duration:',
                    style: TextStyle(color: FacelessTheme.textSecondary)),
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
