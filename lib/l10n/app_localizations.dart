import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_ar.dart';
import 'app_localizations_en.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations? of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations);
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('ar'),
    Locale('en'),
  ];

  /// No description provided for @appTitle.
  ///
  /// In en, this message translates to:
  /// **'Faceless Lab'**
  String get appTitle;

  /// No description provided for @commonCancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get commonCancel;

  /// No description provided for @commonSave.
  ///
  /// In en, this message translates to:
  /// **'Save'**
  String get commonSave;

  /// No description provided for @commonRetry.
  ///
  /// In en, this message translates to:
  /// **'Retry'**
  String get commonRetry;

  /// No description provided for @commonClose.
  ///
  /// In en, this message translates to:
  /// **'Close'**
  String get commonClose;

  /// No description provided for @commonDelete.
  ///
  /// In en, this message translates to:
  /// **'Delete'**
  String get commonDelete;

  /// No description provided for @commonSignIn.
  ///
  /// In en, this message translates to:
  /// **'Sign in'**
  String get commonSignIn;

  /// No description provided for @commonGetStarted.
  ///
  /// In en, this message translates to:
  /// **'Get started'**
  String get commonGetStarted;

  /// No description provided for @settingsLanguage.
  ///
  /// In en, this message translates to:
  /// **'Language'**
  String get settingsLanguage;

  /// No description provided for @settingsLanguageAuto.
  ///
  /// In en, this message translates to:
  /// **'Auto (device)'**
  String get settingsLanguageAuto;

  /// No description provided for @statusAnalyzing.
  ///
  /// In en, this message translates to:
  /// **'Analyzing'**
  String get statusAnalyzing;

  /// No description provided for @statusAwaitingApproval.
  ///
  /// In en, this message translates to:
  /// **'Awaiting approval'**
  String get statusAwaitingApproval;

  /// No description provided for @statusGeneratingSong.
  ///
  /// In en, this message translates to:
  /// **'Generating song'**
  String get statusGeneratingSong;

  /// No description provided for @statusGeneratingCover.
  ///
  /// In en, this message translates to:
  /// **'Generating cover'**
  String get statusGeneratingCover;

  /// No description provided for @statusAssembling.
  ///
  /// In en, this message translates to:
  /// **'Assembling'**
  String get statusAssembling;

  /// No description provided for @statusComplete.
  ///
  /// In en, this message translates to:
  /// **'Complete'**
  String get statusComplete;

  /// No description provided for @statusFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed'**
  String get statusFailed;

  /// No description provided for @statusRunning.
  ///
  /// In en, this message translates to:
  /// **'Running'**
  String get statusRunning;

  /// No description provided for @statusCancelled.
  ///
  /// In en, this message translates to:
  /// **'Cancelled'**
  String get statusCancelled;

  /// No description provided for @homeCleanupFailedTitle.
  ///
  /// In en, this message translates to:
  /// **'Clean up failed runs?'**
  String get homeCleanupFailedTitle;

  /// No description provided for @homeCleanupFailedBody.
  ///
  /// In en, this message translates to:
  /// **'This permanently deletes every run currently in Failed status. Running and complete runs are not touched.'**
  String get homeCleanupFailedBody;

  /// No description provided for @homeDeleteAllFailed.
  ///
  /// In en, this message translates to:
  /// **'Delete all failed'**
  String get homeDeleteAllFailed;

  /// No description provided for @homeRemovedFailedRuns.
  ///
  /// In en, this message translates to:
  /// **'Removed {count} failed run(s)'**
  String homeRemovedFailedRuns(int count);

  /// No description provided for @homeCleanupError.
  ///
  /// In en, this message translates to:
  /// **'Cleanup failed: {error}'**
  String homeCleanupError(String error);

  /// No description provided for @homeDeleteRunTitle.
  ///
  /// In en, this message translates to:
  /// **'Delete this run?'**
  String get homeDeleteRunTitle;

  /// No description provided for @homeDeleteRunBody.
  ///
  /// In en, this message translates to:
  /// **'This permanently removes the run dir, including any generated clips and final.mp4. {name}'**
  String homeDeleteRunBody(String name);

  /// No description provided for @homeDeletedItem.
  ///
  /// In en, this message translates to:
  /// **'Deleted {name}'**
  String homeDeletedItem(String name);

  /// No description provided for @homeDeleteError.
  ///
  /// In en, this message translates to:
  /// **'Delete failed: {error}'**
  String homeDeleteError(String error);

  /// No description provided for @homeRefresh.
  ///
  /// In en, this message translates to:
  /// **'Refresh'**
  String get homeRefresh;

  /// No description provided for @homeSavedVoices.
  ///
  /// In en, this message translates to:
  /// **'Saved voices'**
  String get homeSavedVoices;

  /// No description provided for @homeSettings.
  ///
  /// In en, this message translates to:
  /// **'Settings'**
  String get homeSettings;

  /// No description provided for @homeTabHorror.
  ///
  /// In en, this message translates to:
  /// **'Horror'**
  String get homeTabHorror;

  /// No description provided for @homeTabSong.
  ///
  /// In en, this message translates to:
  /// **'Song'**
  String get homeTabSong;

  /// No description provided for @homeNoRunsMatchFilter.
  ///
  /// In en, this message translates to:
  /// **'No runs match this filter.'**
  String get homeNoRunsMatchFilter;

  /// No description provided for @homeShowAll.
  ///
  /// In en, this message translates to:
  /// **'Show all'**
  String get homeShowAll;

  /// No description provided for @homeAllRuns.
  ///
  /// In en, this message translates to:
  /// **'All Runs'**
  String get homeAllRuns;

  /// No description provided for @homeNewSong.
  ///
  /// In en, this message translates to:
  /// **'New Song'**
  String get homeNewSong;

  /// No description provided for @homeRecent.
  ///
  /// In en, this message translates to:
  /// **'Recent'**
  String get homeRecent;

  /// No description provided for @homeTracksCount.
  ///
  /// In en, this message translates to:
  /// **'{count} tracks'**
  String homeTracksCount(int count);

  /// No description provided for @homeResults.
  ///
  /// In en, this message translates to:
  /// **'Results'**
  String get homeResults;

  /// No description provided for @homeYourSongs.
  ///
  /// In en, this message translates to:
  /// **'Your songs'**
  String get homeYourSongs;

  /// No description provided for @homeNoSongsMatchSearch.
  ///
  /// In en, this message translates to:
  /// **'No songs match your search'**
  String get homeNoSongsMatchSearch;

  /// No description provided for @homeUntitled.
  ///
  /// In en, this message translates to:
  /// **'(untitled)'**
  String get homeUntitled;

  /// No description provided for @homeSearchHint.
  ///
  /// In en, this message translates to:
  /// **'Search your songs…'**
  String get homeSearchHint;

  /// No description provided for @homeLatestRelease.
  ///
  /// In en, this message translates to:
  /// **'◆  LATEST RELEASE'**
  String get homeLatestRelease;

  /// No description provided for @homePlay.
  ///
  /// In en, this message translates to:
  /// **'Play'**
  String get homePlay;

  /// No description provided for @homeDetails.
  ///
  /// In en, this message translates to:
  /// **'Details'**
  String get homeDetails;

  /// No description provided for @homeEpisodesCount.
  ///
  /// In en, this message translates to:
  /// **'{count} episodes'**
  String homeEpisodesCount(int count);

  /// No description provided for @homeEpisodeAbbrev.
  ///
  /// In en, this message translates to:
  /// **'EP {number}'**
  String homeEpisodeAbbrev(int number);

  /// No description provided for @homeYourStories.
  ///
  /// In en, this message translates to:
  /// **'Your stories'**
  String get homeYourStories;

  /// No description provided for @homeNoRenderedVideos.
  ///
  /// In en, this message translates to:
  /// **'No rendered videos yet'**
  String get homeNoRenderedVideos;

  /// No description provided for @homeApproveScriptHint.
  ///
  /// In en, this message translates to:
  /// **'Approve a script and your video will show up here.'**
  String get homeApproveScriptHint;

  /// No description provided for @homeServerUnreachable.
  ///
  /// In en, this message translates to:
  /// **'Could not reach the server.'**
  String get homeServerUnreachable;

  /// No description provided for @homeHeroTagline.
  ///
  /// In en, this message translates to:
  /// **'AI-powered Arabic horror shorts'**
  String get homeHeroTagline;

  /// No description provided for @homeHeroSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Create your short stories with AI'**
  String get homeHeroSubtitle;

  /// No description provided for @homeStartCreating.
  ///
  /// In en, this message translates to:
  /// **'Start creating'**
  String get homeStartCreating;

  /// No description provided for @homeFreeToWrite.
  ///
  /// In en, this message translates to:
  /// **'Free to write · Subscribe to render'**
  String get homeFreeToWrite;

  /// No description provided for @homeChooseTheme.
  ///
  /// In en, this message translates to:
  /// **'Choose a theme'**
  String get homeChooseTheme;

  /// No description provided for @homeChooseThemeSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Tap to start a new story with this style'**
  String get homeChooseThemeSubtitle;

  /// No description provided for @homeHowItWorks.
  ///
  /// In en, this message translates to:
  /// **'How it works'**
  String get homeHowItWorks;

  /// No description provided for @homePlans.
  ///
  /// In en, this message translates to:
  /// **'Plans'**
  String get homePlans;

  /// No description provided for @homeRunsCount.
  ///
  /// In en, this message translates to:
  /// **'({count} runs)'**
  String homeRunsCount(int count);

  /// No description provided for @homeCleanFailed.
  ///
  /// In en, this message translates to:
  /// **'Clean {count} failed'**
  String homeCleanFailed(int count);

  /// No description provided for @homeFilterAll.
  ///
  /// In en, this message translates to:
  /// **'All'**
  String get homeFilterAll;

  /// No description provided for @homeFilterComplete.
  ///
  /// In en, this message translates to:
  /// **'Complete'**
  String get homeFilterComplete;

  /// No description provided for @homeFilterAwaiting.
  ///
  /// In en, this message translates to:
  /// **'Awaiting'**
  String get homeFilterAwaiting;

  /// No description provided for @homeFilterRunning.
  ///
  /// In en, this message translates to:
  /// **'Running'**
  String get homeFilterRunning;

  /// No description provided for @homeFilterFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed'**
  String get homeFilterFailed;

  /// No description provided for @homeStatusWritingLyrics.
  ///
  /// In en, this message translates to:
  /// **'Writing lyrics'**
  String get homeStatusWritingLyrics;

  /// No description provided for @homeStatusReviewApprove.
  ///
  /// In en, this message translates to:
  /// **'Review & approve'**
  String get homeStatusReviewApprove;

  /// No description provided for @homeStatusComposing.
  ///
  /// In en, this message translates to:
  /// **'Composing music'**
  String get homeStatusComposing;

  /// No description provided for @homeStatusDesigningCover.
  ///
  /// In en, this message translates to:
  /// **'Designing cover'**
  String get homeStatusDesigningCover;

  /// No description provided for @homeStatusSyncingBeat.
  ///
  /// In en, this message translates to:
  /// **'Syncing to the beat'**
  String get homeStatusSyncingBeat;

  /// No description provided for @homeStatusSyncingLyrics.
  ///
  /// In en, this message translates to:
  /// **'Syncing lyrics'**
  String get homeStatusSyncingLyrics;

  /// No description provided for @homeStatusRendering.
  ///
  /// In en, this message translates to:
  /// **'Rendering video'**
  String get homeStatusRendering;

  /// No description provided for @homeStatusReady.
  ///
  /// In en, this message translates to:
  /// **'Ready'**
  String get homeStatusReady;

  /// No description provided for @homeStatusPending.
  ///
  /// In en, this message translates to:
  /// **'Pending'**
  String get homeStatusPending;

  /// No description provided for @homeYourPlan.
  ///
  /// In en, this message translates to:
  /// **'Your plan'**
  String get homeYourPlan;

  /// No description provided for @homeRecommended.
  ///
  /// In en, this message translates to:
  /// **'Recommended'**
  String get homeRecommended;

  /// No description provided for @homeCreditsCount.
  ///
  /// In en, this message translates to:
  /// **'{count} credits'**
  String homeCreditsCount(int count);

  /// No description provided for @homeSeeFullPlans.
  ///
  /// In en, this message translates to:
  /// **'See full plans'**
  String get homeSeeFullPlans;

  /// No description provided for @homePlanStarter.
  ///
  /// In en, this message translates to:
  /// **'Starter'**
  String get homePlanStarter;

  /// No description provided for @homePlanCreator.
  ///
  /// In en, this message translates to:
  /// **'Creator'**
  String get homePlanCreator;

  /// No description provided for @homePlanPro.
  ///
  /// In en, this message translates to:
  /// **'Pro'**
  String get homePlanPro;

  /// No description provided for @homeStep1Title.
  ///
  /// In en, this message translates to:
  /// **'Write a premise'**
  String get homeStep1Title;

  /// No description provided for @homeStep1Subtitle.
  ///
  /// In en, this message translates to:
  /// **'One sentence is enough'**
  String get homeStep1Subtitle;

  /// No description provided for @homeStep2Title.
  ///
  /// In en, this message translates to:
  /// **'AI writes your script'**
  String get homeStep2Title;

  /// No description provided for @homeStep2Subtitle.
  ///
  /// In en, this message translates to:
  /// **'Arabic, in seconds — free for everyone'**
  String get homeStep2Subtitle;

  /// No description provided for @homeStep3Title.
  ///
  /// In en, this message translates to:
  /// **'Subscribe to render the video'**
  String get homeStep3Title;

  /// No description provided for @homeStep3Subtitle.
  ///
  /// In en, this message translates to:
  /// **'Each clip uses 1 credit'**
  String get homeStep3Subtitle;

  /// No description provided for @homeMakeFirstSong.
  ///
  /// In en, this message translates to:
  /// **'Make your first AI song'**
  String get homeMakeFirstSong;

  /// No description provided for @homePickSampleHint.
  ///
  /// In en, this message translates to:
  /// **'Pick a sample to start with, or tap \"New song\" to write your own.'**
  String get homePickSampleHint;

  /// No description provided for @homeNewSongFromScratch.
  ///
  /// In en, this message translates to:
  /// **'New song from scratch'**
  String get homeNewSongFromScratch;

  /// No description provided for @homeThemeFolkloric.
  ///
  /// In en, this message translates to:
  /// **'Folkloric'**
  String get homeThemeFolkloric;

  /// No description provided for @homeThemeFolkloricDesc.
  ///
  /// In en, this message translates to:
  /// **'Ancestral tales, jinn, old wells'**
  String get homeThemeFolkloricDesc;

  /// No description provided for @homeThemeUrban.
  ///
  /// In en, this message translates to:
  /// **'Urban'**
  String get homeThemeUrban;

  /// No description provided for @homeThemeUrbanDesc.
  ///
  /// In en, this message translates to:
  /// **'City legends, late-night streets'**
  String get homeThemeUrbanDesc;

  /// No description provided for @homeThemeWilderness.
  ///
  /// In en, this message translates to:
  /// **'Wilderness'**
  String get homeThemeWilderness;

  /// No description provided for @homeThemeWildernessDesc.
  ///
  /// In en, this message translates to:
  /// **'Forests, deserts, the unknown'**
  String get homeThemeWildernessDesc;

  /// No description provided for @homeThemeMemory.
  ///
  /// In en, this message translates to:
  /// **'Memory'**
  String get homeThemeMemory;

  /// No description provided for @homeThemeMemoryDesc.
  ///
  /// In en, this message translates to:
  /// **'Psychological, half-remembered'**
  String get homeThemeMemoryDesc;

  /// No description provided for @homeThemeDomestic.
  ///
  /// In en, this message translates to:
  /// **'Domestic'**
  String get homeThemeDomestic;

  /// No description provided for @homeThemeDomesticDesc.
  ///
  /// In en, this message translates to:
  /// **'Home, family, the everyday turned'**
  String get homeThemeDomesticDesc;

  /// No description provided for @homeThemeTravel.
  ///
  /// In en, this message translates to:
  /// **'Travel'**
  String get homeThemeTravel;

  /// No description provided for @homeThemeTravelDesc.
  ///
  /// In en, this message translates to:
  /// **'On the road, far from home'**
  String get homeThemeTravelDesc;

  /// No description provided for @homeThemeTech.
  ///
  /// In en, this message translates to:
  /// **'Tech'**
  String get homeThemeTech;

  /// No description provided for @homeThemeTechDesc.
  ///
  /// In en, this message translates to:
  /// **'Screens, signals, machines'**
  String get homeThemeTechDesc;

  /// No description provided for @homeThemeWorkplace.
  ///
  /// In en, this message translates to:
  /// **'Workplace'**
  String get homeThemeWorkplace;

  /// No description provided for @homeThemeWorkplaceDesc.
  ///
  /// In en, this message translates to:
  /// **'Offices, shops, after-hours'**
  String get homeThemeWorkplaceDesc;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['ar', 'en'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'ar':
      return AppLocalizationsAr();
    case 'en':
      return AppLocalizationsEn();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
