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

  @override
  String get homeCleanupFailedTitle => 'Clean up failed runs?';

  @override
  String get homeCleanupFailedBody =>
      'This permanently deletes every run currently in Failed status. Running and complete runs are not touched.';

  @override
  String get homeDeleteAllFailed => 'Delete all failed';

  @override
  String homeRemovedFailedRuns(int count) {
    return 'Removed $count failed run(s)';
  }

  @override
  String homeCleanupError(String error) {
    return 'Cleanup failed: $error';
  }

  @override
  String get homeDeleteRunTitle => 'Delete this run?';

  @override
  String homeDeleteRunBody(String name) {
    return 'This permanently removes the run dir, including any generated clips and final.mp4. $name';
  }

  @override
  String homeDeletedItem(String name) {
    return 'Deleted $name';
  }

  @override
  String homeDeleteError(String error) {
    return 'Delete failed: $error';
  }

  @override
  String get homeRefresh => 'Refresh';

  @override
  String get homeSavedVoices => 'Saved voices';

  @override
  String get homeSettings => 'Settings';

  @override
  String get homeTabHorror => 'Horror';

  @override
  String get homeTabSong => 'Song';

  @override
  String get homeNoRunsMatchFilter => 'No runs match this filter.';

  @override
  String get homeShowAll => 'Show all';

  @override
  String get homeAllRuns => 'All Runs';

  @override
  String get homeNewSong => 'New Song';

  @override
  String get homeRecent => 'Recent';

  @override
  String homeTracksCount(int count) {
    return '$count tracks';
  }

  @override
  String get homeResults => 'Results';

  @override
  String get homeYourSongs => 'Your songs';

  @override
  String get homeNoSongsMatchSearch => 'No songs match your search';

  @override
  String get homeUntitled => '(untitled)';

  @override
  String get homeSearchHint => 'Search your songs…';

  @override
  String get homeLatestRelease => '◆  LATEST RELEASE';

  @override
  String get homePlay => 'Play';

  @override
  String get homeDetails => 'Details';

  @override
  String homeEpisodesCount(int count) {
    return '$count episodes';
  }

  @override
  String homeEpisodeAbbrev(int number) {
    return 'EP $number';
  }

  @override
  String get homeYourStories => 'Your stories';

  @override
  String get homeNoRenderedVideos => 'No rendered videos yet';

  @override
  String get homeApproveScriptHint =>
      'Approve a script and your video will show up here.';

  @override
  String get homeServerUnreachable => 'Could not reach the server.';

  @override
  String get homeHeroTagline => 'AI-powered Arabic horror shorts';

  @override
  String get homeHeroSubtitle => 'Create your short stories with AI';

  @override
  String get homeStartCreating => 'Start creating';

  @override
  String get homeFreeToWrite => 'Free to write · Subscribe to render';

  @override
  String get homeChooseTheme => 'Choose a theme';

  @override
  String get homeChooseThemeSubtitle =>
      'Tap to start a new story with this style';

  @override
  String get homeHowItWorks => 'How it works';

  @override
  String get homePlans => 'Plans';

  @override
  String homeRunsCount(int count) {
    return '($count runs)';
  }

  @override
  String homeCleanFailed(int count) {
    return 'Clean $count failed';
  }

  @override
  String get homeFilterAll => 'All';

  @override
  String get homeFilterComplete => 'Complete';

  @override
  String get homeFilterAwaiting => 'Awaiting';

  @override
  String get homeFilterRunning => 'Running';

  @override
  String get homeFilterFailed => 'Failed';

  @override
  String get homeStatusWritingLyrics => 'Writing lyrics';

  @override
  String get homeStatusReviewApprove => 'Review & approve';

  @override
  String get homeStatusComposing => 'Composing music';

  @override
  String get homeStatusDesigningCover => 'Designing cover';

  @override
  String get homeStatusSyncingBeat => 'Syncing to the beat';

  @override
  String get homeStatusSyncingLyrics => 'Syncing lyrics';

  @override
  String get homeStatusRendering => 'Rendering video';

  @override
  String get homeStatusReady => 'Ready';

  @override
  String get homeStatusPending => 'Pending';

  @override
  String get homeYourPlan => 'Your plan';

  @override
  String get homeRecommended => 'Recommended';

  @override
  String homeCreditsCount(int count) {
    return '$count credits';
  }

  @override
  String get homeSeeFullPlans => 'See full plans';

  @override
  String get homePlanStarter => 'Starter';

  @override
  String get homePlanCreator => 'Creator';

  @override
  String get homePlanPro => 'Pro';

  @override
  String get homeStep1Title => 'Write a premise';

  @override
  String get homeStep1Subtitle => 'One sentence is enough';

  @override
  String get homeStep2Title => 'AI writes your script';

  @override
  String get homeStep2Subtitle => 'Arabic, in seconds — free for everyone';

  @override
  String get homeStep3Title => 'Subscribe to render the video';

  @override
  String get homeStep3Subtitle => 'Each clip uses 1 credit';

  @override
  String get homeMakeFirstSong => 'Make your first AI song';

  @override
  String get homePickSampleHint =>
      'Pick a sample to start with, or tap \"New song\" to write your own.';

  @override
  String get homeNewSongFromScratch => 'New song from scratch';

  @override
  String get homeThemeFolkloric => 'Folkloric';

  @override
  String get homeThemeFolkloricDesc => 'Ancestral tales, jinn, old wells';

  @override
  String get homeThemeUrban => 'Urban';

  @override
  String get homeThemeUrbanDesc => 'City legends, late-night streets';

  @override
  String get homeThemeWilderness => 'Wilderness';

  @override
  String get homeThemeWildernessDesc => 'Forests, deserts, the unknown';

  @override
  String get homeThemeMemory => 'Memory';

  @override
  String get homeThemeMemoryDesc => 'Psychological, half-remembered';

  @override
  String get homeThemeDomestic => 'Domestic';

  @override
  String get homeThemeDomesticDesc => 'Home, family, the everyday turned';

  @override
  String get homeThemeTravel => 'Travel';

  @override
  String get homeThemeTravelDesc => 'On the road, far from home';

  @override
  String get homeThemeTech => 'Tech';

  @override
  String get homeThemeTechDesc => 'Screens, signals, machines';

  @override
  String get homeThemeWorkplace => 'Workplace';

  @override
  String get homeThemeWorkplaceDesc => 'Offices, shops, after-hours';
}
