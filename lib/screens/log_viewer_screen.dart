import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../api/client.dart';
import '../l10n/l10n.dart';
import '../theme.dart';

/// Tail of the run's subprocess log. Critical for diagnosing safety-filter
/// rejections, TLS resets, Veo errors without leaving the app.
class LogViewerScreen extends StatefulWidget {
  final FacelessApiClient client;
  final String runId;
  const LogViewerScreen({
    super.key,
    required this.client,
    required this.runId,
  });

  @override
  State<LogViewerScreen> createState() => _LogViewerScreenState();
}

class _LogViewerScreenState extends State<LogViewerScreen> {
  String _log = '';
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final text = await widget.client.getLog(widget.runId, lines: 500);
      if (!mounted) return;
      setState(() => _log = text);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _copy() async {
    await Clipboard.setData(ClipboardData(text: _log));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(context.l10n.logViewerCopied)),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(context.l10n.logViewerTitle(widget.runId),
            style: const TextStyle(fontSize: 14)),
        actions: [
          IconButton(
              icon: const Icon(Icons.copy),
              tooltip: context.l10n.logViewerCopyTooltip,
              onPressed: _log.isEmpty ? null : _copy),
          IconButton(
              icon: const Icon(Icons.refresh),
              tooltip: context.l10n.homeRefresh,
              onPressed: _refresh),
        ],
      ),
      body: _error != null
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Text(_error!,
                    style: TextStyle(
                        color: Theme.of(context).colorScheme.error)),
              ),
            )
          : _loading && _log.isEmpty
              ? const Center(child: CircularProgressIndicator())
              : Container(
                  color: Colors.black,
                  width: double.infinity,
                  child: SingleChildScrollView(
                    reverse: true, // show tail by default
                    padding: const EdgeInsets.all(12),
                    child: SelectableText(
                      _log.isEmpty ? context.l10n.logViewerEmpty : _log,
                      style: const TextStyle(
                        color: FacelessTheme.textPrimary,
                        fontFamily: 'monospace',
                        fontSize: 11,
                        height: 1.4,
                      ),
                    ),
                  ),
                ),
    );
  }
}
