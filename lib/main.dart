import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'screens/home_screen.dart';
import 'screens/login_screen.dart';
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
      home: Builder(
        builder: (context) {
          try {
            // Smoke-test that Supabase is initialized. If it throws, the
            // launcher didn't pass --dart-define values — surface a clear
            // misconfiguration banner rather than the old "type a URL here"
            // form. Restart the launcher (`./scripts/run-app.sh`) to fix.
            Supabase.instance.client;
          } catch (_) {
            return const _MisconfiguredScreen();
          }
          return StreamBuilder<AuthState>(
            stream: Supabase.instance.client.auth.onAuthStateChange,
            builder: (context, snap) {
              final session = Supabase.instance.client.auth.currentSession;
              if (session == null) {
                return const LoginScreen();
              }
              // The backend URL is provisioned via --dart-define at build
              // time (see scripts/run-app.sh). End users never need to
              // enter it. If the deployment is misconfigured the home
              // screen will surface a connection error inline rather than
              // forcing the user onto a Settings form.
              return const HomeScreen();
            },
          );
        },
      ),
    );
  }
}

class _MisconfiguredScreen extends StatelessWidget {
  const _MisconfiguredScreen();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text(
            'Backend not configured.\n\n'
            'Restart via scripts/run-app.sh so the Supabase + API URLs are '
            'baked into the build.',
            textAlign: TextAlign.center,
          ),
        ),
      ),
    );
  }
}
