import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../l10n/l10n.dart';
import '../theme.dart';
import '../ui/brand.dart';
import 'song_approve_screen.dart';

class NewSongScreen extends StatefulWidget {
  final FacelessApiClient client;
  // Optional pre-fills for "try this sample" entry points from the
  // empty state. When set, the form opens with these values populated
  // so the user is one tap away from generating.
  final String? initialTheme;
  final String? initialPresetLabel;
  // Trend Engine: brief prefills (style stamped only if the field is empty).
  final String? initialStyleHint;
  final String? initialLanguage;
  // Artist Core: opening from an ArtistScreen preselects the artist so the
  // song lands in their discography with their defaults prefilled.
  final Artist? initialArtist;
  const NewSongScreen({
    super.key,
    required this.client,
    this.initialTheme,
    this.initialPresetLabel,
    this.initialStyleHint,
    this.initialLanguage,
    this.initialArtist,
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

/// Localized display label for a preset. Lookups/selection stay keyed by the
/// original English constant so `initialPresetLabel` entry points keep working.
String _presetLabel(AppLocalizations l10n, String key) => switch (key) {
      'Romantic Arabic (reference)' => l10n.newSongPresetRomanticArabic,
      'Sad Arabic Ballad' => l10n.newSongPresetSadArabicBallad,
      'Khaleeji Romantic' => l10n.newSongPresetKhaleejiRomantic,
      'Upbeat Arabic Pop' => l10n.newSongPresetUpbeatArabicPop,
      'Acoustic Slow' => l10n.newSongPresetAcousticSlow,
      'English Pop Ballad' => l10n.newSongPresetEnglishPopBallad,
      _ => key,
    };

class _NewSongScreenState extends State<NewSongScreen> {
  final _themeCtrl = TextEditingController();
  final _lyricsCtrl = TextEditingController();
  final _styleCtrl = TextEditingController();
  String _createMode = 'theme'; // 'theme' | 'upload'
  Uint8List? _pickedBytes; // upload mode: the chosen audio file
  String? _pickedName;
  String _language = 'ar';
  String? _dialect;           // Arabic dialect (null = auto; ar-only)
  String _videoMode = 'static'; // 'static' | 'cinematic'
  String _qualityTier = 'standard'; // 'standard' | 'premium' (best-of-N + A&R + master)
  double _audioWeight = 0.8;   // cover faithfulness (Kie audioWeight)
  String _vocalGender = 'm';   // 'm' / 'f' / 'auto'
  String? _sunoModel;          // null = use server default (V5_5)
  String? _personaId;          // null = no persona (let Suno pick)
  String? _selectedPreset;     // label of the chip that filled the style field
  List<Persona> _personas = [];
  Artist? _artist;             // selected artist (null = none)
  List<Artist> _artists = [];
  bool _artistsLoading = true;
  bool _submitting = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadPersonas();
    _loadArtists();
    if (widget.initialArtist != null) {
      _applyArtist(widget.initialArtist!);
    }
    // Apply optional pre-fills from the empty-state "try this" chips.
    if (widget.initialTheme != null) {
      _themeCtrl.text = widget.initialTheme!;
    }
    // Trend-brief prefills — never clobber an artist's stamped style.
    if (widget.initialStyleHint != null && _styleCtrl.text.trim().isEmpty) {
      _styleCtrl.text = widget.initialStyleHint!;
    }
    if (widget.initialLanguage != null) {
      _language = widget.initialLanguage!;
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

  Future<void> _loadArtists() async {
    try {
      final list = await widget.client.listArtists();
      if (mounted) {
        setState(() {
          _artists = list;
          _artistsLoading = false;
        });
      }
    } catch (_) {
      // Artists are optional; the picker row simply stays hidden.
      if (mounted) setState(() => _artistsLoading = false);
    }
  }

  /// Select an artist: prefill their defaults. Explicit user edits win —
  /// the style field is only stamped when still empty.
  void _applyArtist(Artist a) {
    setState(() {
      _artist = a;
      _language = a.defaultLanguage;
      _vocalGender = a.defaultVocalGender;
      if (a.defaultDialect.isNotEmpty) {
        _dialect = a.defaultDialect;
      }
      if (_styleCtrl.text.trim().isEmpty && a.defaultStyle.isNotEmpty) {
        _styleCtrl.text = a.defaultStyle;
      }
    });
  }

  @override
  void dispose() {
    _themeCtrl.dispose();
    _lyricsCtrl.dispose();
    _styleCtrl.dispose();
    super.dispose();
  }

  Future<void> _pickAudio() async {
    final l10n = context.l10n;
    try {
      // FileType.custom + explicit extensions is more reliable across
      // Android OEM file providers than FileType.audio (which silently
      // no-ops on some devices). withData loads bytes for the upload.
      final res = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: const [
          'mp3', 'm4a', 'aac', 'wav', 'flac', 'ogg', 'opus'
        ],
        withData: true,
      );
      if (res == null || res.files.isEmpty) return; // user cancelled
      final f = res.files.first;
      if (f.bytes == null) {
        setState(() => _error = l10n.newSongFileReadError);
        return;
      }
      setState(() {
        _pickedBytes = f.bytes;
        _pickedName = f.name;
        _error = null;
      });
    } catch (e) {
      // Surface the failure instead of doing nothing (e.g. a stale build
      // without the plugin throws MissingPluginException here).
      setState(() => _error = l10n.newSongFilePickerError('$e'));
    }
  }

  Future<void> _submit() async {
    if (_createMode == 'upload') {
      if (_pickedBytes == null) {
        setState(() => _error = context.l10n.newSongChooseAudioError);
        return;
      }
    } else {
      if (_themeCtrl.text.trim().isEmpty) {
        setState(() => _error = context.l10n.newSongThemeRequired);
        return;
      }
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final String runId;
      if (_createMode == 'upload') {
        runId = await widget.client.uploadCoverSong(
          bytes: _pickedBytes!,
          filename: _pickedName ?? 'reference.mp3',
          audioWeight: _audioWeight,
          instruction: _styleCtrl.text.trim().isEmpty ? null : _styleCtrl.text,
          language: _language,
          videoMode: _videoMode,
          vocalGender: _vocalGender,
          artistId: _artist?.id,
        );
      } else {
        runId = await widget.client.createSong(
          theme: _themeCtrl.text.trim(),
          customLyrics:
              _lyricsCtrl.text.trim().isEmpty ? null : _lyricsCtrl.text,
          styleHint: _styleCtrl.text.trim().isEmpty ? null : _styleCtrl.text,
          language: _language,
          personaId: _personaId,
          vocalGender: _vocalGender,
          sunoModel: _sunoModel,
          videoMode: _videoMode,
          artistId: _artist?.id,
          dialect: _language == 'ar' ? _dialect : null,
          qualityTier: _qualityTier,
        );
      }
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

  bool get _showArtistRow =>
      !_artistsLoading && (_artists.isNotEmpty || _artist != null);

  /// Chips to render: the loaded list, plus the preselected artist if the
  /// listing hasn't caught up with it (or failed).
  List<Artist> get _artistChoices {
    final sel = _artist;
    if (sel != null && !_artists.any((a) => a.id == sel.id)) {
      return [sel, ..._artists];
    }
    return _artists;
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.newSongTitle)),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Artist picker — release the song as one of your artists.
            // Hidden while loading, and when there are no artists at all.
            if (_showArtistRow) ...[
              Text(
                l10n.artistPickerLabel,
                style: Theme.of(context).textTheme.labelLarge,
              ),
              const SizedBox(height: 8),
              SizedBox(
                height: 40,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  children: [
                    ChoiceChip(
                      label: Text(l10n.artistPickerNone),
                      selected: _artist == null,
                      onSelected: (_) => setState(() => _artist = null),
                    ),
                    for (final a in _artistChoices)
                      Padding(
                        padding: const EdgeInsetsDirectional.only(start: 8),
                        child: ChoiceChip(
                          label: Text(a.name),
                          selected: _artist?.id == a.id,
                          onSelected: (_) => _applyArtist(a),
                        ),
                      ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
            ],
            // Mode selector — Write a theme vs Upload a song (cover).
            SegmentedButton<String>(
              segments: [
                ButtonSegment(
                  value: 'theme',
                  label: Text(l10n.newSongModeTheme),
                  icon: const Icon(Icons.edit_note),
                ),
                ButtonSegment(
                  value: 'upload',
                  label: Text(l10n.newSongModeUpload),
                  icon: const Icon(Icons.upload_file),
                ),
              ],
              selected: {_createMode},
              onSelectionChanged: (s) =>
                  setState(() => _createMode = s.first),
            ),
            const SizedBox(height: 16),
            Card(
              color: FacelessTheme.surface2,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Text(
                  _createMode == 'upload'
                      ? l10n.newSongUploadExplainer
                      : l10n.newSongThemeExplainer,
                ),
              ),
            ),
            const SizedBox(height: 16),
            if (_createMode == 'upload') ...[
              // Upload-&-cover path: pick an audio file + optional "your touch".
              OutlinedButton.icon(
                onPressed: _submitting ? null : _pickAudio,
                icon: const Icon(Icons.audiotrack),
                label: Text(_pickedName ?? l10n.newSongChooseAudioFile),
              ),
              if (_pickedName != null)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(
                    l10n.newSongSelectedFile(_pickedName!),
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
              const SizedBox(height: 16),
              // Faithfulness knob → Kie audioWeight: how closely the cover
              // follows the source audio. Default 0.8 (covers exist to match).
              Text(l10n.newSongFaithfulness,
                  style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: FacelessTheme.textSecondary)),
              Slider(
                value: _audioWeight,
                min: 0.0,
                max: 1.0,
                divisions: 20,
                label: _audioWeight.toStringAsFixed(2),
                onChanged: _submitting
                    ? null
                    : (v) => setState(() => _audioWeight = v),
              ),
              Text(
                _audioWeight >= 0.6
                    ? l10n.newSongFaithfulnessHigh
                    : l10n.newSongFaithfulnessLow,
                style: const TextStyle(
                    fontSize: 12, color: FacelessTheme.faint),
              ),
              const SizedBox(height: 16),
            ] else ...[
              // Theme path: theme + custom lyrics fields.
              TextField(
                controller: _themeCtrl,
                decoration: InputDecoration(
                  labelText: l10n.newSongThemeLabel,
                  hintText: l10n.newSongThemeHint,
                  border: const OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _lyricsCtrl,
                maxLines: 6,
                decoration: InputDecoration(
                  labelText: l10n.newSongCustomLyricsLabel,
                  hintText: l10n.newSongCustomLyricsHint,
                  border: const OutlineInputBorder(),
                  alignLabelWithHint: true,
                ),
              ),
              const SizedBox(height: 16),
              // Style presets — quick fillers. Tap to stamp a vetted
              // style string into the textfield below; user can edit.
              Text(
                l10n.newSongQuickStyles,
                style: Theme.of(context).textTheme.labelLarge,
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final (label, preset) in _kStylePresets)
                    FilterChip(
                      label: Text(_presetLabel(l10n, label)),
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
            ],
            // Style hint / "your touch" — shown in both modes.
            // In theme mode: style hint for Suno. In YouTube mode: optional
            // instruction to give the re-creation its own character.
            TextField(
              controller: _styleCtrl,
              maxLines: 3,
              decoration: InputDecoration(
                labelText: _createMode == 'theme'
                    ? l10n.newSongStyleHintLabel
                    : l10n.newSongYourTouchLabel,
                hintText: _createMode == 'theme'
                    ? l10n.newSongStyleHintHint
                    : l10n.newSongYourTouchHint,
                border: const OutlineInputBorder(),
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
              decoration: InputDecoration(
                labelText: l10n.newSongLanguageLabel,
                border: const OutlineInputBorder(),
              ),
              items: [
                DropdownMenuItem(
                    value: 'ar', child: Text(l10n.newSongLanguageArabic)),
                DropdownMenuItem(
                    value: 'en', child: Text(l10n.newSongLanguageEnglish)),
                DropdownMenuItem(
                    value: 'es', child: Text(l10n.newSongLanguageSpanish)),
                DropdownMenuItem(
                    value: 'fr', child: Text(l10n.newSongLanguageFrench)),
                DropdownMenuItem(
                    value: 'tr', child: Text(l10n.newSongLanguageTurkish)),
              ],
              onChanged: (v) => setState(() => _language = v ?? 'ar'),
            ),
            // Arabic dialect — only meaningful when the song is Arabic.
            // null = Auto (server / LLM decides).
            if (_language == 'ar') ...[
              const SizedBox(height: 16),
              DropdownButtonFormField<String?>(
                initialValue: _dialect,
                decoration: InputDecoration(
                  labelText: l10n.qualityDialectLabel,
                  border: const OutlineInputBorder(),
                ),
                items: <DropdownMenuItem<String?>>[
                  DropdownMenuItem(
                      value: null, child: Text(l10n.qualityDialectAuto)),
                  DropdownMenuItem(
                      value: 'msa', child: Text(l10n.qualityDialectMsa)),
                  DropdownMenuItem(
                      value: 'egyptian',
                      child: Text(l10n.qualityDialectEgyptian)),
                  DropdownMenuItem(
                      value: 'khaleeji',
                      child: Text(l10n.qualityDialectKhaleeji)),
                  DropdownMenuItem(
                      value: 'levantine',
                      child: Text(l10n.qualityDialectLevantine)),
                  DropdownMenuItem(
                      value: 'iraqi', child: Text(l10n.qualityDialectIraqi)),
                ],
                onChanged: (v) => setState(() => _dialect = v),
              ),
            ],
            const SizedBox(height: 16),
            // Vocal gender — defaults to Male to match the reference
            // ai song.mp4 sound. Pinning gender raises probability but
            // doesn't guarantee (per Suno docs).
            DropdownButtonFormField<String>(
              initialValue: _vocalGender,
              decoration: InputDecoration(
                labelText: l10n.newSongVocalLabel,
                border: const OutlineInputBorder(),
              ),
              items: [
                DropdownMenuItem(
                    value: 'm', child: Text(l10n.newSongVocalMale)),
                DropdownMenuItem(
                    value: 'f', child: Text(l10n.newSongVocalFemale)),
                DropdownMenuItem(
                    value: 'auto', child: Text(l10n.newSongVocalAuto)),
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
              decoration: InputDecoration(
                labelText: l10n.newSongSunoModelLabel,
                helperText: l10n.newSongSunoModelHelper,
                border: const OutlineInputBorder(),
              ),
              items: [
                DropdownMenuItem(value: null,
                    child: Text(l10n.newSongSunoModelDefault)),
                DropdownMenuItem(
                    value: 'V5_5', child: Text(l10n.newSongSunoModelLatest)),
                const DropdownMenuItem(value: 'V5', child: Text('V5')),
                const DropdownMenuItem(value: 'V4_5', child: Text('V4_5')),
                DropdownMenuItem(
                    value: 'V4', child: Text(l10n.newSongSunoModelLegacy)),
              ],
              onChanged: (v) => setState(() => _sunoModel = v),
            ),
            const SizedBox(height: 16),
            Text(
              l10n.newSongVideoTypeLabel,
              style: Theme.of(context).textTheme.labelLarge,
            ),
            const SizedBox(height: 8),
            SegmentedButton<String>(
              segments: [
                ButtonSegment(
                  value: 'static',
                  label: Text(l10n.newSongVideoStatic),
                ),
                ButtonSegment(
                  value: 'cinematic',
                  label: Text(l10n.newSongVideoCinematic),
                ),
              ],
              selected: {_videoMode},
              onSelectionChanged: (s) =>
                  setState(() => _videoMode = s.first),
            ),
            // Quality tier — premium runs best-of-N + AI A&R + master. Only
            // the text→song path supports it (cover/upload is standard).
            if (_createMode != 'upload') ...[
              const SizedBox(height: 16),
              Text(
                l10n.newSongQualityLabel,
                style: Theme.of(context).textTheme.labelLarge,
              ),
              const SizedBox(height: 8),
              SegmentedButton<String>(
                segments: [
                  ButtonSegment(
                    value: 'standard',
                    label: Text(l10n.newSongQualityStandard),
                  ),
                  ButtonSegment(
                    value: 'premium',
                    label: Text(l10n.newSongQualityPremium),
                  ),
                ],
                selected: {_qualityTier},
                onSelectionChanged: (s) =>
                    setState(() => _qualityTier = s.first),
              ),
              if (_qualityTier == 'premium') ...[
                const SizedBox(height: 6),
                Text(
                  l10n.newSongQualityPremiumHint,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ],
            const SizedBox(height: 16),
            // Voice picker — only shows once user has saved at least
            // one persona. Default is "Auto" which lets Suno pick.
            if (_personas.isNotEmpty)
              DropdownButtonFormField<String?>(
                initialValue: _personaId,
                decoration: InputDecoration(
                  labelText: l10n.newSongVoiceLabel,
                  helperText: l10n.newSongVoiceHelper,
                  border: const OutlineInputBorder(),
                ),
                items: <DropdownMenuItem<String?>>[
                  DropdownMenuItem(
                    value: null,
                    child: Text(l10n.newSongVoiceAuto),
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
            GradientButton(
              label: _submitting
                  ? l10n.newSongGenerating
                  : l10n.newSongGenerateButton,
              icon: Icons.auto_awesome,
              loading: _submitting,
              expand: true,
              onPressed: _submitting ? null : _submit,
            ),
            const SizedBox(height: 8),
            Text(
              l10n.newSongReviewNotice,
              style: const TextStyle(
                  fontSize: 12, color: FacelessTheme.textSecondary),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}
