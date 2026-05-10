import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'api/settings.dart';
import 'screens/home_screen.dart';
import 'screens/settings_screen.dart';
import 'theme.dart';

const _supabaseUrl = String.fromEnvironment('SUPABASE_URL');
const _supabaseAnonKey = String.fromEnvironment('SUPABASE_ANON_KEY');

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  if (_supabaseUrl.isNotEmpty && _supabaseAnonKey.isNotEmpty) {
    await Supabase.initialize(
      url: _supabaseUrl,
      anonKey: _supabaseAnonKey,
    );
  }
  runApp(const FacelessApp());
}

class FacelessApp extends StatelessWidget {
  const FacelessApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Faceless',
      debugShowCheckedModeBanner: false,
      theme: FacelessTheme.build(),
      home: const _Bootstrap(),
    );
  }
}

/// On first launch, check whether settings are configured. If not, force the
/// user through the settings screen before showing the home gallery.
class _Bootstrap extends StatefulWidget {
  const _Bootstrap();

  @override
  State<_Bootstrap> createState() => _BootstrapState();
}

class _BootstrapState extends State<_Bootstrap> {
  late Future<bool> _configured;

  @override
  void initState() {
    super.initState();
    _configured = FacelessSettings().isConfigured();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<bool>(
      future: _configured,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }
        if (snap.data == true) {
          return const HomeScreen();
        }
        return const SettingsScreen(firstLaunch: true);
      },
    );
  }
}
