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
