import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../theme.dart';

class PersonasScreen extends StatefulWidget {
  final FacelessApiClient client;
  const PersonasScreen({super.key, required this.client});

  @override
  State<PersonasScreen> createState() => _PersonasScreenState();
}

class _PersonasScreenState extends State<PersonasScreen> {
  late Future<List<Persona>> _future;

  @override
  void initState() {
    super.initState();
    _future = widget.client.listPersonas();
  }

  Future<void> _refresh() async {
    setState(() {
      _future = widget.client.listPersonas();
    });
    await _future;
  }

  Future<void> _confirmDelete(Persona p) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Delete "${p.name}"?'),
        content: const Text(
          'This removes the saved voice. Songs you already generated '
          'with it keep their audio — only future generations lose '
          'the lock to this voice.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(ctx).colorScheme.error,
            ),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    try {
      await widget.client.deletePersona(p.id);
      if (mounted) {
        messenger.showSnackBar(SnackBar(content: Text('"${p.name}" removed')));
        _refresh();
      }
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(SnackBar(content: Text('Delete failed: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Saved voices')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<List<Persona>>(
          future: _future,
          builder: (ctx, snap) {
            if (snap.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snap.hasError) {
              return Center(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Text(
                    'Failed to load voices: ${snap.error}',
                    style: TextStyle(
                        color: Theme.of(context).colorScheme.error),
                    textAlign: TextAlign.center,
                  ),
                ),
              );
            }
            final personas = snap.data ?? [];
            if (personas.isEmpty) {
              return ListView(
                children: const [
                  SizedBox(height: 80),
                  Icon(Icons.record_voice_over,
                      size: 64, color: FacelessTheme.textSecondary),
                  SizedBox(height: 16),
                  Padding(
                    padding: EdgeInsets.symmetric(horizontal: 32),
                    child: Text(
                      'No saved voices yet.\n\n'
                      'Generate a song, then tap "Save this voice" on its '
                      'detail screen to pin the singer for future songs.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: FacelessTheme.textSecondary),
                    ),
                  ),
                ],
              );
            }
            return ListView.separated(
              padding: const EdgeInsets.symmetric(vertical: 8),
              itemCount: personas.length,
              separatorBuilder: (_, _) => const Divider(height: 1),
              itemBuilder: (ctx, i) {
                final p = personas[i];
                return ListTile(
                  leading: const Icon(Icons.record_voice_over),
                  title: Text(p.name),
                  subtitle: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(p.description,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis),
                      const SizedBox(height: 2),
                      Text('From song ${p.sourceRunId} · take ${p.sourceTake}',
                          style: const TextStyle(
                              fontSize: 11,
                              color: FacelessTheme.textSecondary)),
                    ],
                  ),
                  trailing: IconButton(
                    icon: const Icon(Icons.delete_outline),
                    tooltip: 'Delete this voice',
                    onPressed: () => _confirmDelete(p),
                  ),
                  isThreeLine: true,
                );
              },
            );
          },
        ),
      ),
    );
  }
}
