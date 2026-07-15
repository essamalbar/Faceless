import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../l10n/l10n.dart';
import '../theme.dart';

/// Per-beat editor — fix Claude's slips without regenerating from scratch.
/// Only available when status=awaiting_approval (server enforces; we hide the
/// button otherwise). Saves a new script.json server-side.
class EditScriptScreen extends StatefulWidget {
  final FacelessApiClient client;
  final String runId;
  final ScriptResponse initialScript;
  const EditScriptScreen({
    super.key,
    required this.client,
    required this.runId,
    required this.initialScript,
  });

  @override
  State<EditScriptScreen> createState() => _EditScriptScreenState();
}

class _EditScriptScreenState extends State<EditScriptScreen> {
  // Suggestions only — speaker is now a free-form string (PA-1 loosened the
  // backend enum). The user can type any role label; these are just quick picks.
  static const _speakerSuggestions = [
    'narrator', 'mother', 'son', 'father', 'doctor', 'neighbor',
    'grandmother', 'wife', 'daughter', 'friend', 'enemy',
  ];

  late TextEditingController _titleCtrl;
  late List<_EditableBeat> _beats;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _titleCtrl = TextEditingController(text: widget.initialScript.title);
    _beats = widget.initialScript.beats
        .map((b) => _EditableBeat.fromBeat(b))
        .toList();
  }

  Future<void> _save() async {
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.client.editScript(
        widget.runId,
        title: _titleCtrl.text.trim().isEmpty ? null : _titleCtrl.text.trim(),
        beats: _beats.map((b) => b.toJson()).toList(),
      );
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } catch (e) {
      setState(() {
        _error = e.toString();
        _saving = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = context.l10n;
    return Scaffold(
      appBar: AppBar(
        title: Text(l.editScriptTitle),
        actions: [
          TextButton(
            onPressed: _saving ? null : _save,
            child: Text(l.commonSave,
                style: const TextStyle(
                    color: FacelessTheme.accent,
                    fontWeight: FontWeight.w700)),
          ),
        ],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            TextField(
              controller: _titleCtrl,
              decoration: InputDecoration(
                labelText: l.editScriptTitleLabel,
                border: const OutlineInputBorder(),
              ),
              textDirection: TextDirection.rtl,
            ),
            const SizedBox(height: 16),
            ..._beats.asMap().entries.map((e) => _BeatEditor(
                  index: e.key + 1,
                  beat: e.value,
                  speakerSuggestions: _speakerSuggestions,
                  onChanged: () => setState(() {}),
                )),
            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(_error!,
                  style: TextStyle(
                      color: Theme.of(context).colorScheme.error)),
            ],
            const SizedBox(height: 80),
          ],
        ),
      ),
    );
  }

  @override
  void dispose() {
    _titleCtrl.dispose();
    for (final b in _beats) {
      b.dispose();
    }
    super.dispose();
  }
}

class _EditableBeat {
  final TextEditingController arabicCtrl;
  final TextEditingController englishCtrl;
  final TextEditingController characterNameCtrl;
  String speaker;
  double clipDuration;

  _EditableBeat({
    required this.arabicCtrl,
    required this.englishCtrl,
    required this.characterNameCtrl,
    required this.speaker,
    required this.clipDuration,
  });

  factory _EditableBeat.fromBeat(ScriptBeat b) => _EditableBeat(
        arabicCtrl: TextEditingController(text: b.arabic),
        englishCtrl: TextEditingController(text: b.englishMotion),
        characterNameCtrl: TextEditingController(text: b.characterName),
        speaker: b.speaker,
        clipDuration: b.clipDurationS,
      );

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

class _BeatEditor extends StatelessWidget {
  final int index;
  final _EditableBeat beat;
  final List<String> speakerSuggestions;
  final VoidCallback onChanged;
  const _BeatEditor({
    required this.index,
    required this.beat,
    required this.speakerSuggestions,
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
                      if (query.isEmpty) return speakerSuggestions;
                      return speakerSuggestions.where(
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
                labelText: l.editScriptArabicDialogueLabel,
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
                labelText: l.editScriptVisualDescLabel,
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
