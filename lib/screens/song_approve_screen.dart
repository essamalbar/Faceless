import 'package:flutter/material.dart';

import '../api/client.dart';

/// Stub — replaced by Task 16's full implementation.
class SongApproveScreen extends StatelessWidget {
  final FacelessApiClient client;
  final String runId;
  const SongApproveScreen(
      {super.key, required this.client, required this.runId});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Review draft')),
      body: const Center(
          child: Text('Approve screen — implemented in Task 16')),
    );
  }
}
