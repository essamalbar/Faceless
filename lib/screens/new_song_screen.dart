import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../theme.dart';
import 'song_approve_screen.dart';

class NewSongScreen extends StatefulWidget {
  final FacelessApiClient client;
  // Optional pre-fills for "try this sample" entry points from the
  // empty state. When set, the form opens with these values populated
  // so the user is one tap away from generating.
  final String? initialTheme;
  final String? initialPresetLabel;
  const NewSongScreen({
    super.key,
    required this.client,
    this.initialTheme,
    this.initialPresetLabel,
  });

  @override
  State<NewSongScreen> createState() => _NewSongScreenState();
}

// Vetted style presets — tested against ai song.mp4 quality bar.
// Each entry: (label shown on chip, full style string stamped into the
// textfield when picked). Users can edit the stamped string before
// submitting. The lyrics LLM auto-generates a style if the field is
// left empty, but explicit presets give more consistent results.
const _kStylePresets = <(String, String)>[
  (
    'Romantic Arabic (reference)',
    'modern Arabic pop ballad, mid-tempo 88 BPM, male lyric-baritone vocal '
        'with expressive emotional delivery, warm intimate close-mic tone, '
        'oud + classical Arabic strings + piano + tasteful percussion, '
        'polished 2020s Arabic pop production, atmospheric and yearning, '
        'romantic contemplative not crying-sad, C# minor key',
  ),
  (
    'Sad Arabic Ballad',
    'Arabic emotional ballad, slow tempo 70 BPM, oud + classical Arabic '
        'strings + soft piano, male vocal warm and melancholic with vibrato, '
        'modern 2020s Arabic production, deeply emotional minor key',
  ),
  (
    'Khaleeji Romantic',
    'Khaleeji romantic ballad, mid-tempo 90 BPM, male vocal warm baritone '
        'smooth delivery, oud + qanun + classical Arabic strings + light '
        'percussion, traditional Gulf-style production with modern polish, '
        'romantic longing, minor key',
  ),
  (
    'Upbeat Arabic Pop',
    'modern Arabic pop, upbeat tempo 105 BPM, energetic male vocal, '
        'electronic drums + bass + synth + oud accents, polished 2020s '
        'Arabic pop production, optimistic danceable, major key',
  ),
  (
    'Acoustic Slow',
    'acoustic ballad, slow tempo 65 BPM, male vocal intimate and breathy, '
        'acoustic guitar + soft strings + minimal percussion, organic 2020s '
        'production, deeply emotional, minor key',
  ),
  (
    'English Pop Ballad',
    'modern English pop ballad, mid-tempo 80 BPM, male vocal expressive '
        'and emotional, piano + strings + light percussion, polished 2020s '
        'production, atmospheric and longing, minor key',
  ),
];


