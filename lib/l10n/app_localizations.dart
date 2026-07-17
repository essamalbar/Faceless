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

  /// No description provided for @newSongTitle.
  ///
  /// In en, this message translates to:
  /// **'New song'**
  String get newSongTitle;

  /// No description provided for @newSongModeTheme.
  ///
  /// In en, this message translates to:
  /// **'Write a theme'**
  String get newSongModeTheme;

  /// No description provided for @newSongModeUpload.
  ///
  /// In en, this message translates to:
  /// **'Upload a song'**
  String get newSongModeUpload;

  /// No description provided for @newSongUploadExplainer.
  ///
  /// In en, this message translates to:
  /// **'Upload a song and the AI makes a faithful cover — it keeps the melody and words, performed by a new voice. The voice will differ from the original. Review and edit the words before any credit is spent.'**
  String get newSongUploadExplainer;

  /// No description provided for @newSongThemeExplainer.
  ///
  /// In en, this message translates to:
  /// **'The AI will write lyrics and a cover image prompt. You can review and edit both before any credit is spent.'**
  String get newSongThemeExplainer;

  /// No description provided for @newSongFileReadError.
  ///
  /// In en, this message translates to:
  /// **'Couldn\'t read that file — try another.'**
  String get newSongFileReadError;

  /// No description provided for @newSongFilePickerError.
  ///
  /// In en, this message translates to:
  /// **'Could not open the file picker: {error}'**
  String newSongFilePickerError(String error);

  /// No description provided for @newSongChooseAudioError.
  ///
  /// In en, this message translates to:
  /// **'Choose an audio file to cover'**
  String get newSongChooseAudioError;

  /// No description provided for @newSongThemeRequired.
  ///
  /// In en, this message translates to:
  /// **'Theme is required'**
  String get newSongThemeRequired;

  /// No description provided for @newSongChooseAudioFile.
  ///
  /// In en, this message translates to:
  /// **'Choose audio file (mp3, m4a, wav…)'**
  String get newSongChooseAudioFile;

  /// No description provided for @newSongSelectedFile.
  ///
  /// In en, this message translates to:
  /// **'Selected: {name}'**
  String newSongSelectedFile(String name);

  /// No description provided for @newSongThemeLabel.
  ///
  /// In en, this message translates to:
  /// **'Theme'**
  String get newSongThemeLabel;

  /// No description provided for @newSongThemeHint.
  ///
  /// In en, this message translates to:
  /// **'A sad song about the moon'**
  String get newSongThemeHint;

  /// No description provided for @newSongCustomLyricsLabel.
  ///
  /// In en, this message translates to:
  /// **'Custom lyrics (optional)'**
  String get newSongCustomLyricsLabel;

  /// No description provided for @newSongCustomLyricsHint.
  ///
  /// In en, this message translates to:
  /// **'Leave empty for AI'**
  String get newSongCustomLyricsHint;

  /// No description provided for @newSongQuickStyles.
  ///
  /// In en, this message translates to:
  /// **'Quick styles'**
  String get newSongQuickStyles;

  /// No description provided for @newSongPresetRomanticArabic.
  ///
  /// In en, this message translates to:
  /// **'Romantic Arabic (reference)'**
  String get newSongPresetRomanticArabic;

  /// No description provided for @newSongPresetSadArabicBallad.
  ///
  /// In en, this message translates to:
  /// **'Sad Arabic Ballad'**
  String get newSongPresetSadArabicBallad;

  /// No description provided for @newSongPresetKhaleejiRomantic.
  ///
  /// In en, this message translates to:
  /// **'Khaleeji Romantic'**
  String get newSongPresetKhaleejiRomantic;

  /// No description provided for @newSongPresetUpbeatArabicPop.
  ///
  /// In en, this message translates to:
  /// **'Upbeat Arabic Pop'**
  String get newSongPresetUpbeatArabicPop;

  /// No description provided for @newSongPresetAcousticSlow.
  ///
  /// In en, this message translates to:
  /// **'Acoustic Slow'**
  String get newSongPresetAcousticSlow;

  /// No description provided for @newSongPresetEnglishPopBallad.
  ///
  /// In en, this message translates to:
  /// **'English Pop Ballad'**
  String get newSongPresetEnglishPopBallad;

  /// No description provided for @newSongStyleHintLabel.
  ///
  /// In en, this message translates to:
  /// **'Style hint'**
  String get newSongStyleHintLabel;

  /// No description provided for @newSongYourTouchLabel.
  ///
  /// In en, this message translates to:
  /// **'Your touch (optional)'**
  String get newSongYourTouchLabel;

  /// No description provided for @newSongStyleHintHint.
  ///
  /// In en, this message translates to:
  /// **'Pick a Quick style above, or type your own. Leave empty for AI to auto-pick.'**
  String get newSongStyleHintHint;

  /// No description provided for @newSongYourTouchHint.
  ///
  /// In en, this message translates to:
  /// **'e.g. make it more upbeat, add oud, slower tempo…'**
  String get newSongYourTouchHint;

  /// No description provided for @newSongLanguageLabel.
  ///
  /// In en, this message translates to:
  /// **'Language'**
  String get newSongLanguageLabel;

  /// No description provided for @newSongLanguageArabic.
  ///
  /// In en, this message translates to:
  /// **'Arabic'**
  String get newSongLanguageArabic;

  /// No description provided for @newSongLanguageEnglish.
  ///
  /// In en, this message translates to:
  /// **'English'**
  String get newSongLanguageEnglish;

  /// No description provided for @newSongLanguageSpanish.
  ///
  /// In en, this message translates to:
  /// **'Spanish'**
  String get newSongLanguageSpanish;

  /// No description provided for @newSongLanguageFrench.
  ///
  /// In en, this message translates to:
  /// **'French'**
  String get newSongLanguageFrench;

  /// No description provided for @newSongLanguageTurkish.
  ///
  /// In en, this message translates to:
  /// **'Turkish'**
  String get newSongLanguageTurkish;

  /// No description provided for @newSongVocalLabel.
  ///
  /// In en, this message translates to:
  /// **'Vocal'**
  String get newSongVocalLabel;

  /// No description provided for @newSongVocalMale.
  ///
  /// In en, this message translates to:
  /// **'Male'**
  String get newSongVocalMale;

  /// No description provided for @newSongVocalFemale.
  ///
  /// In en, this message translates to:
  /// **'Female'**
  String get newSongVocalFemale;

  /// No description provided for @newSongVocalAuto.
  ///
  /// In en, this message translates to:
  /// **'Auto (Suno picks)'**
  String get newSongVocalAuto;

  /// No description provided for @newSongSunoModelLabel.
  ///
  /// In en, this message translates to:
  /// **'Suno model'**
  String get newSongSunoModelLabel;

  /// No description provided for @newSongSunoModelHelper.
  ///
  /// In en, this message translates to:
  /// **'Newer = better quality. V3_5 is excluded (obvious-AI sound).'**
  String get newSongSunoModelHelper;

  /// No description provided for @newSongSunoModelDefault.
  ///
  /// In en, this message translates to:
  /// **'Default (V5_5)'**
  String get newSongSunoModelDefault;

  /// No description provided for @newSongSunoModelLatest.
  ///
  /// In en, this message translates to:
  /// **'V5_5 (latest)'**
  String get newSongSunoModelLatest;

  /// No description provided for @newSongSunoModelLegacy.
  ///
  /// In en, this message translates to:
  /// **'V4 (legacy)'**
  String get newSongSunoModelLegacy;

  /// No description provided for @newSongVideoTypeLabel.
  ///
  /// In en, this message translates to:
  /// **'Video type'**
  String get newSongVideoTypeLabel;

  /// No description provided for @newSongVideoStatic.
  ///
  /// In en, this message translates to:
  /// **'Static cover · 1 credit'**
  String get newSongVideoStatic;

  /// No description provided for @newSongVideoCinematic.
  ///
  /// In en, this message translates to:
  /// **'Cinematic video · 3 credits'**
  String get newSongVideoCinematic;

  /// No description provided for @newSongVoiceLabel.
  ///
  /// In en, this message translates to:
  /// **'Voice'**
  String get newSongVoiceLabel;

  /// No description provided for @newSongVoiceHelper.
  ///
  /// In en, this message translates to:
  /// **'Reuse a saved singer voice from a previous song'**
  String get newSongVoiceHelper;

  /// No description provided for @newSongVoiceAuto.
  ///
  /// In en, this message translates to:
  /// **'Auto (let Suno pick)'**
  String get newSongVoiceAuto;

  /// No description provided for @newSongGenerating.
  ///
  /// In en, this message translates to:
  /// **'Generating…'**
  String get newSongGenerating;

  /// No description provided for @newSongGenerateButton.
  ///
  /// In en, this message translates to:
  /// **'Generate my song'**
  String get newSongGenerateButton;

  /// No description provided for @newSongReviewNotice.
  ///
  /// In en, this message translates to:
  /// **'You will review lyrics + cover prompt before any credit is spent.'**
  String get newSongReviewNotice;

  /// No description provided for @approveReviewDraft.
  ///
  /// In en, this message translates to:
  /// **'Review draft'**
  String get approveReviewDraft;

  /// No description provided for @approveAnalyzing.
  ///
  /// In en, this message translates to:
  /// **'Analyzing the song…\nThis can take a few minutes for imports.'**
  String get approveAnalyzing;

  /// No description provided for @approvePreparing.
  ///
  /// In en, this message translates to:
  /// **'Preparing…'**
  String get approvePreparing;

  /// No description provided for @approveAnalysisFailed.
  ///
  /// In en, this message translates to:
  /// **'Analysis failed — please try again'**
  String get approveAnalysisFailed;

  /// No description provided for @approveTimedOut.
  ///
  /// In en, this message translates to:
  /// **'Timed out waiting for lyrics (exceeded 5 minutes)'**
  String get approveTimedOut;

  /// No description provided for @approveEditLyrics.
  ///
  /// In en, this message translates to:
  /// **'Edit lyrics'**
  String get approveEditLyrics;

  /// No description provided for @approveKeepSectionTags.
  ///
  /// In en, this message translates to:
  /// **'Keep Suno section tags ([Verse 1], [Chorus]) intact — Suno uses them to structure the arrangement. Dropping them gives a formless song.'**
  String get approveKeepSectionTags;

  /// No description provided for @approveLyricsTooLong.
  ///
  /// In en, this message translates to:
  /// **'Lyrics exceed 4000 chars'**
  String get approveLyricsTooLong;

  /// No description provided for @approveLyricsSection.
  ///
  /// In en, this message translates to:
  /// **'Lyrics'**
  String get approveLyricsSection;

  /// No description provided for @approveEdit.
  ///
  /// In en, this message translates to:
  /// **'Edit'**
  String get approveEdit;

  /// No description provided for @approveReroll.
  ///
  /// In en, this message translates to:
  /// **'Re-roll'**
  String get approveReroll;

  /// No description provided for @approveStyleSection.
  ///
  /// In en, this message translates to:
  /// **'Style'**
  String get approveStyleSection;

  /// No description provided for @approveCoverPromptSection.
  ///
  /// In en, this message translates to:
  /// **'Cover prompt'**
  String get approveCoverPromptSection;

  /// No description provided for @approveCost.
  ///
  /// In en, this message translates to:
  /// **'{count, plural, =1{Cost: 1 credit (~{usd})} other{Cost: {count} credits (~{usd})}}'**
  String approveCost(int count, String usd);

  /// No description provided for @approveDiscard.
  ///
  /// In en, this message translates to:
  /// **'Discard'**
  String get approveDiscard;

  /// No description provided for @approveApproveGenerate.
  ///
  /// In en, this message translates to:
  /// **'Approve & generate'**
  String get approveApproveGenerate;

  /// No description provided for @songDetailTitleFallback.
  ///
  /// In en, this message translates to:
  /// **'Song'**
  String get songDetailTitleFallback;

  /// No description provided for @songDetailStatusWaitingApproval.
  ///
  /// In en, this message translates to:
  /// **'Waiting for approval'**
  String get songDetailStatusWaitingApproval;

  /// No description provided for @songDetailStatusGeneratingSong.
  ///
  /// In en, this message translates to:
  /// **'Generating song (Suno ~30 s)…'**
  String get songDetailStatusGeneratingSong;

  /// No description provided for @songDetailStatusGeneratingCover.
  ///
  /// In en, this message translates to:
  /// **'Generating cover (~15 s)…'**
  String get songDetailStatusGeneratingCover;

  /// No description provided for @songDetailStatusAssembling.
  ///
  /// In en, this message translates to:
  /// **'Assembling video…'**
  String get songDetailStatusAssembling;

  /// No description provided for @songDetailStatusDone.
  ///
  /// In en, this message translates to:
  /// **'Done'**
  String get songDetailStatusDone;

  /// No description provided for @songDetailSwitchingTake.
  ///
  /// In en, this message translates to:
  /// **'Switching to Take {take} — ready in ~1 min'**
  String songDetailSwitchingTake(int take);

  /// No description provided for @songDetailSwapFailed.
  ///
  /// In en, this message translates to:
  /// **'Swap failed: {error}'**
  String songDetailSwapFailed(String error);

  /// No description provided for @songDetailRetryTitle.
  ///
  /// In en, this message translates to:
  /// **'Retry will re-charge'**
  String get songDetailRetryTitle;

  /// No description provided for @songDetailRetryBody.
  ///
  /// In en, this message translates to:
  /// **'The song generation failed. Retrying will spawn a new Suno job and deduct credits again. Continue?'**
  String get songDetailRetryBody;

  /// No description provided for @songDetailRetryFailed.
  ///
  /// In en, this message translates to:
  /// **'Retry failed: {error}'**
  String songDetailRetryFailed(String error);

  /// No description provided for @songDetailDownloadFailed.
  ///
  /// In en, this message translates to:
  /// **'Download failed: {error}'**
  String songDetailDownloadFailed(String error);

  /// No description provided for @songDetailDeleteTitle.
  ///
  /// In en, this message translates to:
  /// **'Delete this song?'**
  String get songDetailDeleteTitle;

  /// No description provided for @songDetailDeleteBody.
  ///
  /// In en, this message translates to:
  /// **'This permanently removes the song, cover, takes, and final video for \"{title}\". Credits already spent on Suno + Flux are not refunded.'**
  String songDetailDeleteBody(String title);

  /// No description provided for @songDetailThisRun.
  ///
  /// In en, this message translates to:
  /// **'this run'**
  String get songDetailThisRun;

  /// No description provided for @songDetailSongDeleted.
  ///
  /// In en, this message translates to:
  /// **'Song deleted'**
  String get songDetailSongDeleted;

  /// No description provided for @songDetailDeleteFailed.
  ///
  /// In en, this message translates to:
  /// **'Delete failed: {error}'**
  String songDetailDeleteFailed(String error);

  /// No description provided for @songDetailSaveVoiceTitle.
  ///
  /// In en, this message translates to:
  /// **'Save this voice'**
  String get songDetailSaveVoiceTitle;

  /// No description provided for @songDetailSaveVoiceBody.
  ///
  /// In en, this message translates to:
  /// **'Locks the singer\'s voice from this song so you can reuse it on future generations.'**
  String get songDetailSaveVoiceBody;

  /// No description provided for @songDetailVoiceNameLabel.
  ///
  /// In en, this message translates to:
  /// **'Voice name'**
  String get songDetailVoiceNameLabel;

  /// No description provided for @songDetailDescriptionLabel.
  ///
  /// In en, this message translates to:
  /// **'Description'**
  String get songDetailDescriptionLabel;

  /// No description provided for @songDetailDescriptionHelper.
  ///
  /// In en, this message translates to:
  /// **'Genre, mood, vocal qualities'**
  String get songDetailDescriptionHelper;

  /// No description provided for @songDetailVoiceSaved.
  ///
  /// In en, this message translates to:
  /// **'Voice \"{name}\" saved. Use it on the next song from the New Song form.'**
  String songDetailVoiceSaved(String name);

  /// No description provided for @songDetailSaveFailed.
  ///
  /// In en, this message translates to:
  /// **'Save failed: {error}'**
  String songDetailSaveFailed(String error);

  /// No description provided for @songDetailShareTitle.
  ///
  /// In en, this message translates to:
  /// **'Share this song'**
  String get songDetailShareTitle;

  /// No description provided for @songDetailShareBody.
  ///
  /// In en, this message translates to:
  /// **'Anyone with this link can play the song — no sign-in needed. Paste it in WhatsApp, Twitter, or anywhere; the preview shows the cover.'**
  String get songDetailShareBody;

  /// No description provided for @songDetailOpen.
  ///
  /// In en, this message translates to:
  /// **'Open'**
  String get songDetailOpen;

  /// No description provided for @songDetailCopyLink.
  ///
  /// In en, this message translates to:
  /// **'Copy link'**
  String get songDetailCopyLink;

  /// No description provided for @songDetailLinkCopied.
  ///
  /// In en, this message translates to:
  /// **'Link copied to clipboard'**
  String get songDetailLinkCopied;

  /// No description provided for @songDetailShareFailed.
  ///
  /// In en, this message translates to:
  /// **'Share failed: {error}'**
  String songDetailShareFailed(String error);

  /// No description provided for @songDetailAiSongFallback.
  ///
  /// In en, this message translates to:
  /// **'AI song'**
  String get songDetailAiSongFallback;

  /// No description provided for @songDetailWatermarkTitle.
  ///
  /// In en, this message translates to:
  /// **'Apply Faceless Lab watermark?'**
  String get songDetailWatermarkTitle;

  /// No description provided for @songDetailWatermarkBody.
  ///
  /// In en, this message translates to:
  /// **'Re-renders the song\'s video to burn in the brand mark (top-right of the frame) and embed copyright + share-URL metadata into the MP4. The original audio and lyrics are preserved.\n\nTakes about 3–6 minutes. You can keep using the app — the watermark will appear once the render completes.'**
  String get songDetailWatermarkBody;

  /// No description provided for @songDetailApplyWatermark.
  ///
  /// In en, this message translates to:
  /// **'Apply watermark'**
  String get songDetailApplyWatermark;

  /// No description provided for @songDetailApplyingWatermark.
  ///
  /// In en, this message translates to:
  /// **'Applying watermark — this takes 3–6 minutes…'**
  String get songDetailApplyingWatermark;

  /// No description provided for @songDetailWatermarkApplied.
  ///
  /// In en, this message translates to:
  /// **'Watermark applied in {seconds} seconds.'**
  String songDetailWatermarkApplied(String seconds);

  /// No description provided for @songDetailWatermarkFailed.
  ///
  /// In en, this message translates to:
  /// **'Watermark failed: {error}'**
  String songDetailWatermarkFailed(String error);

  /// No description provided for @songDetailRerollTitle.
  ///
  /// In en, this message translates to:
  /// **'Re-roll voice takes?'**
  String get songDetailRerollTitle;

  /// No description provided for @songDetailRerollBody.
  ///
  /// In en, this message translates to:
  /// **'Generates two fresh Suno vocal takes (~\$0.05). Lyrics, style, and cover are preserved. Use this when both current takes missed the mood.'**
  String get songDetailRerollBody;

  /// No description provided for @songDetailReroll.
  ///
  /// In en, this message translates to:
  /// **'Re-roll'**
  String get songDetailReroll;

  /// No description provided for @songDetailRerolling.
  ///
  /// In en, this message translates to:
  /// **'Re-rolling Suno takes — ready in ~2 min'**
  String get songDetailRerolling;

  /// No description provided for @songDetailRerollFailed.
  ///
  /// In en, this message translates to:
  /// **'Re-roll failed: {error}'**
  String songDetailRerollFailed(String error);

  /// No description provided for @songDetailRegenCoverTitle.
  ///
  /// In en, this message translates to:
  /// **'Regenerate cover?'**
  String get songDetailRegenCoverTitle;

  /// No description provided for @songDetailRegenCoverBody.
  ///
  /// In en, this message translates to:
  /// **'Calls Flux for a fresh cover image (~\$0.03) and re-assembles the video with the new cover. Suno output is preserved. Takes ~2 minutes.'**
  String get songDetailRegenCoverBody;

  /// No description provided for @songDetailRegenerate.
  ///
  /// In en, this message translates to:
  /// **'Regenerate'**
  String get songDetailRegenerate;

  /// No description provided for @songDetailRegeneratingCover.
  ///
  /// In en, this message translates to:
  /// **'Regenerating cover — refresh in ~2 min'**
  String get songDetailRegeneratingCover;

  /// No description provided for @songDetailFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed: {error}'**
  String songDetailFailed(String error);

  /// No description provided for @songDetailDeleteTooltip.
  ///
  /// In en, this message translates to:
  /// **'Delete this song'**
  String get songDetailDeleteTooltip;

  /// No description provided for @songDetailDownloadMp4.
  ///
  /// In en, this message translates to:
  /// **'Download MP4'**
  String get songDetailDownloadMp4;

  /// No description provided for @songDetailDownloadMp3.
  ///
  /// In en, this message translates to:
  /// **'Download MP3'**
  String get songDetailDownloadMp3;

  /// No description provided for @songDetailShare.
  ///
  /// In en, this message translates to:
  /// **'Share'**
  String get songDetailShare;

  /// No description provided for @songDetailRegenCoverButton.
  ///
  /// In en, this message translates to:
  /// **'Regenerate cover'**
  String get songDetailRegenCoverButton;

  /// No description provided for @songDetailRerollTakesButton.
  ///
  /// In en, this message translates to:
  /// **'Re-roll voice takes'**
  String get songDetailRerollTakesButton;

  /// No description provided for @songDetailPlayVideo.
  ///
  /// In en, this message translates to:
  /// **'Play video'**
  String get songDetailPlayVideo;

  /// No description provided for @songDetailDownload.
  ///
  /// In en, this message translates to:
  /// **'Download'**
  String get songDetailDownload;

  /// No description provided for @songDetailVideoLoadError.
  ///
  /// In en, this message translates to:
  /// **'Could not load video: {error}'**
  String songDetailVideoLoadError(String error);

  /// No description provided for @songDetailActiveTake.
  ///
  /// In en, this message translates to:
  /// **'Active take'**
  String get songDetailActiveTake;

  /// No description provided for @songDetailTakeChosen.
  ///
  /// In en, this message translates to:
  /// **'Take {take} ✓'**
  String songDetailTakeChosen(int take);

  /// No description provided for @songDetailUseTake.
  ///
  /// In en, this message translates to:
  /// **'Use Take {take}'**
  String songDetailUseTake(int take);

  /// No description provided for @songDetailFailSongTitle.
  ///
  /// In en, this message translates to:
  /// **'Song generation failed'**
  String get songDetailFailSongTitle;

  /// No description provided for @songDetailFailSongHint.
  ///
  /// In en, this message translates to:
  /// **'Retry will spawn a fresh Suno job — this re-charges credits.'**
  String get songDetailFailSongHint;

  /// No description provided for @songDetailFailCoverTitle.
  ///
  /// In en, this message translates to:
  /// **'Cover image failed'**
  String get songDetailFailCoverTitle;

  /// No description provided for @songDetailFailCoverHint.
  ///
  /// In en, this message translates to:
  /// **'Suno output is saved. Retry only re-runs Flux + ffmpeg (~\$0.03).'**
  String get songDetailFailCoverHint;

  /// No description provided for @songDetailFailAssembleTitle.
  ///
  /// In en, this message translates to:
  /// **'Video assembly failed'**
  String get songDetailFailAssembleTitle;

  /// No description provided for @songDetailFailAssembleHint.
  ///
  /// In en, this message translates to:
  /// **'Suno + cover are saved. Retry only re-runs ffmpeg (free).'**
  String get songDetailFailAssembleHint;

  /// No description provided for @songDetailErrorFallback.
  ///
  /// In en, this message translates to:
  /// **'Error'**
  String get songDetailErrorFallback;

  /// No description provided for @songDetailUnknownError.
  ///
  /// In en, this message translates to:
  /// **'Unknown error'**
  String get songDetailUnknownError;

  /// No description provided for @landingHeroPill.
  ///
  /// In en, this message translates to:
  /// **'AI Music Studio · Arabic & beyond'**
  String get landingHeroPill;

  /// No description provided for @landingHeroTitlePart1.
  ///
  /// In en, this message translates to:
  /// **'Turn any idea into a '**
  String get landingHeroTitlePart1;

  /// No description provided for @landingHeroTitlePart2Accent.
  ///
  /// In en, this message translates to:
  /// **'finished song.'**
  String get landingHeroTitlePart2Accent;

  /// No description provided for @landingHeroSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Write a theme, or upload a track for a faithful cover. Faceless composes the lyrics, voices it, designs the cover, and cuts a cinematic video — you approve before a single credit is spent.'**
  String get landingHeroSubtitle;

  /// No description provided for @landingStartCreating.
  ///
  /// In en, this message translates to:
  /// **'Start creating'**
  String get landingStartCreating;

  /// No description provided for @landingTrustLine.
  ///
  /// In en, this message translates to:
  /// **'★★★★★   Loved by creators · 60 free credits to start'**
  String get landingTrustLine;

  /// No description provided for @landingNowGenerating.
  ///
  /// In en, this message translates to:
  /// **'Now generating'**
  String get landingNowGenerating;

  /// No description provided for @landingSampleTagline.
  ///
  /// In en, this message translates to:
  /// **'Cinematic · 92 BPM · Arabic pop'**
  String get landingSampleTagline;

  /// No description provided for @landingSectionHowItWorks.
  ///
  /// In en, this message translates to:
  /// **'How it works'**
  String get landingSectionHowItWorks;

  /// No description provided for @landingSectionShowcase.
  ///
  /// In en, this message translates to:
  /// **'What it makes'**
  String get landingSectionShowcase;

  /// No description provided for @landingSectionPricing.
  ///
  /// In en, this message translates to:
  /// **'Pricing'**
  String get landingSectionPricing;

  /// No description provided for @landingStep1Title.
  ///
  /// In en, this message translates to:
  /// **'Pick a mode'**
  String get landingStep1Title;

  /// No description provided for @landingStep1Body.
  ///
  /// In en, this message translates to:
  /// **'Horror shorts: one-sentence premise becomes a cinematic Arabic story with characters and shots. Songs: a theme + style becomes a full Arabic ballad with cover art.'**
  String get landingStep1Body;

  /// No description provided for @landingStep2Title.
  ///
  /// In en, this message translates to:
  /// **'Review before you spend'**
  String get landingStep2Title;

  /// No description provided for @landingStep2Body.
  ///
  /// In en, this message translates to:
  /// **'AI drafts the script or lyrics + cover prompt for free. You see exactly what gets generated. Approve only when it feels right.'**
  String get landingStep2Body;

  /// No description provided for @landingStep3Title.
  ///
  /// In en, this message translates to:
  /// **'Download or share'**
  String get landingStep3Title;

  /// No description provided for @landingStep3Body.
  ///
  /// In en, this message translates to:
  /// **'Square MP4 with music + visuals, ready for WhatsApp and Instagram. Save the lyrics or script as a PDF. Share a public link with OG preview baked in.'**
  String get landingStep3Body;

  /// No description provided for @landingShowcaseTagline1.
  ///
  /// In en, this message translates to:
  /// **'Horror · Folkloric · 2 min'**
  String get landingShowcaseTagline1;

  /// No description provided for @landingShowcaseTagline2.
  ///
  /// In en, this message translates to:
  /// **'Horror · Urban · 90 sec'**
  String get landingShowcaseTagline2;

  /// No description provided for @landingShowcaseTagline3.
  ///
  /// In en, this message translates to:
  /// **'Song · Romantic ballad · 3 min'**
  String get landingShowcaseTagline3;

  /// No description provided for @landingPricingSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Credits power both modes. 1 song ≈ 1 credit. 1 horror clip = 1 credit (avg short = 8–12).'**
  String get landingPricingSubtitle;

  /// No description provided for @landingTierStarter.
  ///
  /// In en, this message translates to:
  /// **'Starter'**
  String get landingTierStarter;

  /// No description provided for @landingTierStarterDesc.
  ///
  /// In en, this message translates to:
  /// **'For trying ideas'**
  String get landingTierStarterDesc;

  /// No description provided for @landingTierCreator.
  ///
  /// In en, this message translates to:
  /// **'Creator'**
  String get landingTierCreator;

  /// No description provided for @landingTierCreatorDesc.
  ///
  /// In en, this message translates to:
  /// **'For weekly drops'**
  String get landingTierCreatorDesc;

  /// No description provided for @landingTierPro.
  ///
  /// In en, this message translates to:
  /// **'Pro'**
  String get landingTierPro;

  /// No description provided for @landingTierProDesc.
  ///
  /// In en, this message translates to:
  /// **'For daily output'**
  String get landingTierProDesc;

  /// No description provided for @landingRecommended.
  ///
  /// In en, this message translates to:
  /// **'Recommended'**
  String get landingRecommended;

  /// No description provided for @landingPerMonth.
  ///
  /// In en, this message translates to:
  /// **'/ month'**
  String get landingPerMonth;

  /// No description provided for @landingCreditsPerMonth.
  ///
  /// In en, this message translates to:
  /// **'{count} credits / month'**
  String landingCreditsPerMonth(int count);

  /// No description provided for @landingStartFree.
  ///
  /// In en, this message translates to:
  /// **'Start free'**
  String get landingStartFree;

  /// No description provided for @landingFooterLine.
  ///
  /// In en, this message translates to:
  /// **'Faceless Lab · faceless-lab.com'**
  String get landingFooterLine;

  /// No description provided for @loginEmailLabel.
  ///
  /// In en, this message translates to:
  /// **'Email'**
  String get loginEmailLabel;

  /// No description provided for @loginPasswordLabel.
  ///
  /// In en, this message translates to:
  /// **'Password'**
  String get loginPasswordLabel;

  /// No description provided for @loginEmailRequired.
  ///
  /// In en, this message translates to:
  /// **'Email is required'**
  String get loginEmailRequired;

  /// No description provided for @loginEmailInvalid.
  ///
  /// In en, this message translates to:
  /// **'Enter a valid email'**
  String get loginEmailInvalid;

  /// No description provided for @loginPasswordRequired.
  ///
  /// In en, this message translates to:
  /// **'Password is required'**
  String get loginPasswordRequired;

  /// No description provided for @loginPasswordMinLength.
  ///
  /// In en, this message translates to:
  /// **'Min 8 characters for new accounts'**
  String get loginPasswordMinLength;

  /// No description provided for @loginAccountCreatedInfo.
  ///
  /// In en, this message translates to:
  /// **'Account created. Check your email to confirm — or sign in directly if email confirmation is disabled.'**
  String get loginAccountCreatedInfo;

  /// No description provided for @loginUnexpectedError.
  ///
  /// In en, this message translates to:
  /// **'Unexpected error: {error}'**
  String loginUnexpectedError(String error);

  /// No description provided for @loginShowPassword.
  ///
  /// In en, this message translates to:
  /// **'Show password'**
  String get loginShowPassword;

  /// No description provided for @loginHidePassword.
  ///
  /// In en, this message translates to:
  /// **'Hide password'**
  String get loginHidePassword;

  /// No description provided for @loginCreateAccount.
  ///
  /// In en, this message translates to:
  /// **'Create account'**
  String get loginCreateAccount;

  /// No description provided for @loginSignUp.
  ///
  /// In en, this message translates to:
  /// **'Sign up'**
  String get loginSignUp;

  /// No description provided for @loginNoAccountYet.
  ///
  /// In en, this message translates to:
  /// **'No account yet? '**
  String get loginNoAccountYet;

  /// No description provided for @loginAlreadyHaveAccount.
  ///
  /// In en, this message translates to:
  /// **'Already have one? '**
  String get loginAlreadyHaveAccount;

  /// No description provided for @loginSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Sign in to manage your runs'**
  String get loginSubtitle;

  /// No description provided for @loginFooterTagline.
  ///
  /// In en, this message translates to:
  /// **'Faceless · Arabic horror, scripted by AI'**
  String get loginFooterTagline;

  /// No description provided for @onboardingSkip.
  ///
  /// In en, this message translates to:
  /// **'Skip'**
  String get onboardingSkip;

  /// No description provided for @onboardingNext.
  ///
  /// In en, this message translates to:
  /// **'Next'**
  String get onboardingNext;

  /// No description provided for @onboardingLetsCreate.
  ///
  /// In en, this message translates to:
  /// **'Let\'s create'**
  String get onboardingLetsCreate;

  /// No description provided for @onboardingSlide1Eyebrow.
  ///
  /// In en, this message translates to:
  /// **'WELCOME'**
  String get onboardingSlide1Eyebrow;

  /// No description provided for @onboardingSlide1Title.
  ///
  /// In en, this message translates to:
  /// **'An Arabic AI studio that respects your wallet'**
  String get onboardingSlide1Title;

  /// No description provided for @onboardingSlide1Body.
  ///
  /// In en, this message translates to:
  /// **'Faceless Lab generates cinematic Arabic horror shorts and original Arabic songs from a single sentence. You\'ll write the premise; we\'ll handle the rest.'**
  String get onboardingSlide1Body;

  /// No description provided for @onboardingSlide2Eyebrow.
  ///
  /// In en, this message translates to:
  /// **'TWO MODES'**
  String get onboardingSlide2Eyebrow;

  /// No description provided for @onboardingSlide2Title.
  ///
  /// In en, this message translates to:
  /// **'Horror shorts. AI songs. One studio.'**
  String get onboardingSlide2Title;

  /// No description provided for @onboardingSlide2Body.
  ///
  /// In en, this message translates to:
  /// **'Switch between Horror (cinematic Arabic shorts in 6 dialects) and Songs (full Suno-vocal tracks with AI cover art). Each render lives in your library and stays sharable forever.'**
  String get onboardingSlide2Body;

  /// No description provided for @onboardingSlide3Eyebrow.
  ///
  /// In en, this message translates to:
  /// **'FAIR PRICING'**
  String get onboardingSlide3Eyebrow;

  /// No description provided for @onboardingSlide3Title.
  ///
  /// In en, this message translates to:
  /// **'Free drafts. You only pay when you generate.'**
  String get onboardingSlide3Title;

  /// No description provided for @onboardingSlide3Body.
  ///
  /// In en, this message translates to:
  /// **'Scripts and lyrics preview at zero cost. Approve when you\'re happy. If a render fails, the credits come back automatically — you never pay for video that didn\'t deliver.'**
  String get onboardingSlide3Body;

  /// No description provided for @onboardingSlide4Eyebrow.
  ///
  /// In en, this message translates to:
  /// **'LET\'S GO'**
  String get onboardingSlide4Eyebrow;

  /// No description provided for @onboardingSlide4Title.
  ///
  /// In en, this message translates to:
  /// **'Your first draft is free.'**
  String get onboardingSlide4Title;

  /// No description provided for @onboardingSlide4Body.
  ///
  /// In en, this message translates to:
  /// **'Tap below and write a sentence. The system will produce a full Arabic script or song lyrics for you to review — all before any credit is spent.'**
  String get onboardingSlide4Body;

  /// No description provided for @settingsResetDefaultsTitle.
  ///
  /// In en, this message translates to:
  /// **'Reset to launcher defaults?'**
  String get settingsResetDefaultsTitle;

  /// No description provided for @settingsResetDefaultsBody.
  ///
  /// In en, this message translates to:
  /// **'This clears your saved Server URL from the device. The app will fall back to whatever the launcher script (run-app.sh) baked in via --dart-define on the next launch. Use this when the tunnel URL has changed and the saved value is stale.'**
  String get settingsResetDefaultsBody;

  /// No description provided for @settingsReset.
  ///
  /// In en, this message translates to:
  /// **'Reset'**
  String get settingsReset;

  /// No description provided for @settingsSignOutTitle.
  ///
  /// In en, this message translates to:
  /// **'Sign out?'**
  String get settingsSignOutTitle;

  /// No description provided for @settingsSignOutBody.
  ///
  /// In en, this message translates to:
  /// **'You\'ll need to sign in again to access your library and credits.'**
  String get settingsSignOutBody;

  /// No description provided for @settingsSignOut.
  ///
  /// In en, this message translates to:
  /// **'Sign out'**
  String get settingsSignOut;

  /// No description provided for @settingsSectionSubscription.
  ///
  /// In en, this message translates to:
  /// **'Subscription'**
  String get settingsSectionSubscription;

  /// No description provided for @settingsPlanCredits.
  ///
  /// In en, this message translates to:
  /// **'Plan & credits'**
  String get settingsPlanCredits;

  /// No description provided for @settingsPlanCreditsSubtitle.
  ///
  /// In en, this message translates to:
  /// **'View plans, manage your subscription'**
  String get settingsPlanCreditsSubtitle;

  /// No description provided for @settingsFreePlanSubtitle.
  ///
  /// In en, this message translates to:
  /// **'You are on the Free plan — subscribe to render videos'**
  String get settingsFreePlanSubtitle;

  /// No description provided for @settingsManagePlanSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Manage your {plan} plan'**
  String settingsManagePlanSubtitle(String plan);

  /// No description provided for @settingsSectionAdvanced.
  ///
  /// In en, this message translates to:
  /// **'Advanced'**
  String get settingsSectionAdvanced;

  /// No description provided for @settingsSectionAbout.
  ///
  /// In en, this message translates to:
  /// **'About'**
  String get settingsSectionAbout;

  /// No description provided for @settingsTestConnected.
  ///
  /// In en, this message translates to:
  /// **'✓ Connected'**
  String get settingsTestConnected;

  /// No description provided for @settingsTestFailed.
  ///
  /// In en, this message translates to:
  /// **'✗ {error}'**
  String settingsTestFailed(String error);

  /// No description provided for @settingsResetDone.
  ///
  /// In en, this message translates to:
  /// **'✓ Reset — using launcher defaults'**
  String get settingsResetDone;

  /// No description provided for @settingsNotSignedIn.
  ///
  /// In en, this message translates to:
  /// **'Not signed in'**
  String get settingsNotSignedIn;

  /// No description provided for @settingsFreePlan.
  ///
  /// In en, this message translates to:
  /// **'Free plan'**
  String get settingsFreePlan;

  /// No description provided for @settingsPlanName.
  ///
  /// In en, this message translates to:
  /// **'{plan} plan'**
  String settingsPlanName(String plan);

  /// No description provided for @settingsServerConnection.
  ///
  /// In en, this message translates to:
  /// **'Server connection'**
  String get settingsServerConnection;

  /// No description provided for @settingsServerConnectionSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Override the API URL — for self-hosters and debugging'**
  String get settingsServerConnectionSubtitle;

  /// No description provided for @settingsFirstTimeSetup.
  ///
  /// In en, this message translates to:
  /// **'First-time setup. Paste the API URL printed by run-app.sh, then tap Test → Save.'**
  String get settingsFirstTimeSetup;

  /// No description provided for @settingsServerUrlLabel.
  ///
  /// In en, this message translates to:
  /// **'Server URL'**
  String get settingsServerUrlLabel;

  /// No description provided for @settingsUrlRequired.
  ///
  /// In en, this message translates to:
  /// **'required'**
  String get settingsUrlRequired;

  /// No description provided for @settingsUrlMustStartWithHttp.
  ///
  /// In en, this message translates to:
  /// **'must start with http:// or https://'**
  String get settingsUrlMustStartWithHttp;

  /// No description provided for @settingsTest.
  ///
  /// In en, this message translates to:
  /// **'Test'**
  String get settingsTest;

  /// No description provided for @settingsResetToLauncherDefaults.
  ///
  /// In en, this message translates to:
  /// **'Reset to launcher defaults'**
  String get settingsResetToLauncherDefaults;

  /// No description provided for @settingsAboutApp.
  ///
  /// In en, this message translates to:
  /// **'App'**
  String get settingsAboutApp;

  /// No description provided for @settingsAboutVersion.
  ///
  /// In en, this message translates to:
  /// **'Version'**
  String get settingsAboutVersion;

  /// No description provided for @settingsAboutMadeFor.
  ///
  /// In en, this message translates to:
  /// **'Made for'**
  String get settingsAboutMadeFor;

  /// No description provided for @settingsAboutMadeForValue.
  ///
  /// In en, this message translates to:
  /// **'Arabic short-form storytelling'**
  String get settingsAboutMadeForValue;

  /// No description provided for @billingTitle.
  ///
  /// In en, this message translates to:
  /// **'Billing'**
  String get billingTitle;

  /// No description provided for @billingSubscriptions.
  ///
  /// In en, this message translates to:
  /// **'Subscriptions'**
  String get billingSubscriptions;

  /// No description provided for @billingPricePerMonth.
  ///
  /// In en, this message translates to:
  /// **'{price} / month'**
  String billingPricePerMonth(String price);

  /// No description provided for @billingManageSubscription.
  ///
  /// In en, this message translates to:
  /// **'Manage subscription (Stripe)'**
  String get billingManageSubscription;

  /// No description provided for @billingRecentTransactions.
  ///
  /// In en, this message translates to:
  /// **'Recent transactions'**
  String get billingRecentTransactions;

  /// No description provided for @billingNoTransactions.
  ///
  /// In en, this message translates to:
  /// **'No transactions yet.'**
  String get billingNoTransactions;

  /// No description provided for @billingBalance.
  ///
  /// In en, this message translates to:
  /// **'Balance'**
  String get billingBalance;

  /// No description provided for @billingPlanLabel.
  ///
  /// In en, this message translates to:
  /// **'Plan: {plan}'**
  String billingPlanLabel(String plan);

  /// No description provided for @billingPlanFree.
  ///
  /// In en, this message translates to:
  /// **'Free'**
  String get billingPlanFree;

  /// No description provided for @billingCancelsOn.
  ///
  /// In en, this message translates to:
  /// **'Cancels {date}'**
  String billingCancelsOn(String date);

  /// No description provided for @billingRenewsOn.
  ///
  /// In en, this message translates to:
  /// **'Renews {date}'**
  String billingRenewsOn(String date);

  /// No description provided for @billingCurrentPlanChip.
  ///
  /// In en, this message translates to:
  /// **'current'**
  String get billingCurrentPlanChip;

  /// No description provided for @billingSubscribe.
  ///
  /// In en, this message translates to:
  /// **'Subscribe'**
  String get billingSubscribe;

  /// No description provided for @transactionsTitle.
  ///
  /// In en, this message translates to:
  /// **'Transactions'**
  String get transactionsTitle;

  /// No description provided for @transactionsKindSongSpend.
  ///
  /// In en, this message translates to:
  /// **'Song spend'**
  String get transactionsKindSongSpend;

  /// No description provided for @transactionsKindRefund.
  ///
  /// In en, this message translates to:
  /// **'Refund'**
  String get transactionsKindRefund;

  /// No description provided for @transactionsKindAdminCredit.
  ///
  /// In en, this message translates to:
  /// **'Admin credit'**
  String get transactionsKindAdminCredit;

  /// No description provided for @transactionsKindWelcomeCredit.
  ///
  /// In en, this message translates to:
  /// **'Welcome credit'**
  String get transactionsKindWelcomeCredit;

  /// No description provided for @transactionsKindSubscription.
  ///
  /// In en, this message translates to:
  /// **'Subscription'**
  String get transactionsKindSubscription;

  /// No description provided for @transactionsKindTopup.
  ///
  /// In en, this message translates to:
  /// **'Top-up'**
  String get transactionsKindTopup;

  /// No description provided for @transactionsLoadFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed to load: {error}'**
  String transactionsLoadFailed(String error);

  /// No description provided for @transactionsEmpty.
  ///
  /// In en, this message translates to:
  /// **'No transactions yet.\nGenerate a song or buy credits to see activity here.'**
  String get transactionsEmpty;

  /// No description provided for @personasDeleteTitle.
  ///
  /// In en, this message translates to:
  /// **'Delete \"{name}\"?'**
  String personasDeleteTitle(String name);

  /// No description provided for @personasDeleteBody.
  ///
  /// In en, this message translates to:
  /// **'This removes the saved voice. Songs you already generated with it keep their audio — only future generations lose the lock to this voice.'**
  String get personasDeleteBody;

  /// No description provided for @personasRemoved.
  ///
  /// In en, this message translates to:
  /// **'\"{name}\" removed'**
  String personasRemoved(String name);

  /// No description provided for @personasLoadFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed to load voices: {error}'**
  String personasLoadFailed(String error);

  /// No description provided for @personasEmpty.
  ///
  /// In en, this message translates to:
  /// **'No saved voices yet.\n\nGenerate a song, then tap \"Save this voice\" on its detail screen to pin the singer for future songs.'**
  String get personasEmpty;

  /// No description provided for @personasFromSong.
  ///
  /// In en, this message translates to:
  /// **'From song {runId} · take {take}'**
  String personasFromSong(String runId, int take);

  /// No description provided for @personasDeleteTooltip.
  ///
  /// In en, this message translates to:
  /// **'Delete this voice'**
  String get personasDeleteTooltip;

  /// No description provided for @newRunTitle.
  ///
  /// In en, this message translates to:
  /// **'New Episode'**
  String get newRunTitle;

  /// No description provided for @newRunTabAiGenerate.
  ///
  /// In en, this message translates to:
  /// **'AI Generate'**
  String get newRunTabAiGenerate;

  /// No description provided for @newRunTabPasteScript.
  ///
  /// In en, this message translates to:
  /// **'Paste Script'**
  String get newRunTabPasteScript;

  /// No description provided for @newRunAiExplainer.
  ///
  /// In en, this message translates to:
  /// **'AI generates a script from your premise. Pick the dialect, art style, character template, and narration style; the writer follows your choices.'**
  String get newRunAiExplainer;

  /// No description provided for @newRunPremiseLabel.
  ///
  /// In en, this message translates to:
  /// **'Premise (Arabic)'**
  String get newRunPremiseLabel;

  /// No description provided for @newRunPremiseTooShort.
  ///
  /// In en, this message translates to:
  /// **'Premise too short'**
  String get newRunPremiseTooShort;

  /// No description provided for @newRunThemeLabel.
  ///
  /// In en, this message translates to:
  /// **'Theme'**
  String get newRunThemeLabel;

  /// No description provided for @newRunDialectLabel.
  ///
  /// In en, this message translates to:
  /// **'Dialect'**
  String get newRunDialectLabel;

  /// No description provided for @newRunArtStyleLabel.
  ///
  /// In en, this message translates to:
  /// **'Art style'**
  String get newRunArtStyleLabel;

  /// No description provided for @newRunCharacterTemplateLabel.
  ///
  /// In en, this message translates to:
  /// **'Character template'**
  String get newRunCharacterTemplateLabel;

  /// No description provided for @newRunEndingTypeLabel.
  ///
  /// In en, this message translates to:
  /// **'Ending type'**
  String get newRunEndingTypeLabel;

  /// No description provided for @newRunNarrationStyleLabel.
  ///
  /// In en, this message translates to:
  /// **'Narration style'**
  String get newRunNarrationStyleLabel;

  /// No description provided for @newRunDialectMsa.
  ///
  /// In en, this message translates to:
  /// **'MSA (الفصحى)'**
  String get newRunDialectMsa;

  /// No description provided for @newRunDialectSyrian.
  ///
  /// In en, this message translates to:
  /// **'Syrian / Levantine'**
  String get newRunDialectSyrian;

  /// No description provided for @newRunDialectEgyptian.
  ///
  /// In en, this message translates to:
  /// **'Egyptian'**
  String get newRunDialectEgyptian;

  /// No description provided for @newRunDialectKhaliji.
  ///
  /// In en, this message translates to:
  /// **'Khaliji / Gulf'**
  String get newRunDialectKhaliji;

  /// No description provided for @newRunDialectMaghrebi.
  ///
  /// In en, this message translates to:
  /// **'Maghrebi'**
  String get newRunDialectMaghrebi;

  /// No description provided for @newRunDialectIraqi.
  ///
  /// In en, this message translates to:
  /// **'Iraqi'**
  String get newRunDialectIraqi;

  /// No description provided for @newRunArtPixar3d.
  ///
  /// In en, this message translates to:
  /// **'3D Pixar'**
  String get newRunArtPixar3d;

  /// No description provided for @newRunArtAnime2d.
  ///
  /// In en, this message translates to:
  /// **'2D Anime'**
  String get newRunArtAnime2d;

  /// No description provided for @newRunArtCinematic.
  ///
  /// In en, this message translates to:
  /// **'Cinematic photo-real'**
  String get newRunArtCinematic;

  /// No description provided for @newRunArtClaymation.
  ///
  /// In en, this message translates to:
  /// **'Claymation'**
  String get newRunArtClaymation;

  /// No description provided for @newRunArtHandDrawn.
  ///
  /// In en, this message translates to:
  /// **'Hand-drawn'**
  String get newRunArtHandDrawn;

  /// No description provided for @newRunArtGhibli.
  ///
  /// In en, this message translates to:
  /// **'Studio Ghibli'**
  String get newRunArtGhibli;

  /// No description provided for @newRunAiChoose.
  ///
  /// In en, this message translates to:
  /// **'Let the AI choose'**
  String get newRunAiChoose;

  /// No description provided for @newRunCharHuman.
  ///
  /// In en, this message translates to:
  /// **'Human cast'**
  String get newRunCharHuman;

  /// No description provided for @newRunCharFruit.
  ///
  /// In en, this message translates to:
  /// **'Fruit cast (Sunstoriz)'**
  String get newRunCharFruit;

  /// No description provided for @newRunCharAnimal.
  ///
  /// In en, this message translates to:
  /// **'Animal cast'**
  String get newRunCharAnimal;

  /// No description provided for @newRunCharSurreal.
  ///
  /// In en, this message translates to:
  /// **'Surreal creatures'**
  String get newRunCharSurreal;

  /// No description provided for @newRunEndingOpen.
  ///
  /// In en, this message translates to:
  /// **'Open-ended'**
  String get newRunEndingOpen;

  /// No description provided for @newRunEndingClosedTragic.
  ///
  /// In en, this message translates to:
  /// **'Closed tragic'**
  String get newRunEndingClosedTragic;

  /// No description provided for @newRunEndingClosedHappy.
  ///
  /// In en, this message translates to:
  /// **'Closed happy'**
  String get newRunEndingClosedHappy;

  /// No description provided for @newRunEndingTwist.
  ///
  /// In en, this message translates to:
  /// **'Twist'**
  String get newRunEndingTwist;

  /// No description provided for @newRunNarrCinematic.
  ///
  /// In en, this message translates to:
  /// **'Cinematic (recommended)'**
  String get newRunNarrCinematic;

  /// No description provided for @newRunNarrFirstPerson.
  ///
  /// In en, this message translates to:
  /// **'First-person monologue (TikTok)'**
  String get newRunNarrFirstPerson;

  /// No description provided for @newRunBeatsLabel.
  ///
  /// In en, this message translates to:
  /// **'Beats:'**
  String get newRunBeatsLabel;

  /// No description provided for @newRunSecPerBeatLabel.
  ///
  /// In en, this message translates to:
  /// **'Sec / beat:'**
  String get newRunSecPerBeatLabel;

  /// No description provided for @newRunWriting.
  ///
  /// In en, this message translates to:
  /// **'Writing…'**
  String get newRunWriting;

  /// No description provided for @newRunGenerateScript.
  ///
  /// In en, this message translates to:
  /// **'Generate Script'**
  String get newRunGenerateScript;

  /// No description provided for @newRunPasteExplainer.
  ///
  /// In en, this message translates to:
  /// **'Your dialogue is used VERBATIM — no LLM rewrite. Use this for episode continuations where you want to control every line.'**
  String get newRunPasteExplainer;

  /// No description provided for @newRunPasteFromMarkdown.
  ///
  /// In en, this message translates to:
  /// **'Paste from Markdown Script'**
  String get newRunPasteFromMarkdown;

  /// No description provided for @newRunTitleLabel.
  ///
  /// In en, this message translates to:
  /// **'Title (Arabic)'**
  String get newRunTitleLabel;

  /// No description provided for @newRunTitleHint.
  ///
  /// In en, this message translates to:
  /// **'مثلاً: العقد المقدس - الحلقة 4'**
  String get newRunTitleHint;

  /// No description provided for @newRunStoryContextLabel.
  ///
  /// In en, this message translates to:
  /// **'Story context (optional, Arabic)'**
  String get newRunStoryContextLabel;

  /// No description provided for @newRunStoryContextHint.
  ///
  /// In en, this message translates to:
  /// **'الحلقة الرابعة من سلسلة العقد'**
  String get newRunStoryContextHint;

  /// No description provided for @newRunTitleRequired.
  ///
  /// In en, this message translates to:
  /// **'Title is required'**
  String get newRunTitleRequired;

  /// No description provided for @newRunBeatRequired.
  ///
  /// In en, this message translates to:
  /// **'At least one beat is required'**
  String get newRunBeatRequired;

  /// No description provided for @newRunVisualRequired.
  ///
  /// In en, this message translates to:
  /// **'Every beat needs a visual description (English)'**
  String get newRunVisualRequired;

  /// No description provided for @newRunParsedBeats.
  ///
  /// In en, this message translates to:
  /// **'Parsed {count} beats ({method})'**
  String newRunParsedBeats(int count, String method);

  /// No description provided for @newRunMethodRegex.
  ///
  /// In en, this message translates to:
  /// **'regex'**
  String get newRunMethodRegex;

  /// No description provided for @newRunMethodAiSplit.
  ///
  /// In en, this message translates to:
  /// **'AI split'**
  String get newRunMethodAiSplit;

  /// No description provided for @newRunMethodAuto.
  ///
  /// In en, this message translates to:
  /// **'auto-segmented'**
  String get newRunMethodAuto;

  /// No description provided for @newRunBadgeParsedMarkdown.
  ///
  /// In en, this message translates to:
  /// **'Parsed from your markdown'**
  String get newRunBadgeParsedMarkdown;

  /// No description provided for @newRunBadgeAiSplit.
  ///
  /// In en, this message translates to:
  /// **'Split by AI — review before saving'**
  String get newRunBadgeAiSplit;

  /// No description provided for @newRunBadgeAutoSegmented.
  ///
  /// In en, this message translates to:
  /// **'Auto-segmented — review carefully'**
  String get newRunBadgeAutoSegmented;

  /// No description provided for @newRunBeatsSection.
  ///
  /// In en, this message translates to:
  /// **'Beats'**
  String get newRunBeatsSection;

  /// No description provided for @newRunAddBeat.
  ///
  /// In en, this message translates to:
  /// **'Add Beat ({number})'**
  String newRunAddBeat(int number);

  /// No description provided for @newRunSaving.
  ///
  /// In en, this message translates to:
  /// **'Saving…'**
  String get newRunSaving;

  /// No description provided for @newRunUseScript.
  ///
  /// In en, this message translates to:
  /// **'Use This Script ({count} beats, ~{cost})'**
  String newRunUseScript(int count, String cost);

  /// No description provided for @newRunPasteDialogTitle.
  ///
  /// In en, this message translates to:
  /// **'Paste Markdown Script'**
  String get newRunPasteDialogTitle;

  /// No description provided for @newRunPasteFormatHelp.
  ///
  /// In en, this message translates to:
  /// **'Recognised format: **العنوان: ...** title, **المشهد N – ...** scene headings, and **SPEAKER:**\\n\"dialogue\" blocks. Stage directions in plain prose are kept as silent context. Your Arabic is preserved character-for-character.'**
  String get newRunPasteFormatHelp;

  /// No description provided for @newRunPasteHint.
  ///
  /// In en, this message translates to:
  /// **'**العنوان: القلادة المقدسة – الحلقة 4**\n\n**المشهد 1 – الفراغ**\nسكون مطلق...\n\n**الشاب (بهمس):**\n\"أنا… وين…؟\"\n\n...'**
  String get newRunPasteHint;

  /// No description provided for @newRunPasteRealScript.
  ///
  /// In en, this message translates to:
  /// **'Paste a real script (at least a few scenes).'**
  String get newRunPasteRealScript;

  /// No description provided for @newRunTargetBeats.
  ///
  /// In en, this message translates to:
  /// **'Target beats:'**
  String get newRunTargetBeats;

  /// No description provided for @newRunParsing.
  ///
  /// In en, this message translates to:
  /// **'Parsing…'**
  String get newRunParsing;

  /// No description provided for @newRunParseToBeats.
  ///
  /// In en, this message translates to:
  /// **'Parse to Beats'**
  String get newRunParseToBeats;

  /// No description provided for @newRunBeatBadge.
  ///
  /// In en, this message translates to:
  /// **'BEAT {number}'**
  String newRunBeatBadge(String number);

  /// No description provided for @newRunSpeakerLabel.
  ///
  /// In en, this message translates to:
  /// **'Speaker (free-text)'**
  String get newRunSpeakerLabel;

  /// No description provided for @newRunSpeakerHint.
  ///
  /// In en, this message translates to:
  /// **'e.g. mother, narrator, warrior, …'**
  String get newRunSpeakerHint;

  /// No description provided for @newRunCharacterNameLabel.
  ///
  /// In en, this message translates to:
  /// **'Character name (Arabic, optional)'**
  String get newRunCharacterNameLabel;

  /// No description provided for @newRunCharacterNameHint.
  ///
  /// In en, this message translates to:
  /// **'e.g. خالد، فاطمة، أم يوسف'**
  String get newRunCharacterNameHint;

  /// No description provided for @newRunArabicDialogueLabel.
  ///
  /// In en, this message translates to:
  /// **'Arabic dialogue (leave empty for silent action beat)'**
  String get newRunArabicDialogueLabel;

  /// No description provided for @newRunVisualDescLabel.
  ///
  /// In en, this message translates to:
  /// **'Visual description (English) — required'**
  String get newRunVisualDescLabel;

  /// No description provided for @newRunVisualDescHint.
  ///
  /// In en, this message translates to:
  /// **'e.g. Strawberry son in stone room, golden light, looking at necklace'**
  String get newRunVisualDescHint;

  /// No description provided for @newRunClipDurationLabel.
  ///
  /// In en, this message translates to:
  /// **'Clip duration:'**
  String get newRunClipDurationLabel;

  /// No description provided for @runDetailStoryFallback.
  ///
  /// In en, this message translates to:
  /// **'Story'**
  String get runDetailStoryFallback;

  /// No description provided for @runDetailActivityLog.
  ///
  /// In en, this message translates to:
  /// **'Activity log'**
  String get runDetailActivityLog;

  /// No description provided for @runDetailApprovedPreparing.
  ///
  /// In en, this message translates to:
  /// **'Approved — preparing characters (~30s)…'**
  String get runDetailApprovedPreparing;

  /// No description provided for @runDetailApprovedGenerating.
  ///
  /// In en, this message translates to:
  /// **'Approved — generating clips…'**
  String get runDetailApprovedGenerating;

  /// No description provided for @runDetailApproveFailed.
  ///
  /// In en, this message translates to:
  /// **'Approve failed: {error}'**
  String runDetailApproveFailed(String error);

  /// No description provided for @runDetailRegenLookTitle.
  ///
  /// In en, this message translates to:
  /// **'Regenerate character look?'**
  String get runDetailRegenLookTitle;

  /// No description provided for @runDetailRegenLookBody.
  ///
  /// In en, this message translates to:
  /// **'This discards the current character look and generates a new one. Your credit balance is not affected.'**
  String get runDetailRegenLookBody;

  /// No description provided for @runDetailKeep.
  ///
  /// In en, this message translates to:
  /// **'Keep'**
  String get runDetailKeep;

  /// No description provided for @runDetailRerollFailed.
  ///
  /// In en, this message translates to:
  /// **'Reroll failed: {error}'**
  String runDetailRerollFailed(String error);

  /// No description provided for @runDetailRepairing.
  ///
  /// In en, this message translates to:
  /// **'Repairing video — re-muxing for browser playback…'**
  String get runDetailRepairing;

  /// No description provided for @runDetailRepaired.
  ///
  /// In en, this message translates to:
  /// **'Repaired. Tap Play again.'**
  String get runDetailRepaired;

  /// No description provided for @runDetailRepairFailed.
  ///
  /// In en, this message translates to:
  /// **'Repair failed: {error}'**
  String runDetailRepairFailed(String error);

  /// No description provided for @runDetailResuming.
  ///
  /// In en, this message translates to:
  /// **'Resuming pipeline…'**
  String get runDetailResuming;

  /// No description provided for @runDetailResumeFailed.
  ///
  /// In en, this message translates to:
  /// **'Resume failed: {error}'**
  String runDetailResumeFailed(String error);

  /// No description provided for @runDetailDiscardTitle.
  ///
  /// In en, this message translates to:
  /// **'Discard this run?'**
  String get runDetailDiscardTitle;

  /// No description provided for @runDetailDiscardBody.
  ///
  /// In en, this message translates to:
  /// **'Cancelling will stop any running pipeline AND delete the run entirely. The script and any partially-generated artifacts will be removed. This cannot be undone.'**
  String get runDetailDiscardBody;

  /// No description provided for @runDetailRunDiscarded.
  ///
  /// In en, this message translates to:
  /// **'Run discarded'**
  String get runDetailRunDiscarded;

  /// No description provided for @runDetailDiscardFailed.
  ///
  /// In en, this message translates to:
  /// **'Discard failed: {error}'**
  String runDetailDiscardFailed(String error);

  /// No description provided for @runDetailNoScriptToReroll.
  ///
  /// In en, this message translates to:
  /// **'No script — nothing to reroll'**
  String get runDetailNoScriptToReroll;

  /// No description provided for @runDetailRerollingClips.
  ///
  /// In en, this message translates to:
  /// **'{count, plural, =1{Rerolling 1 clip — 1 credit} other{Rerolling {count} clips — {count} credits}}'**
  String runDetailRerollingClips(int count);

  /// No description provided for @runDetailRerollClipTitle.
  ///
  /// In en, this message translates to:
  /// **'Reroll clip {number}?'**
  String runDetailRerollClipTitle(String number);

  /// No description provided for @runDetailRerollClipBody.
  ///
  /// In en, this message translates to:
  /// **'This regenerates one clip and costs 1 credit.'**
  String get runDetailRerollClipBody;

  /// No description provided for @runDetailRerollOneCredit.
  ///
  /// In en, this message translates to:
  /// **'Reroll (1 credit)'**
  String get runDetailRerollOneCredit;

  /// No description provided for @runDetailRerollingClip.
  ///
  /// In en, this message translates to:
  /// **'Rerolling clip {number} — 1 credit'**
  String runDetailRerollingClip(String number);

  /// No description provided for @runDetailStatusReady.
  ///
  /// In en, this message translates to:
  /// **'Ready to watch'**
  String get runDetailStatusReady;

  /// No description provided for @runDetailStatusScriptReady.
  ///
  /// In en, this message translates to:
  /// **'Script ready — approve to generate the video'**
  String get runDetailStatusScriptReady;

  /// No description provided for @runDetailStatusCharacterReady.
  ///
  /// In en, this message translates to:
  /// **'Character look ready — approve to generate clips'**
  String get runDetailStatusCharacterReady;

  /// No description provided for @runDetailStatusGenerating.
  ///
  /// In en, this message translates to:
  /// **'Generating your video…'**
  String get runDetailStatusGenerating;

  /// No description provided for @runDetailStatusWriting.
  ///
  /// In en, this message translates to:
  /// **'Writing the script…'**
  String get runDetailStatusWriting;

  /// No description provided for @runDetailStatusFailed.
  ///
  /// In en, this message translates to:
  /// **'Generation failed — tap Resume to retry'**
  String get runDetailStatusFailed;

  /// No description provided for @runDetailRepairPlayback.
  ///
  /// In en, this message translates to:
  /// **'Repair playback'**
  String get runDetailRepairPlayback;

  /// No description provided for @runDetailRerollSelectedClips.
  ///
  /// In en, this message translates to:
  /// **'Reroll selected clips'**
  String get runDetailRerollSelectedClips;

  /// No description provided for @runDetailGenerationFailed.
  ///
  /// In en, this message translates to:
  /// **'Generation failed'**
  String get runDetailGenerationFailed;

  /// No description provided for @runDetailResume.
  ///
  /// In en, this message translates to:
  /// **'Resume'**
  String get runDetailResume;

  /// No description provided for @runDetailCancelDiscard.
  ///
  /// In en, this message translates to:
  /// **'Cancel & Discard'**
  String get runDetailCancelDiscard;

  /// No description provided for @runDetailCreditsCount.
  ///
  /// In en, this message translates to:
  /// **'{count, plural, =1{1 credit} other{{count} credits}}'**
  String runDetailCreditsCount(int count);

  /// No description provided for @runDetailScriptBeats.
  ///
  /// In en, this message translates to:
  /// **'{count, plural, =1{Script (1 beat)} other{Script ({count} beats)}}'**
  String runDetailScriptBeats(int count);

  /// No description provided for @runDetailDownloadScriptPdf.
  ///
  /// In en, this message translates to:
  /// **'Download script (PDF)'**
  String get runDetailDownloadScriptPdf;

  /// No description provided for @runDetailRerollClipTooltip.
  ///
  /// In en, this message translates to:
  /// **'Reroll this clip (1 credit)'**
  String get runDetailRerollClipTooltip;

  /// No description provided for @runDetailSilentBeat.
  ///
  /// In en, this message translates to:
  /// **'(silent action beat — no dialogue)'**
  String get runDetailSilentBeat;

  /// No description provided for @runDetailStartingGeneration.
  ///
  /// In en, this message translates to:
  /// **'Starting video generation — clips appear shortly…'**
  String get runDetailStartingGeneration;

  /// No description provided for @runDetailApprovingPreparing.
  ///
  /// In en, this message translates to:
  /// **'Approving — preparing characters (~30s)…'**
  String get runDetailApprovingPreparing;

  /// No description provided for @runDetailApproveVeoLine.
  ///
  /// In en, this message translates to:
  /// **'{count, plural, =1{Approve to generate the video — 1 credit} other{Approve to generate the video — {count} credits}}'**
  String runDetailApproveVeoLine(int count);

  /// No description provided for @runDetailApproveLine.
  ///
  /// In en, this message translates to:
  /// **'{count, plural, =1{Approve to start generation — 1 credit total} other{Approve to start generation — {count} credits total}}'**
  String runDetailApproveLine(int count);

  /// No description provided for @runDetailVeoGateHint.
  ///
  /// In en, this message translates to:
  /// **'Once started, clips render one by one (~1 min each).'**
  String get runDetailVeoGateHint;

  /// No description provided for @runDetailApproveHint.
  ///
  /// In en, this message translates to:
  /// **'Characters are prepared first; the video starts once you confirm again.'**
  String get runDetailApproveHint;

  /// No description provided for @runDetailApprove.
  ///
  /// In en, this message translates to:
  /// **'Approve'**
  String get runDetailApprove;

  /// No description provided for @runDetailStagePreparingCharacters.
  ///
  /// In en, this message translates to:
  /// **'Preparing characters…'**
  String get runDetailStagePreparingCharacters;

  /// No description provided for @runDetailStageGeneratingClip.
  ///
  /// In en, this message translates to:
  /// **'Generating clip {current} of {total}…'**
  String runDetailStageGeneratingClip(int current, int total);

  /// No description provided for @runDetailStageAligningCaptions.
  ///
  /// In en, this message translates to:
  /// **'Aligning captions…'**
  String get runDetailStageAligningCaptions;

  /// No description provided for @runDetailStageAssembling.
  ///
  /// In en, this message translates to:
  /// **'Assembling final video…'**
  String get runDetailStageAssembling;

  /// No description provided for @runDetailClipsDone.
  ///
  /// In en, this message translates to:
  /// **'{done} / {total} clips done'**
  String runDetailClipsDone(int done, int total);

  /// No description provided for @runDetailCharacterLook.
  ///
  /// In en, this message translates to:
  /// **'CHARACTER LOOK'**
  String get runDetailCharacterLook;

  /// No description provided for @runDetailDontLikeRegenerate.
  ///
  /// In en, this message translates to:
  /// **'Don\'t like it? Regenerate'**
  String get runDetailDontLikeRegenerate;

  /// No description provided for @runDetailRerollWhichTitle.
  ///
  /// In en, this message translates to:
  /// **'Reroll which clips?'**
  String get runDetailRerollWhichTitle;

  /// No description provided for @runDetailRerollWhichBody.
  ///
  /// In en, this message translates to:
  /// **'Pick the clips that need regenerating. Each costs 1 credit. The other clips stay; the final video re-stitches at the end.'**
  String get runDetailRerollWhichBody;

  /// No description provided for @runDetailNoClipsSelected.
  ///
  /// In en, this message translates to:
  /// **'No clips selected'**
  String get runDetailNoClipsSelected;

  /// No description provided for @runDetailSelectedClipsCredits.
  ///
  /// In en, this message translates to:
  /// **'{count, plural, =1{1 clip — 1 credit} other{{count} clips — {count} credits}}'**
  String runDetailSelectedClipsCredits(int count);

  /// No description provided for @editScriptTitle.
  ///
  /// In en, this message translates to:
  /// **'Edit Script'**
  String get editScriptTitle;

  /// No description provided for @editScriptTitleLabel.
  ///
  /// In en, this message translates to:
  /// **'Title'**
  String get editScriptTitleLabel;

  /// No description provided for @editScriptArabicDialogueLabel.
  ///
  /// In en, this message translates to:
  /// **'Arabic dialogue (leave empty for silent beat)'**
  String get editScriptArabicDialogueLabel;

  /// No description provided for @editScriptVisualDescLabel.
  ///
  /// In en, this message translates to:
  /// **'Visual description (English)'**
  String get editScriptVisualDescLabel;

  /// No description provided for @costTitle.
  ///
  /// In en, this message translates to:
  /// **'Spend'**
  String get costTitle;

  /// No description provided for @costSortByDate.
  ///
  /// In en, this message translates to:
  /// **'Sort by date'**
  String get costSortByDate;

  /// No description provided for @costSortByAmount.
  ///
  /// In en, this message translates to:
  /// **'Sort by amount'**
  String get costSortByAmount;

  /// No description provided for @costByAmount.
  ///
  /// In en, this message translates to:
  /// **'BY AMOUNT'**
  String get costByAmount;

  /// No description provided for @costByDate.
  ///
  /// In en, this message translates to:
  /// **'BY DATE (newest first)'**
  String get costByDate;

  /// No description provided for @costTotalKieSpend.
  ///
  /// In en, this message translates to:
  /// **'TOTAL KIE.AI SPEND'**
  String get costTotalKieSpend;

  /// No description provided for @costRunsLabel.
  ///
  /// In en, this message translates to:
  /// **'RUNS'**
  String get costRunsLabel;

  /// No description provided for @costAvgPerRun.
  ///
  /// In en, this message translates to:
  /// **'AVG / RUN'**
  String get costAvgPerRun;

  /// No description provided for @costPercentOfTotal.
  ///
  /// In en, this message translates to:
  /// **'{percent} % of total'**
  String costPercentOfTotal(String percent);

  /// No description provided for @costFootnote.
  ///
  /// In en, this message translates to:
  /// **'Counts Veo (\$0.10/sec) + Flux character sheet (\$0.05/run). Doesn\'t include ElevenLabs (~\$0.30/episode if used) or Anthropic / Groq script generation (<\$0.05/episode).'**
  String get costFootnote;

  /// No description provided for @videoPlayerClipTitle.
  ///
  /// In en, this message translates to:
  /// **'Clip {number}'**
  String videoPlayerClipTitle(String number);

  /// No description provided for @videoPlayerUrlCopied.
  ///
  /// In en, this message translates to:
  /// **'Video URL copied — paste anywhere'**
  String get videoPlayerUrlCopied;

  /// No description provided for @videoPlayerOpenLinkToDownload.
  ///
  /// In en, this message translates to:
  /// **'Open the link in a new tab to download'**
  String get videoPlayerOpenLinkToDownload;

  /// No description provided for @videoPlayerPlaybackError.
  ///
  /// In en, this message translates to:
  /// **'playback error'**
  String get videoPlayerPlaybackError;

  /// No description provided for @videoPlayerCantRepairBody.
  ///
  /// In en, this message translates to:
  /// **'This video can\'t be repaired.\n\nThe mp4 file is corrupt at a level we can\'t fix without re-rendering. Use the Reroll button on the run page to regenerate the affected clips.'**
  String get videoPlayerCantRepairBody;

  /// No description provided for @videoPlayerBackToRun.
  ///
  /// In en, this message translates to:
  /// **'Back to run'**
  String get videoPlayerBackToRun;

  /// No description provided for @videoPlayerRepairing.
  ///
  /// In en, this message translates to:
  /// **'Repairing playback…'**
  String get videoPlayerRepairing;

  /// No description provided for @logViewerTitle.
  ///
  /// In en, this message translates to:
  /// **'Log — {runId}'**
  String logViewerTitle(String runId);

  /// No description provided for @logViewerCopyTooltip.
  ///
  /// In en, this message translates to:
  /// **'Copy log'**
  String get logViewerCopyTooltip;

  /// No description provided for @logViewerCopied.
  ///
  /// In en, this message translates to:
  /// **'Log copied'**
  String get logViewerCopied;

  /// No description provided for @logViewerEmpty.
  ///
  /// In en, this message translates to:
  /// **'(empty)'**
  String get logViewerEmpty;

  /// No description provided for @paywallOutOfCredits.
  ///
  /// In en, this message translates to:
  /// **'Out of credits'**
  String get paywallOutOfCredits;

  /// No description provided for @paywallNeedCredits.
  ///
  /// In en, this message translates to:
  /// **'This video needs {needed} credits. You have {balance} — {missing} more to go. Top up to keep generating.'**
  String paywallNeedCredits(int needed, int balance, int missing);

  /// No description provided for @paywallSavedNotice.
  ///
  /// In en, this message translates to:
  /// **'Your script and characters are saved. After topping up, tap Resume on this run to continue.'**
  String get paywallSavedNotice;

  /// No description provided for @paywallTopUp.
  ///
  /// In en, this message translates to:
  /// **'Top up'**
  String get paywallTopUp;

  /// No description provided for @misconfiguredTitle.
  ///
  /// In en, this message translates to:
  /// **'Backend not configured.'**
  String get misconfiguredTitle;

  /// No description provided for @misconfiguredBody.
  ///
  /// In en, this message translates to:
  /// **'Restart via scripts/run-app.sh so the Supabase + API URLs are baked into the build.'**
  String get misconfiguredBody;

  /// No description provided for @artistsSectionTitle.
  ///
  /// In en, this message translates to:
  /// **'Artists'**
  String get artistsSectionTitle;

  /// No description provided for @artistNewTile.
  ///
  /// In en, this message translates to:
  /// **'New'**
  String get artistNewTile;

  /// No description provided for @artistEditTitleCreate.
  ///
  /// In en, this message translates to:
  /// **'New artist'**
  String get artistEditTitleCreate;

  /// No description provided for @artistEditTitleEdit.
  ///
  /// In en, this message translates to:
  /// **'Edit artist'**
  String get artistEditTitleEdit;

  /// No description provided for @artistNameLabel.
  ///
  /// In en, this message translates to:
  /// **'Name'**
  String get artistNameLabel;

  /// No description provided for @artistNameRequired.
  ///
  /// In en, this message translates to:
  /// **'Name is required'**
  String get artistNameRequired;

  /// No description provided for @artistHandleLabel.
  ///
  /// In en, this message translates to:
  /// **'Handle'**
  String get artistHandleLabel;

  /// No description provided for @artistHandleHelper.
  ///
  /// In en, this message translates to:
  /// **'Optional — leave empty and one is generated from the name'**
  String get artistHandleHelper;

  /// No description provided for @artistBioLabel.
  ///
  /// In en, this message translates to:
  /// **'Bio'**
  String get artistBioLabel;

  /// No description provided for @artistDefaultStyleLabel.
  ///
  /// In en, this message translates to:
  /// **'Default style'**
  String get artistDefaultStyleLabel;

  /// No description provided for @artistVocalLabel.
  ///
  /// In en, this message translates to:
  /// **'Default voice'**
  String get artistVocalLabel;

  /// No description provided for @artistChooseAvatar.
  ///
  /// In en, this message translates to:
  /// **'Choose avatar image'**
  String get artistChooseAvatar;

  /// No description provided for @artistAvatarSelected.
  ///
  /// In en, this message translates to:
  /// **'New avatar selected — it uploads when you save'**
  String get artistAvatarSelected;

  /// No description provided for @artistAvatarUploadFailed.
  ///
  /// In en, this message translates to:
  /// **'Avatar upload failed: {error}'**
  String artistAvatarUploadFailed(String error);

  /// No description provided for @artistCreateButton.
  ///
  /// In en, this message translates to:
  /// **'Create artist'**
  String get artistCreateButton;

  /// No description provided for @artistSaveButton.
  ///
  /// In en, this message translates to:
  /// **'Save changes'**
  String get artistSaveButton;

  /// No description provided for @artistDeleteButton.
  ///
  /// In en, this message translates to:
  /// **'Delete artist'**
  String get artistDeleteButton;

  /// No description provided for @artistDeleteConfirmTitle.
  ///
  /// In en, this message translates to:
  /// **'Delete artist?'**
  String get artistDeleteConfirmTitle;

  /// No description provided for @artistDeleteConfirmBody.
  ///
  /// In en, this message translates to:
  /// **'Songs stay playable but leave this discography. The saved voice is kept.'**
  String get artistDeleteConfirmBody;

  /// No description provided for @artistDeleteFailed.
  ///
  /// In en, this message translates to:
  /// **'Delete failed: {error}'**
  String artistDeleteFailed(String error);

  /// No description provided for @artistSongCount.
  ///
  /// In en, this message translates to:
  /// **'{count, plural, =0{No songs yet} =1{1 song} other{{count} songs}}'**
  String artistSongCount(int count);

  /// No description provided for @artistShare.
  ///
  /// In en, this message translates to:
  /// **'Share'**
  String get artistShare;

  /// No description provided for @artistLinkCopied.
  ///
  /// In en, this message translates to:
  /// **'Artist link copied'**
  String get artistLinkCopied;

  /// No description provided for @artistEdit.
  ///
  /// In en, this message translates to:
  /// **'Edit'**
  String get artistEdit;

  /// No description provided for @artistNewSongCta.
  ///
  /// In en, this message translates to:
  /// **'New song as {name}'**
  String artistNewSongCta(String name);

  /// No description provided for @artistDiscographyTitle.
  ///
  /// In en, this message translates to:
  /// **'Discography'**
  String get artistDiscographyTitle;

  /// No description provided for @artistNoSongsYet.
  ///
  /// In en, this message translates to:
  /// **'No songs yet — release the first one as {name}.'**
  String artistNoSongsYet(String name);

  /// No description provided for @artistPickerLabel.
  ///
  /// In en, this message translates to:
  /// **'Sing as artist'**
  String get artistPickerLabel;

  /// No description provided for @artistPickerNone.
  ///
  /// In en, this message translates to:
  /// **'None'**
  String get artistPickerNone;

  /// No description provided for @artistMakeFromSongButton.
  ///
  /// In en, this message translates to:
  /// **'Make this singer an artist'**
  String get artistMakeFromSongButton;

  /// No description provided for @artistMakeFromSongBody.
  ///
  /// In en, this message translates to:
  /// **'Saves this song\'s voice and creates an artist around it. This song joins the discography, and new songs can be made as this artist.'**
  String get artistMakeFromSongBody;

  /// No description provided for @artistCreatedSnack.
  ///
  /// In en, this message translates to:
  /// **'Artist \"{name}\" created'**
  String artistCreatedSnack(String name);

  /// No description provided for @artistCreateFailed.
  ///
  /// In en, this message translates to:
  /// **'Couldn\'t create artist: {error}'**
  String artistCreateFailed(String error);

  /// No description provided for @releaseButton.
  ///
  /// In en, this message translates to:
  /// **'Release to stores'**
  String get releaseButton;

  /// No description provided for @releaseButtonReleased.
  ///
  /// In en, this message translates to:
  /// **'Released ✓'**
  String get releaseButtonReleased;

  /// No description provided for @releaseDialogTitle.
  ///
  /// In en, this message translates to:
  /// **'Release to stores'**
  String get releaseDialogTitle;

  /// No description provided for @releaseDialogExplainer.
  ///
  /// In en, this message translates to:
  /// **'Everything a distributor needs — audio, artwork, metadata, and lyrics — packed into one zip. Follow the steps below to get this song on Spotify, Apple Music, and more.'**
  String get releaseDialogExplainer;

  /// No description provided for @releaseArtistHint.
  ///
  /// In en, this message translates to:
  /// **'Tip: assign an artist first for consistent branding.'**
  String get releaseArtistHint;

  /// No description provided for @releaseStep1.
  ///
  /// In en, this message translates to:
  /// **'Download the release package.'**
  String get releaseStep1;

  /// No description provided for @releaseStep2.
  ///
  /// In en, this message translates to:
  /// **'Unzip it.'**
  String get releaseStep2;

  /// No description provided for @releaseStep3.
  ///
  /// In en, this message translates to:
  /// **'Create a DistroKid (or any distributor) account.'**
  String get releaseStep3;

  /// No description provided for @releaseStep4.
  ///
  /// In en, this message translates to:
  /// **'Tap \"Upload\" and choose audio.mp3.'**
  String get releaseStep4;

  /// No description provided for @releaseStep5.
  ///
  /// In en, this message translates to:
  /// **'Use cover.jpg as the artwork.'**
  String get releaseStep5;

  /// No description provided for @releaseStep6.
  ///
  /// In en, this message translates to:
  /// **'Copy the title, artist, genre, and language from metadata.txt.'**
  String get releaseStep6;

  /// No description provided for @releaseStep7.
  ///
  /// In en, this message translates to:
  /// **'Paste lyrics.txt when asked for the lyrics.'**
  String get releaseStep7;

  /// No description provided for @releaseStep8.
  ///
  /// In en, this message translates to:
  /// **'Submit — stores go live in 1–7 days, then return here and tap \"Mark as released\".'**
  String get releaseStep8;

  /// No description provided for @releaseDownloadPackage.
  ///
  /// In en, this message translates to:
  /// **'Download package'**
  String get releaseDownloadPackage;

  /// No description provided for @releaseMarkAsReleased.
  ///
  /// In en, this message translates to:
  /// **'Mark as released'**
  String get releaseMarkAsReleased;

  /// No description provided for @releaseMarkedSnack.
  ///
  /// In en, this message translates to:
  /// **'Marked as released'**
  String get releaseMarkedSnack;

  /// No description provided for @releaseUnmarkedSnack.
  ///
  /// In en, this message translates to:
  /// **'Release mark removed'**
  String get releaseUnmarkedSnack;

  /// No description provided for @releaseMarkFailed.
  ///
  /// In en, this message translates to:
  /// **'Couldn\'t update release status: {error}'**
  String releaseMarkFailed(String error);

  /// No description provided for @releaseBadge.
  ///
  /// In en, this message translates to:
  /// **'Released'**
  String get releaseBadge;

  /// No description provided for @ytSettingsTitle.
  ///
  /// In en, this message translates to:
  /// **'YouTube'**
  String get ytSettingsTitle;

  /// No description provided for @ytSettingsSubtitleDisconnected.
  ///
  /// In en, this message translates to:
  /// **'Publish songs to your channel'**
  String get ytSettingsSubtitleDisconnected;

  /// No description provided for @ytSettingsConnected.
  ///
  /// In en, this message translates to:
  /// **'Connected: {channel}'**
  String ytSettingsConnected(String channel);

  /// No description provided for @ytConnect.
  ///
  /// In en, this message translates to:
  /// **'Connect'**
  String get ytConnect;

  /// No description provided for @ytDisconnect.
  ///
  /// In en, this message translates to:
  /// **'Disconnect'**
  String get ytDisconnect;

  /// No description provided for @ytDisconnectConfirmTitle.
  ///
  /// In en, this message translates to:
  /// **'Disconnect YouTube?'**
  String get ytDisconnectConfirmTitle;

  /// No description provided for @ytDisconnectConfirmBody.
  ///
  /// In en, this message translates to:
  /// **'Publishing from the app stops until you connect again. Videos already on YouTube are not affected.'**
  String get ytDisconnectConfirmBody;

  /// No description provided for @ytDisconnectedSnack.
  ///
  /// In en, this message translates to:
  /// **'YouTube disconnected'**
  String get ytDisconnectedSnack;

  /// No description provided for @ytDisconnectFailed.
  ///
  /// In en, this message translates to:
  /// **'Couldn\'t disconnect: {error}'**
  String ytDisconnectFailed(String error);

  /// No description provided for @ytFinishInBrowser.
  ///
  /// In en, this message translates to:
  /// **'Finish connecting in the browser, then pull to refresh.'**
  String get ytFinishInBrowser;

  /// No description provided for @ytConnectFailed.
  ///
  /// In en, this message translates to:
  /// **'Couldn\'t start YouTube connect: {error}'**
  String ytConnectFailed(String error);

  /// No description provided for @ytPublishButton.
  ///
  /// In en, this message translates to:
  /// **'Publish to YouTube'**
  String get ytPublishButton;

  /// No description provided for @ytOnYoutubeButton.
  ///
  /// In en, this message translates to:
  /// **'On YouTube'**
  String get ytOnYoutubeButton;

  /// No description provided for @ytPublishDialogTitle.
  ///
  /// In en, this message translates to:
  /// **'Publish to YouTube'**
  String get ytPublishDialogTitle;

  /// No description provided for @ytPublishPreauditNote.
  ///
  /// In en, this message translates to:
  /// **'The upload starts as private until Google approves the app — make it public from YouTube Studio.'**
  String get ytPublishPreauditNote;

  /// No description provided for @ytPublish.
  ///
  /// In en, this message translates to:
  /// **'Publish'**
  String get ytPublish;

  /// No description provided for @ytPublishedSnack.
  ///
  /// In en, this message translates to:
  /// **'Published to YouTube'**
  String get ytPublishedSnack;

  /// No description provided for @ytPublishFailed.
  ///
  /// In en, this message translates to:
  /// **'Publish failed: {error}'**
  String ytPublishFailed(String error);

  /// No description provided for @ytNotConnectedSnack.
  ///
  /// In en, this message translates to:
  /// **'YouTube isn\'t connected — connect it from Settings first.'**
  String get ytNotConnectedSnack;

  /// No description provided for @ytBadge.
  ///
  /// In en, this message translates to:
  /// **'YouTube'**
  String get ytBadge;

  /// No description provided for @ytAutoPublishLabel.
  ///
  /// In en, this message translates to:
  /// **'Auto-publish new songs to YouTube'**
  String get ytAutoPublishLabel;

  /// No description provided for @ytAutoPublishSubtitle.
  ///
  /// In en, this message translates to:
  /// **'When a song finishes, it\'s uploaded to your channel automatically.'**
  String get ytAutoPublishSubtitle;

  /// No description provided for @ytAutoPublishSaveFailed.
  ///
  /// In en, this message translates to:
  /// **'Couldn\'t save the YouTube auto-publish setting: {error}'**
  String ytAutoPublishSaveFailed(String error);

  /// No description provided for @newSongFaithfulness.
  ///
  /// In en, this message translates to:
  /// **'Faithfulness to the original'**
  String get newSongFaithfulness;

  /// No description provided for @newSongFaithfulnessHigh.
  ///
  /// In en, this message translates to:
  /// **'High — the cover closely follows the original\'s melody and feel.'**
  String get newSongFaithfulnessHigh;

  /// No description provided for @newSongFaithfulnessLow.
  ///
  /// In en, this message translates to:
  /// **'Low — more creative freedom, further from the original.'**
  String get newSongFaithfulnessLow;

  /// No description provided for @llmDegradedBanner.
  ///
  /// In en, this message translates to:
  /// **'Lyric quality reduced — the primary writing model is unavailable (check Anthropic credits).'**
  String get llmDegradedBanner;

  /// No description provided for @trendSectionTitle.
  ///
  /// In en, this message translates to:
  /// **'Trending now'**
  String get trendSectionTitle;

  /// No description provided for @trendRefreshTooltip.
  ///
  /// In en, this message translates to:
  /// **'New ideas'**
  String get trendRefreshTooltip;

  /// No description provided for @trendCreateButton.
  ///
  /// In en, this message translates to:
  /// **'Create'**
  String get trendCreateButton;

  /// No description provided for @trendGenerating.
  ///
  /// In en, this message translates to:
  /// **'Reading today\'s trends…'**
  String get trendGenerating;

  /// No description provided for @draftMorningLabel.
  ///
  /// In en, this message translates to:
  /// **'Morning drafts'**
  String get draftMorningLabel;

  /// No description provided for @draftMorningSubtitle.
  ///
  /// In en, this message translates to:
  /// **'A free draft every morning from the day\'s trends — you only pay when you approve.'**
  String get draftMorningSubtitle;

  /// No description provided for @draftSectionTitle.
  ///
  /// In en, this message translates to:
  /// **'Morning drafts'**
  String get draftSectionTitle;

  /// No description provided for @draftReviewButton.
  ///
  /// In en, this message translates to:
  /// **'Review'**
  String get draftReviewButton;

  /// No description provided for @qualityEditStyle.
  ///
  /// In en, this message translates to:
  /// **'Edit style'**
  String get qualityEditStyle;

  /// No description provided for @qualityDiacritize.
  ///
  /// In en, this message translates to:
  /// **'Add diacritics'**
  String get qualityDiacritize;

  /// No description provided for @qualityDiacritizeDone.
  ///
  /// In en, this message translates to:
  /// **'Diacritics added to the lyrics'**
  String get qualityDiacritizeDone;

  /// No description provided for @qualityDiacritizeFailed.
  ///
  /// In en, this message translates to:
  /// **'Couldn\'t add diacritics: {error}'**
  String qualityDiacritizeFailed(String error);

  /// No description provided for @qualityDialectLabel.
  ///
  /// In en, this message translates to:
  /// **'Dialect'**
  String get qualityDialectLabel;

  /// No description provided for @qualityDialectAuto.
  ///
  /// In en, this message translates to:
  /// **'Auto'**
  String get qualityDialectAuto;

  /// No description provided for @qualityDialectMsa.
  ///
  /// In en, this message translates to:
  /// **'Modern Standard Arabic'**
  String get qualityDialectMsa;

  /// No description provided for @qualityDialectEgyptian.
  ///
  /// In en, this message translates to:
  /// **'Egyptian'**
  String get qualityDialectEgyptian;

  /// No description provided for @qualityDialectKhaleeji.
  ///
  /// In en, this message translates to:
  /// **'Khaleeji (Gulf)'**
  String get qualityDialectKhaleeji;

  /// No description provided for @qualityDialectLevantine.
  ///
  /// In en, this message translates to:
  /// **'Levantine'**
  String get qualityDialectLevantine;

  /// No description provided for @qualityDialectIraqi.
  ///
  /// In en, this message translates to:
  /// **'Iraqi'**
  String get qualityDialectIraqi;
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
