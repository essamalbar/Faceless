import 'package:flutter/material.dart';

import '../api/client.dart';

/// Stub — replaced by Task 17's full implementation.
class SongDetailScreen extends StatelessWidget {
  final FacelessApiClient client;
  final String runId;
  const SongDetailScreen(
      {super.key, required this.client, required this.runId});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Song')),
      body: const Center(
          child: Text('Detail screen — implemented in Task 17')),
    );
  }
}
