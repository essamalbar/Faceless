import 'package:flutter/material.dart';

import '../api/client.dart';
import '../theme.dart';
import 'song_approve_screen.dart';

class NewSongScreen extends StatefulWidget {
  final FacelessApiClient client;
  const NewSongScreen({super.key, required this.client});

  @override
  State<NewSongScreen> createState() => _NewSongScreenState();
}

class _NewSongScreenState extends State<NewSongScreen> {
  final _themeCtrl = TextEditingController();
  final _lyricsCtrl = TextEditingController();
  final _styleCtrl = TextEditingController();
  String _language = 'ar';
  bool _submitting = false;
  String? _error;

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
            TextField(
              controller: _styleCtrl,
              decoration: const InputDecoration(
                labelText: 'Style hint (optional)',
                hintText: 'Arabic ballad, slow tempo, male vocal',
                border: OutlineInputBorder(),
              ),
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
            const SizedBox(height: 24),
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
