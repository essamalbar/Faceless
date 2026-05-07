/// Compile-time defaults injected via `--dart-define`.
///
/// The launcher script (`scripts/run-app.sh`) reads `.env` and passes:
///   --dart-define=FACELESS_API_URL=<tunnel or LAN URL>
///   --dart-define=FACELESS_API_TOKEN=<bearer token>
///
/// When these are non-empty the bootstrap skips the Settings screen on first
/// launch and connects automatically. The user can still override via the
/// gear icon → Settings if they want a different server (e.g. testing).
library;

class FacelessConfig {
  static const apiUrl = String.fromEnvironment('FACELESS_API_URL');
  static const apiToken = String.fromEnvironment('FACELESS_API_TOKEN');

  static bool get hasBakedDefaults =>
      apiUrl.isNotEmpty && apiToken.isNotEmpty;
}
