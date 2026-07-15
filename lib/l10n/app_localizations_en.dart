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

  @override
  String get newSongTitle => 'New song';

  @override
  String get newSongModeTheme => 'Write a theme';

  @override
  String get newSongModeUpload => 'Upload a song';

  @override
  String get newSongUploadExplainer =>
      'Upload a song and the AI makes a faithful cover — it keeps the melody and words, performed by a new voice. The voice will differ from the original. Review and edit the words before any credit is spent.';

  @override
  String get newSongThemeExplainer =>
      'The AI will write lyrics and a cover image prompt. You can review and edit both before any credit is spent.';

  @override
  String get newSongFileReadError => 'Couldn\'t read that file — try another.';

  @override
  String newSongFilePickerError(String error) {
    return 'Could not open the file picker: $error';
  }

  @override
  String get newSongChooseAudioError => 'Choose an audio file to cover';

  @override
  String get newSongThemeRequired => 'Theme is required';

  @override
  String get newSongChooseAudioFile => 'Choose audio file (mp3, m4a, wav…)';

  @override
  String newSongSelectedFile(String name) {
    return 'Selected: $name';
  }

  @override
  String get newSongThemeLabel => 'Theme';

  @override
  String get newSongThemeHint => 'A sad song about the moon';

  @override
  String get newSongCustomLyricsLabel => 'Custom lyrics (optional)';

  @override
  String get newSongCustomLyricsHint => 'Leave empty for AI';

  @override
  String get newSongQuickStyles => 'Quick styles';

  @override
  String get newSongPresetRomanticArabic => 'Romantic Arabic (reference)';

  @override
  String get newSongPresetSadArabicBallad => 'Sad Arabic Ballad';

  @override
  String get newSongPresetKhaleejiRomantic => 'Khaleeji Romantic';

  @override
  String get newSongPresetUpbeatArabicPop => 'Upbeat Arabic Pop';

  @override
  String get newSongPresetAcousticSlow => 'Acoustic Slow';

  @override
  String get newSongPresetEnglishPopBallad => 'English Pop Ballad';

  @override
  String get newSongStyleHintLabel => 'Style hint';

  @override
  String get newSongYourTouchLabel => 'Your touch (optional)';

  @override
  String get newSongStyleHintHint =>
      'Pick a Quick style above, or type your own. Leave empty for AI to auto-pick.';

  @override
  String get newSongYourTouchHint =>
      'e.g. make it more upbeat, add oud, slower tempo…';

  @override
  String get newSongLanguageLabel => 'Language';

  @override
  String get newSongLanguageArabic => 'Arabic';

  @override
  String get newSongLanguageEnglish => 'English';

  @override
  String get newSongLanguageSpanish => 'Spanish';

  @override
  String get newSongLanguageFrench => 'French';

  @override
  String get newSongLanguageTurkish => 'Turkish';

  @override
  String get newSongVocalLabel => 'Vocal';

  @override
  String get newSongVocalMale => 'Male';

  @override
  String get newSongVocalFemale => 'Female';

  @override
  String get newSongVocalAuto => 'Auto (Suno picks)';

  @override
  String get newSongSunoModelLabel => 'Suno model';

  @override
  String get newSongSunoModelHelper =>
      'Newer = better quality. V3_5 is excluded (obvious-AI sound).';

  @override
  String get newSongSunoModelDefault => 'Default (V5_5)';

  @override
  String get newSongSunoModelLatest => 'V5_5 (latest)';

  @override
  String get newSongSunoModelLegacy => 'V4 (legacy)';

  @override
  String get newSongVideoTypeLabel => 'Video type';

  @override
  String get newSongVideoStatic => 'Static cover · 1 credit';

  @override
  String get newSongVideoCinematic => 'Cinematic video · 3 credits';

  @override
  String get newSongVoiceLabel => 'Voice';

  @override
  String get newSongVoiceHelper =>
      'Reuse a saved singer voice from a previous song';

  @override
  String get newSongVoiceAuto => 'Auto (let Suno pick)';

  @override
  String get newSongGenerating => 'Generating…';

  @override
  String get newSongGenerateButton => 'Generate my song';

  @override
  String get newSongReviewNotice =>
      'You will review lyrics + cover prompt before any credit is spent.';

  @override
  String get approveReviewDraft => 'Review draft';

  @override
  String get approveAnalyzing =>
      'Analyzing the song…\nThis can take a few minutes for imports.';

  @override
  String get approvePreparing => 'Preparing…';

  @override
  String get approveAnalysisFailed => 'Analysis failed — please try again';

  @override
  String get approveTimedOut =>
      'Timed out waiting for lyrics (exceeded 5 minutes)';

  @override
  String get approveEditLyrics => 'Edit lyrics';

  @override
  String get approveKeepSectionTags =>
      'Keep Suno section tags ([Verse 1], [Chorus]) intact — Suno uses them to structure the arrangement. Dropping them gives a formless song.';

  @override
  String get approveLyricsTooLong => 'Lyrics exceed 4000 chars';

  @override
  String get approveLyricsSection => 'Lyrics';

  @override
  String get approveEdit => 'Edit';

  @override
  String get approveReroll => 'Re-roll';

  @override
  String get approveStyleSection => 'Style';

  @override
  String get approveCoverPromptSection => 'Cover prompt';

  @override
  String approveCost(int count, String usd) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Cost: $count credits (~$usd)',
      one: 'Cost: 1 credit (~$usd)',
    );
    return '$_temp0';
  }

  @override
  String get approveDiscard => 'Discard';

  @override
  String get approveApproveGenerate => 'Approve & generate';

  @override
  String get songDetailTitleFallback => 'Song';

  @override
  String get songDetailStatusWaitingApproval => 'Waiting for approval';

  @override
  String get songDetailStatusGeneratingSong => 'Generating song (Suno ~30 s)…';

  @override
  String get songDetailStatusGeneratingCover => 'Generating cover (~15 s)…';

  @override
  String get songDetailStatusAssembling => 'Assembling video…';

  @override
  String get songDetailStatusDone => 'Done';

  @override
  String songDetailSwitchingTake(int take) {
    return 'Switching to Take $take — ready in ~1 min';
  }

  @override
  String songDetailSwapFailed(String error) {
    return 'Swap failed: $error';
  }

  @override
  String get songDetailRetryTitle => 'Retry will re-charge';

  @override
  String get songDetailRetryBody =>
      'The song generation failed. Retrying will spawn a new Suno job and deduct credits again. Continue?';

  @override
  String songDetailRetryFailed(String error) {
    return 'Retry failed: $error';
  }

  @override
  String songDetailDownloadFailed(String error) {
    return 'Download failed: $error';
  }

  @override
  String get songDetailDeleteTitle => 'Delete this song?';

  @override
  String songDetailDeleteBody(String title) {
    return 'This permanently removes the song, cover, takes, and final video for \"$title\". Credits already spent on Suno + Flux are not refunded.';
  }

  @override
  String get songDetailThisRun => 'this run';

  @override
  String get songDetailSongDeleted => 'Song deleted';

  @override
  String songDetailDeleteFailed(String error) {
    return 'Delete failed: $error';
  }

  @override
  String get songDetailSaveVoiceTitle => 'Save this voice';

  @override
  String get songDetailSaveVoiceBody =>
      'Locks the singer\'s voice from this song so you can reuse it on future generations.';

  @override
  String get songDetailVoiceNameLabel => 'Voice name';

  @override
  String get songDetailDescriptionLabel => 'Description';

  @override
  String get songDetailDescriptionHelper => 'Genre, mood, vocal qualities';

  @override
  String songDetailVoiceSaved(String name) {
    return 'Voice \"$name\" saved. Use it on the next song from the New Song form.';
  }

  @override
  String songDetailSaveFailed(String error) {
    return 'Save failed: $error';
  }

  @override
  String get songDetailShareTitle => 'Share this song';

  @override
  String get songDetailShareBody =>
      'Anyone with this link can play the song — no sign-in needed. Paste it in WhatsApp, Twitter, or anywhere; the preview shows the cover.';

  @override
  String get songDetailOpen => 'Open';

  @override
  String get songDetailCopyLink => 'Copy link';

  @override
  String get songDetailLinkCopied => 'Link copied to clipboard';

  @override
  String songDetailShareFailed(String error) {
    return 'Share failed: $error';
  }

  @override
  String get songDetailAiSongFallback => 'AI song';

  @override
  String get songDetailWatermarkTitle => 'Apply Faceless Lab watermark?';

  @override
  String get songDetailWatermarkBody =>
      'Re-renders the song\'s video to burn in the brand mark (top-right of the frame) and embed copyright + share-URL metadata into the MP4. The original audio and lyrics are preserved.\n\nTakes about 3–6 minutes. You can keep using the app — the watermark will appear once the render completes.';

  @override
  String get songDetailApplyWatermark => 'Apply watermark';

  @override
  String get songDetailApplyingWatermark =>
      'Applying watermark — this takes 3–6 minutes…';

  @override
  String songDetailWatermarkApplied(String seconds) {
    return 'Watermark applied in $seconds seconds.';
  }

  @override
  String songDetailWatermarkFailed(String error) {
    return 'Watermark failed: $error';
  }

  @override
  String get songDetailRerollTitle => 'Re-roll voice takes?';

  @override
  String get songDetailRerollBody =>
      'Generates two fresh Suno vocal takes (~\$0.05). Lyrics, style, and cover are preserved. Use this when both current takes missed the mood.';

  @override
  String get songDetailReroll => 'Re-roll';

  @override
  String get songDetailRerolling => 'Re-rolling Suno takes — ready in ~2 min';

  @override
  String songDetailRerollFailed(String error) {
    return 'Re-roll failed: $error';
  }

  @override
  String get songDetailRegenCoverTitle => 'Regenerate cover?';

  @override
  String get songDetailRegenCoverBody =>
      'Calls Flux for a fresh cover image (~\$0.03) and re-assembles the video with the new cover. Suno output is preserved. Takes ~2 minutes.';

  @override
  String get songDetailRegenerate => 'Regenerate';

  @override
  String get songDetailRegeneratingCover =>
      'Regenerating cover — refresh in ~2 min';

  @override
  String songDetailFailed(String error) {
    return 'Failed: $error';
  }

  @override
  String get songDetailDeleteTooltip => 'Delete this song';

  @override
  String get songDetailDownloadMp4 => 'Download MP4';

  @override
  String get songDetailDownloadMp3 => 'Download MP3';

  @override
  String get songDetailShare => 'Share';

  @override
  String get songDetailRegenCoverButton => 'Regenerate cover';

  @override
  String get songDetailRerollTakesButton => 'Re-roll voice takes';

  @override
  String get songDetailPlayVideo => 'Play video';

  @override
  String get songDetailDownload => 'Download';

  @override
  String songDetailVideoLoadError(String error) {
    return 'Could not load video: $error';
  }

  @override
  String get songDetailActiveTake => 'Active take';

  @override
  String songDetailTakeChosen(int take) {
    return 'Take $take ✓';
  }

  @override
  String songDetailUseTake(int take) {
    return 'Use Take $take';
  }

  @override
  String get songDetailFailSongTitle => 'Song generation failed';

  @override
  String get songDetailFailSongHint =>
      'Retry will spawn a fresh Suno job — this re-charges credits.';

  @override
  String get songDetailFailCoverTitle => 'Cover image failed';

  @override
  String get songDetailFailCoverHint =>
      'Suno output is saved. Retry only re-runs Flux + ffmpeg (~\$0.03).';

  @override
  String get songDetailFailAssembleTitle => 'Video assembly failed';

  @override
  String get songDetailFailAssembleHint =>
      'Suno + cover are saved. Retry only re-runs ffmpeg (free).';

  @override
  String get songDetailErrorFallback => 'Error';

  @override
  String get songDetailUnknownError => 'Unknown error';
}
