/// Create / edit a virtual artist (Artist Core).
///
/// Create mode when [artist] is null. Pops with the saved [Artist] on
/// success, or the string `'deleted'` after a confirmed delete, so callers
/// can distinguish "updated" from "gone".
library;

import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../l10n/l10n.dart';
import '../theme.dart';
import '../ui/brand.dart';
import '../widgets/artist_avatar.dart';

class ArtistEditScreen extends StatefulWidget {
  final FacelessApiClient client;
  final Artist? artist; // null = create mode
  const ArtistEditScreen({super.key, required this.client, this.artist});

  @override
  State<ArtistEditScreen> createState() => _ArtistEditScreenState();
}

class _ArtistEditScreenState extends State<ArtistEditScreen> {
  late final TextEditingController _nameCtrl;
  late final TextEditingController _handleCtrl;
  late final TextEditingController _bioCtrl;
  late final TextEditingController _styleCtrl;
  late String _language;
  late String _vocalGender;
  late bool _autoPublishYoutube;
  late bool _morningDrafts;
  Uint8List? _avatarBytes; // picked but not yet uploaded (uploads on save)
  String? _avatarName;
  bool _saving = false;
  String? _error; // general form error
  String? _handleError; // inline 409 duplicate-handle message

  bool get _isEdit => widget.artist != null;

  @override
  void initState() {
    super.initState();
    final a = widget.artist;
    _nameCtrl = TextEditingController(text: a?.name ?? '');
    _handleCtrl = TextEditingController(text: a?.handle ?? '');
    _bioCtrl = TextEditingController(text: a?.bio ?? '');
    _styleCtrl = TextEditingController(text: a?.defaultStyle ?? '');
    _language = (a?.defaultLanguage == 'en') ? 'en' : 'ar';
    _vocalGender = (a?.defaultVocalGender == 'f') ? 'f' : 'm';
    _autoPublishYoutube = a?.autoPublishYoutube ?? false; // create: OFF
    _morningDrafts = a?.morningDrafts ?? false; // create: OFF
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _handleCtrl.dispose();
    _bioCtrl.dispose();
    _styleCtrl.dispose();
    super.dispose();
  }

  Future<void> _pickAvatar() async {
    final l10n = context.l10n;
    try {
      final res = await FilePicker.platform
          .pickFiles(type: FileType.image, withData: true);
      if (res == null || res.files.isEmpty) return; // user cancelled
      final f = res.files.first;
      if (f.bytes == null) {
        setState(() => _error = l10n.newSongFileReadError);
        return;
      }
      setState(() {
        _avatarBytes = f.bytes;
        _avatarName = f.name;
        _error = null;
      });
    } catch (e) {
      setState(() => _error = l10n.newSongFilePickerError('$e'));
    }
  }