class _NewSongScreenState extends State<NewSongScreen> {
  final _themeCtrl = TextEditingController();
  final _lyricsCtrl = TextEditingController();
  final _styleCtrl = TextEditingController();
  String _language = 'ar';
  String _videoMode = 'static'; // 'static' | 'cinematic'
  String _vocalGender = 'm';   // 'm' / 'f' / 'auto'
  String? _sunoModel;          // null = use server default (V5_5)
  String? _personaId;          // null = no persona (let Suno pick)
  String? _selectedPreset;     // label of the chip that filled the style field
  List<Persona> _personas = [];
  bool _submitting = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadPersonas();
    // Apply optional pre-fills from the empty-state "try this" chips.
    if (widget.initialTheme != null) {
      _themeCtrl.text = widget.initialTheme!;
    }
    if (widget.initialPresetLabel != null) {
      final match = _kStylePresets.firstWhere(
        (e) => e.$1 == widget.initialPresetLabel,
        orElse: () => ('', ''),
      );
      if (match.$1.isNotEmpty) {
        _styleCtrl.text = match.$2;
        _selectedPreset = match.$1;
      }
    }
  }

  Future<void> _loadPersonas() async {
    try {
      final list = await widget.client.listPersonas();
      if (mounted) setState(() => _personas = list);
    } catch (_) {
      // Personas are optional; ignore listing errors silently
    }
  }

  @override
  void dispose() {
    _themeCtrl.dispose();
    _lyricsCtrl.dispose();
    _styleCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_themeCtrl.text.trim().isEmpty) {
      setState(() => _error = 'Theme is required');
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final runId = await widget.client.createSong(
        theme: _themeCtrl.text.trim(),
        customLyrics:
            _lyricsCtrl.text.trim().isEmpty ? null : _lyricsCtrl.text,
        styleHint: _styleCtrl.text.trim().isEmpty ? null : _styleCtrl.text,
        language: _language,
        personaId: _personaId,
        vocalGender: _vocalGender,
        sunoModel: _sunoModel,
        videoMode: _videoMode,
      );
      if (!mounted) return;
      Navigator.of(context).pushReplacement(MaterialPageRoute(
        builder: (_) =>
            SongApproveScreen(client: widget.client, runId: runId),
      ));
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = '$e';
        _submitting = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('New song')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Card(
              color: FacelessTheme.surface2,
              child: const Padding(
                padding: EdgeInsets.all(16),
                child: Text(
                  'The AI will write lyrics and a cover image prompt. '
                  'You can review and edit both before any credit is spent.',
                ),
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _themeCtrl,
              decoration: const InputDecoration(
                labelText: 'Theme',
                hintText: 'أغنية حزينة عن القمر',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _lyricsCtrl,
              maxLines: 6,
              decoration: const InputDecoration(
                labelText: 'Custom lyrics (optional)',
                hintText: 'Leave empty for AI',
                border: OutlineInputBorder(),
                alignLabelWithHint: true,
              ),
            ),
            const SizedBox(height: 16),
            // Style presets — quick fillers. Tap to stamp a vetted
            // style string into the textfield below; user can edit.
            Text(
              'Quick styles',
              style: Theme.of(context).textTheme.labelLarge,
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final (label, preset) in _kStylePresets)
                  FilterChip(
                    label: Text(label),
                    selected: _selectedPreset == label,
                    onSelected: (_) {
                      setState(() {
                        _styleCtrl.text = preset;
                        _selectedPreset = label;
                      });
                    },
                  ),
              ],
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _styleCtrl,
              maxLines: 3,
              decoration: const InputDecoration(
                labelText: 'Style hint',
                hintText: 'Pick a Quick style above, or type your own. '
                    'Leave empty for AI to auto-pick.',
                border: OutlineInputBorder(),
                alignLabelWithHint: true,
              ),
              onChanged: (_) {
                // Clear preset selection if user edits — they've
                // departed from the canned text.
                if (_selectedPreset != null) {
                  setState(() => _selectedPreset = null);
                }
              },
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              initialValue: _language,
              decoration: const InputDecoration(
                labelText: 'Language',
                border: OutlineInputBorder(),
              ),
              items: const [
                DropdownMenuItem(value: 'ar', child: Text('Arabic')),
                DropdownMenuItem(value: 'en', child: Text('English')),
                DropdownMenuItem(value: 'es', child: Text('Spanish')),
                DropdownMenuItem(value: 'fr', child: Text('French')),
                DropdownMenuItem(value: 'tr', child: Text('Turkish')),
              ],
              onChanged: (v) => setState(() => _language = v ?? 'ar'),
            ),
            const SizedBox(height: 16),
            // Vocal gender — defaults to Male to match the reference
            // ai song.mp4 sound. Pinning gender raises probability but
            // doesn't guarantee (per Suno docs).
            DropdownButtonFormField<String>(
              initialValue: _vocalGender,
              decoration: const InputDecoration(
                labelText: 'Vocal',
                border: OutlineInputBorder(),
              ),
              items: const [
                DropdownMenuItem(value: 'm', child: Text('Male')),
                DropdownMenuItem(value: 'f', child: Text('Female')),
                DropdownMenuItem(value: 'auto', child: Text('Auto (Suno picks)')),
              ],
              onChanged: (v) => setState(() => _vocalGender = v ?? 'm'),
            ),
            const SizedBox(height: 16),
            // Suno model picker. Default V5_5 is the highest quality
            // at design time. V5 has a slightly different voice
            // character — useful for A/B testing. V4_5 is the older
            // fallback for users on the cheaper tier.
            DropdownButtonFormField<String?>(
              initialValue: _sunoModel,
              decoration: const InputDecoration(
                labelText: 'Suno model',
                helperText: 'Newer = better quality. V3_5 is excluded '
                    '(obvious-AI sound).',
                border: OutlineInputBorder(),
              ),
              items: const [
                DropdownMenuItem(value: null,
                    child: Text('Default (V5_5)')),
                DropdownMenuItem(value: 'V5_5', child: Text('V5_5 (latest)')),
                DropdownMenuItem(value: 'V5', child: Text('V5')),
                DropdownMenuItem(value: 'V4_5', child: Text('V4_5')),
                DropdownMenuItem(value: 'V4', child: Text('V4 (legacy)')),
              ],
              onChanged: (v) => setState(() => _sunoModel = v),
            ),
            const SizedBox(height: 16),
            Text(
              'Video type',
              style: Theme.of(context).textTheme.labelLarge,
            ),
            const SizedBox(height: 8),
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(
                  value: 'static',
                  label: Text('Static cover · 1 credit'),
                ),
                ButtonSegment(
                  value: 'cinematic',
                  label: Text('Cinematic video · 3 credits'),
                ),
              ],
              selected: {_videoMode},
              onSelectionChanged: (s) =>
                  setState(() => _videoMode = s.first),
            ),
            const SizedBox(height: 16),
            // Voice picker — only shows once user has saved at least
            // one persona. Default is "Auto" which lets Suno pick.
            if (_personas.isNotEmpty)
              DropdownButtonFormField<String?>(
                initialValue: _personaId,
                decoration: const InputDecoration(
                  labelText: 'Voice',
                  helperText: 'Reuse a saved singer voice from a previous song',
                  border: OutlineInputBorder(),
                ),
                items: <DropdownMenuItem<String?>>[
                  const DropdownMenuItem(
                    value: null,
                    child: Text('Auto (let Suno pick)'),
                  ),
                  for (final p in _personas)
                    DropdownMenuItem(value: p.id, child: Text(p.name)),
                ],
                onChanged: (v) => setState(() => _personaId = v),
              ),
            if (_personas.isNotEmpty) const SizedBox(height: 16),
            const SizedBox(height: 8),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Text(
                  _error!,
                  style: TextStyle(
                      color: Theme.of(context).colorScheme.error),
                ),
              ),
            FilledButton.icon(
              onPressed: _submitting ? null : _submit,
              icon: _submitting
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.music_note),
              label: Text(_submitting ? 'Generating…' : 'Generate draft'),
            ),
            const SizedBox(height: 8),
            const Text(
              'You will review lyrics + cover prompt before any credit is spent.',
              style: TextStyle(fontSize: 12, color: FacelessTheme.textSecondary),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}
