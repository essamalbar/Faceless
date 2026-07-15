import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../l10n/l10n.dart';
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
    final l10n = context.l10n;
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(l10n.personasDeleteTitle(p.name)),
        content: Text(l10n.personasDeleteBody),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false),
              child: Text(l10n.commonCancel)),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(ctx).colorScheme.error,
            ),
            onPressed: () => Navigator.pop(ctx, true),
            child: Text(l10n.commonDelete),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    try {
      await widget.client.deletePersona(p.id);
      if (mounted) {
        messenger.showSnackBar(
            SnackBar(content: Text(l10n.personasRemoved(p.name))));
        _refresh();
      }
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(
            SnackBar(content: Text(l10n.homeDeleteError('$e'))));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.homeSavedVoices)),
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
                    l10n.personasLoadFailed('${snap.error}'),
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
                children: [
                  const SizedBox(height: 80),
                  const Icon(Icons.record_voice_over,
                      size: 64, color: FacelessTheme.textSecondary),
                  const SizedBox(height: 16),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 32),
                    child: Text(
                      l10n.personasEmpty,
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                          color: FacelessTheme.textSecondary),
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
                      Text(
                          l10n.personasFromSong(
                              p.sourceRunId, p.sourceTake),
                          style: const TextStyle(
                              fontSize: 11,
                              color: FacelessTheme.textSecondary)),
                    ],
                  ),
                  trailing: IconButton(
                    icon: const Icon(Icons.delete_outline),
                    tooltip: l10n.personasDeleteTooltip,
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
