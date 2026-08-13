import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../l10n/l10n.dart';
import '../theme.dart';
import '../ui/brand.dart';
import '../ui/song_genres.dart';
import '../widgets/genre_grid.dart';
import 'legal_screen.dart';
import 'song_approve_screen.dart';

class NewSongScreen extends StatefulWidget {
  final FacelessApiClient client;
  // Optional pre-fills for "try this sample" entry points from the
  // empty state. When set, the form opens with these values populated
  // so the user is one tap away from generating.
  final String? initialTheme;
  final String? initialGenreKey;
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
    this.initialGenreKey,
    this.initialStyleHint,
    this.initialLanguage,
    this.initialArtist,
  });

  @override
  State<NewSongScreen> createState() => _NewSongScreenState();
}

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
  String? _genreKey;           // null = Auto (server/LLM infers genre)
  bool _showLyrics = false;    // reveal the custom-lyrics field on demand
  List<Persona> _personas = [];
  Artist? _artist;             // selected artist (null = none)
  List<Artist> _artists = [];
  bool _artistsLoading = true;
  bool _submitting = false;
  // Tier-3 legal gate: user must attest they own/have rights to the material
  // before Create/Upload is enabled.
  bool _ownershipAttested = false;
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
    if (widget.initialGenreKey != null &&
        isGenreValidForLanguage(widget.initialGenreKey, _language)) {
      _genreKey = widget.initialGenreKey;
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
    // Legal gate — enforce here, not only via the disabled button.
    if (!_ownershipAttested) {
      setState(() => _error =
          'Please confirm you own or have the rights to this material.');
      return;
    }
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
          ownershipAttested: _ownershipAttested,
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
          genre: _genreKey,
          ownershipAttested: _ownershipAttested,
        );
      }
      if (!mounted) return;
      Navigator.of(context).pushReplacement(MaterialPageRoute(
        builder: (_) =>
            SongApproveScreen(client: widget.client, runId: runId),
      ));
    } on TermsNotAcceptedException {
      // Soft gate: route the user to the accept-capable Terms screen instead
      // of dead-ending on the exception text. Re-enable the button first so
      // it's usable when they return.
      if (!mounted) return;
      setState(() => _submitting = false);
      final accepted = await Navigator.of(context).push<bool>(
        MaterialPageRoute(
          builder: (_) =>
              LegalScreen(client: widget.client, mustAccept: true),
        ),
      );
      if (!mounted) return;
      if (accepted == true) {
        // Don't silently auto-resubmit — nudge the user to tap Generate again.
        setState(() => _error = null);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Terms accepted — tap Generate again.'),
          ),
        );
      }
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
            // Language — shared by both modes (upload/cover sends it too),
            // so it lives above the mode-specific content. In the theme
            // flow this also puts it above the genre grid; switching away
            // from Arabic invalidates an Arabic-only genre selection.
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
              onChanged: (v) => setState(() {
                _language = v ?? 'ar';
                if (!isGenreValidForLanguage(_genreKey, _language)) {
                  _genreKey = null;
                }
              }),
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
              // "Your touch" — optional instruction to give the re-creation
              // its own character. Bound to the same controller as the
              // theme flow's style-hint field below (only one ever mounts).
              TextField(
                controller: _styleCtrl,
                maxLines: 3,
                decoration: InputDecoration(
                  labelText: l10n.newSongYourTouchLabel,
                  hintText: l10n.newSongYourTouchHint,
                  border: const OutlineInputBorder(),
                  alignLabelWithHint: true,
                ),
              ),
              const SizedBox(height: 16),
            ] else ...[
              // Theme path: describe the song, then genre + power-user
              // controls. Custom lyrics stay behind a disclosure — most
              // users let the lyrics LLM write from the theme above.
              TextField(
                controller: _themeCtrl,
                decoration: InputDecoration(
                  labelText: l10n.newSongThemeLabel,
                  hintText: l10n.newSongThemeHint,
                  border: const OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 12),
              InkWell(
                onTap: () => setState(() => _showLyrics = !_showLyrics),
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        _showLyrics ? Icons.expand_less : Icons.expand_more,
                        size: 18,
                        color: FacelessTheme.accent,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        l10n.addMyLyrics,
                        style: const TextStyle(
                          color: FacelessTheme.accent,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              if (_showLyrics) ...[
                const SizedBox(height: 8),
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
              ],
              const SizedBox(height: 16),
              // Genre grid — Auto (null) lets the lyrics/style LLM infer.
              Text(l10n.genrePickerLabel,
                  style: Theme.of(context).textTheme.labelLarge),
              const SizedBox(height: 8),
              GenreGrid(
                selectedKey: _genreKey,
                language: _language,
                onChanged: (k) => setState(() => _genreKey = k),
              ),
              const SizedBox(height: 16),
              // Advanced options — dialect, style hint, quality tier, Suno
              // model, persona. Collapsed by default.
              ExpansionTile(
                title: Text(l10n.advancedOptions),
                initiallyExpanded: false,
                children: [
                  // Arabic dialect — only meaningful when the song is
                  // Arabic. null = Auto (server / LLM decides).
                  if (_language == 'ar') ...[
                    DropdownButtonFormField<String?>(
                      initialValue: _dialect,
                      decoration: InputDecoration(
                        labelText: l10n.qualityDialectLabel,
                        border: const OutlineInputBorder(),
                      ),
                      items: <DropdownMenuItem<String?>>[
                        DropdownMenuItem(
                            value: null,
                            child: Text(l10n.qualityDialectAuto)),
                        DropdownMenuItem(
                            value: 'msa',
                            child: Text(l10n.qualityDialectMsa)),
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
                            value: 'iraqi',
                            child: Text(l10n.qualityDialectIraqi)),
                      ],
                      onChanged: (v) => setState(() => _dialect = v),
                    ),
                    const SizedBox(height: 16),
                  ],
                  // Style hint for Suno — user can edit freely.
                  TextField(
                    controller: _styleCtrl,
                    maxLines: 3,
                    decoration: InputDecoration(
                      labelText: l10n.newSongStyleHintLabel,
                      hintText: l10n.newSongStyleHintHint,
                      border: const OutlineInputBorder(),
                      alignLabelWithHint: true,
                    ),
                  ),
                  const SizedBox(height: 16),
                  // Quality tier — premium runs best-of-N + AI A&R + master.
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
                          value: 'V5_5',
                          child: Text(l10n.newSongSunoModelLatest)),
                      const DropdownMenuItem(value: 'V5', child: Text('V5')),
                      const DropdownMenuItem(
                          value: 'V4_5', child: Text('V4_5')),
                      DropdownMenuItem(
                          value: 'V4',
                          child: Text(l10n.newSongSunoModelLegacy)),
                    ],
                    onChanged: (v) => setState(() => _sunoModel = v),
                  ),
                  // Voice picker — only shows once user has saved at
                  // least one persona. Default is "Auto" which lets
                  // Suno pick.
                  if (_personas.isNotEmpty) ...[
                    const SizedBox(height: 16),
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
                          DropdownMenuItem(
                              value: p.id, child: Text(p.name)),
                      ],
                      onChanged: (v) => setState(() => _personaId = v),
                    ),
                  ],
                  const SizedBox(height: 8),
                ],
              ),
            ],
            const SizedBox(height: 16),
            // Vocal gender — defaults to Male to match the reference
            // ai song.mp4 sound. Pinning gender raises probability but
            // doesn't guarantee (per Suno docs). Shared by both modes.
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
            // Video type — shared by both modes.
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
            const SizedBox(height: 16),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Text(
                  _error!,
                  style: TextStyle(
                      color: Theme.of(context).colorScheme.error),
                ),
              ),
            // Ownership attestation — required before Create/Upload. Gates
            // the generate button below and is enforced again in _submit().
            Container(
              margin: const EdgeInsets.only(bottom: 12),
              padding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              decoration: BoxDecoration(
                color: FacelessTheme.surface2,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: FacelessTheme.border),
              ),
              child: Row(
                children: [
                  Checkbox(
                    value: _ownershipAttested,
                    onChanged: _submitting
                        ? null
                        : (v) => setState(
                            () => _ownershipAttested = v ?? false),
                  ),
                  const Expanded(
                    child: Text(
                      'I own or have the rights to this material.',
                      style: TextStyle(
                        fontSize: 13,
                        color: FacelessTheme.textPrimary,
                        height: 1.35,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            GradientButton(
              label: _submitting
                  ? l10n.newSongGenerating
                  : l10n.newSongGenerateButton,
              icon: Icons.auto_awesome,
              loading: _submitting,
              expand: true,
              onPressed: (_submitting || !_ownershipAttested)
                  ? null
                  : _submit,
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