  Future<void> _save() async {
    final l10n = context.l10n;
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) {
      setState(() => _error = l10n.artistNameRequired);
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
      _handleError = null;
    });
    final handle = _handleCtrl.text.trim();
    final messenger = ScaffoldMessenger.of(context);
    Artist artist;
    try {
      if (_isEdit) {
        artist = await widget.client.patchArtist(widget.artist!.id, {
          'name': name,
          if (handle.isNotEmpty && handle != widget.artist!.handle)
            'handle': handle,
          'bio': _bioCtrl.text.trim(),
          'default_style': _styleCtrl.text.trim(),
          'default_language': _language,
          'default_vocal_gender': _vocalGender,
          'auto_publish_youtube': _autoPublishYoutube,
          'morning_drafts': _morningDrafts,
        });
      } else {
        artist = await widget.client.createArtist(
          name: name,
          handle: handle.isEmpty ? null : handle,
          bio: _bioCtrl.text.trim(),
          defaultStyle: _styleCtrl.text.trim(),
          defaultLanguage: _language,
          defaultVocalGender: _vocalGender,
        );
        // POST /artists doesn't accept the YouTube toggle — patch it on
        // right after create, but only when the user actually turned it
        // on (default is OFF). A failed patch shouldn't lose the artist.
        if (_autoPublishYoutube || _morningDrafts) {
          try {
            artist = await widget.client.patchArtist(artist.id, {
              if (_autoPublishYoutube) 'auto_publish_youtube': true,
              if (_morningDrafts) 'morning_drafts': true,
            });
          } catch (e) {
            messenger.showSnackBar(
                SnackBar(content: Text(l10n.ytAutoPublishSaveFailed('$e'))));
          }
        }
      }
    } on FacelessApiException catch (e) {
      // 409 duplicate handle — the server message includes the suggestion;
      // surface it inline under the handle field.
      setState(() {
        _saving = false;
        if (e.status == 409) {
          _handleError = e.message;
        } else {
          _error = e.message;
        }
      });
      return;
    } catch (e) {
      setState(() {
        _saving = false;
        _error = '$e';
      });
      return;
    }
    // Avatar uploads after the entity exists. A failed upload shouldn't
    // lose the saved artist — report it and pop with the artist anyway.
    if (_avatarBytes != null) {
      try {
        artist = await widget.client.uploadArtistAvatar(
          artistId: artist.id,
          bytes: _avatarBytes!,
          filename: _avatarName ?? 'avatar.png',
        );
      } catch (e) {
        messenger.showSnackBar(
            SnackBar(content: Text(l10n.artistAvatarUploadFailed('$e'))));
      }
    }
    if (mounted) Navigator.of(context).pop(artist);
  }

  Future<void> _delete() async {
    final artist = widget.artist!;
    final yes = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(ctx.l10n.artistDeleteConfirmTitle),
        content: Text(ctx.l10n.artistDeleteConfirmBody),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: Text(ctx.l10n.commonCancel)),
          FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: Text(ctx.l10n.commonDelete)),
        ],
      ),
    );
    if (yes != true || !mounted) return;
    setState(() => _saving = true);
    try {
      await widget.client.deleteArtist(artist.id);
      if (mounted) Navigator.of(context).pop('deleted');
    } catch (e) {
      if (mounted) {
        setState(() {
          _saving = false;
          _error = context.l10n.artistDeleteFailed('$e');
        });
      }
    }
  }

  Widget _avatarPreview() {
    if (_avatarBytes != null) {
      return Container(
        width: 72,
        height: 72,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          border: Border.all(color: FacelessTheme.border),
        ),
        child: ClipOval(
          child: Image.memory(_avatarBytes!, fit: BoxFit.cover),
        ),
      );
    }
    if (_isEdit) {
      return ArtistAvatar(artist: widget.artist!, client: widget.client, size: 72);
    }
    // Create mode, nothing picked yet — soft gradient placeholder.
    return Container(
      width: 72,
      height: 72,
      decoration: BoxDecoration(
        gradient: coverGradient(
            _nameCtrl.text.isEmpty ? 'artist' : _nameCtrl.text),
        shape: BoxShape.circle,
        border: Border.all(color: FacelessTheme.border),
      ),
      child: const Icon(Icons.person_outline, color: Colors.white, size: 32),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Scaffold(
      appBar: AppBar(
        title:
            Text(_isEdit ? l10n.artistEditTitleEdit : l10n.artistEditTitleCreate),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                _avatarPreview(),
                const SizedBox(width: 16),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _saving ? null : _pickAvatar,
                    icon: const Icon(Icons.image_outlined),
                    label: Text(l10n.artistChooseAvatar),
                  ),
                ),
              ],
            ),
            if (_avatarBytes != null)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(
                  l10n.artistAvatarSelected,
                  style: const TextStyle(
                      fontSize: 12, color: FacelessTheme.textSecondary),
                ),
              ),
            const SizedBox(height: 20),
            TextField(
              controller: _nameCtrl,
              decoration: InputDecoration(labelText: l10n.artistNameLabel),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _handleCtrl,
              decoration: InputDecoration(
                labelText: l10n.artistHandleLabel,
                helperText: l10n.artistHandleHelper,
                errorText: _handleError,
                prefixText: '@',
              ),
              onChanged: (_) {
                if (_handleError != null) setState(() => _handleError = null);
              },
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _bioCtrl,
              maxLines: 3,
              decoration: InputDecoration(
                labelText: l10n.artistBioLabel,
                alignLabelWithHint: true,
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _styleCtrl,
              maxLines: 2,
              decoration: InputDecoration(
                labelText: l10n.artistDefaultStyleLabel,
                alignLabelWithHint: true,
              ),
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              initialValue: _language,
              decoration:
                  InputDecoration(labelText: l10n.newSongLanguageLabel),
              items: [
                DropdownMenuItem(
                    value: 'ar', child: Text(l10n.newSongLanguageArabic)),
                DropdownMenuItem(
                    value: 'en', child: Text(l10n.newSongLanguageEnglish)),
              ],
              onChanged: (v) => setState(() => _language = v ?? 'ar'),
            ),
            const SizedBox(height: 16),
            Text(l10n.artistVocalLabel,
                style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: 8),
            SegmentedButton<String>(
              segments: [
                ButtonSegment(value: 'm', label: Text(l10n.newSongVocalMale)),
                ButtonSegment(value: 'f', label: Text(l10n.newSongVocalFemale)),
              ],
              selected: {_vocalGender},
              onSelectionChanged: (s) =>
                  setState(() => _vocalGender = s.first),
            ),
            const SizedBox(height: 12),
            // YouTube: completed songs by this artist upload to the
            // connected channel automatically (needs YouTube connected
            // in Settings).
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(l10n.ytAutoPublishLabel),
              subtitle: Text(
                l10n.ytAutoPublishSubtitle,
                style: const TextStyle(
                    fontSize: 12, color: FacelessTheme.textSecondary),
              ),
              value: _autoPublishYoutube,
              onChanged: _saving
                  ? null
                  : (v) => setState(() => _autoPublishYoutube = v),
            ),
            // Morning drafts: a FREE draft each morning from the day's
            // trends — the approve gate (and billing) is untouched.
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(l10n.draftMorningLabel),
              subtitle: Text(
                l10n.draftMorningSubtitle,
                style: const TextStyle(
                    fontSize: 12, color: FacelessTheme.textSecondary),
              ),
              value: _morningDrafts,
              onChanged: _saving
                  ? null
                  : (v) => setState(() => _morningDrafts = v),
            ),
            const SizedBox(height: 20),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Text(
                  _error!,
                  style:
                      TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            GradientButton(
              label: _isEdit ? l10n.artistSaveButton : l10n.artistCreateButton,
              icon: Icons.check,
              loading: _saving,
              expand: true,
              onPressed: _saving ? null : _save,
            ),
            if (_isEdit) ...[
              const SizedBox(height: 12),
              TextButton.icon(
                onPressed: _saving ? null : _delete,
                icon:
                    const Icon(Icons.delete_outline, color: FacelessTheme.danger),
                label: Text(
                  l10n.artistDeleteButton,
                  style: const TextStyle(color: FacelessTheme.danger),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
