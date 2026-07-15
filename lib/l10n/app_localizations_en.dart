// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appTitle => 'Faceless Lab';

  @override
  String get commonCancel => 'Cancel';

  @override
  String get commonSave => 'Save';

  @override
  String get commonRetry => 'Retry';

  @override
  String get commonClose => 'Close';

  @override
  String get commonDelete => 'Delete';

  @override
  String get commonSignIn => 'Sign in';

  @override
  String get commonGetStarted => 'Get started';

  @override
  String get settingsLanguage => 'Language';

  @override
  String get settingsLanguageAuto => 'Auto (device)';

  @override
  String get statusAnalyzing => 'Analyzing';

  @override
  String get statusAwaitingApproval => 'Awaiting approval';

  @override
  String get statusGeneratingSong => 'Generating song';

  @override
  String get statusGeneratingCover => 'Generating cover';

  @override
  String get statusAssembling => 'Assembling';

  @override
  String get statusComplete => 'Complete';

  @override
  String get statusFailed => 'Failed';

  @override
  String get statusRunning => 'Running';

  @override
  String get statusCancelled => 'Cancelled';
}
