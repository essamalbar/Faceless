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

  @override
  String get landingHeroPill => 'AI Music Studio · Arabic & beyond';

  @override
  String get landingHeroTitlePart1 => 'Turn any idea into a ';

  @override
  String get landingHeroTitlePart2Accent => 'finished song.';

  @override
  String get landingHeroSubtitle =>
      'Write a theme, or upload a track for a faithful cover. Faceless composes the lyrics, voices it, designs the cover, and cuts a cinematic video — you approve before a single credit is spent.';

  @override
  String get landingStartCreating => 'Start creating';

  @override
  String get landingTrustLine =>
      '★★★★★   Loved by creators · 60 free credits to start';

  @override
  String get landingNowGenerating => 'Now generating';

  @override
  String get landingSampleTagline => 'Cinematic · 92 BPM · Arabic pop';

  @override
  String get landingSectionHowItWorks => 'How it works';

  @override
  String get landingSectionShowcase => 'What it makes';

  @override
  String get landingSectionPricing => 'Pricing';

  @override
  String get landingStep1Title => 'Pick a mode';

  @override
  String get landingStep1Body =>
      'Horror shorts: one-sentence premise becomes a cinematic Arabic story with characters and shots. Songs: a theme + style becomes a full Arabic ballad with cover art.';

  @override
  String get landingStep2Title => 'Review before you spend';

  @override
  String get landingStep2Body =>
      'AI drafts the script or lyrics + cover prompt for free. You see exactly what gets generated. Approve only when it feels right.';

  @override
  String get landingStep3Title => 'Download or share';

  @override
  String get landingStep3Body =>
      'Square MP4 with music + visuals, ready for WhatsApp and Instagram. Save the lyrics or script as a PDF. Share a public link with OG preview baked in.';

  @override
  String get landingShowcaseTagline1 => 'Horror · Folkloric · 2 min';

  @override
  String get landingShowcaseTagline2 => 'Horror · Urban · 90 sec';

  @override
  String get landingShowcaseTagline3 => 'Song · Romantic ballad · 3 min';

  @override
  String get landingPricingSubtitle =>
      'Credits power both modes. 1 song ≈ 1 credit. 1 horror clip = 1 credit (avg short = 8–12).';

  @override
  String get landingTierStarter => 'Starter';

  @override
  String get landingTierStarterDesc => 'For trying ideas';

  @override
  String get landingTierCreator => 'Creator';

  @override
  String get landingTierCreatorDesc => 'For weekly drops';

  @override
  String get landingTierPro => 'Pro';

  @override
  String get landingTierProDesc => 'For daily output';

  @override
  String get landingRecommended => 'Recommended';

  @override
  String get landingPerMonth => '/ month';

  @override
  String landingCreditsPerMonth(int count) {
    return '$count credits / month';
  }

  @override
  String get landingStartFree => 'Start free';

  @override
  String get landingFooterLine => 'Faceless Lab · faceless-lab.com';

  @override
  String get loginEmailLabel => 'Email';

  @override
  String get loginPasswordLabel => 'Password';

  @override
  String get loginEmailRequired => 'Email is required';

  @override
  String get loginEmailInvalid => 'Enter a valid email';

  @override
  String get loginPasswordRequired => 'Password is required';

  @override
  String get loginPasswordMinLength => 'Min 8 characters for new accounts';

  @override
  String get loginAccountCreatedInfo =>
      'Account created. Check your email to confirm — or sign in directly if email confirmation is disabled.';

  @override
  String loginUnexpectedError(String error) {
    return 'Unexpected error: $error';
  }

  @override
  String get loginShowPassword => 'Show password';

  @override
  String get loginHidePassword => 'Hide password';

  @override
  String get loginCreateAccount => 'Create account';

  @override
  String get loginSignUp => 'Sign up';

  @override
  String get loginNoAccountYet => 'No account yet? ';

  @override
  String get loginAlreadyHaveAccount => 'Already have one? ';

  @override
  String get loginSubtitle => 'Sign in to manage your runs';

  @override
  String get loginFooterTagline => 'Faceless · Arabic horror, scripted by AI';

  @override
  String get onboardingSkip => 'Skip';

  @override
  String get onboardingNext => 'Next';

  @override
  String get onboardingLetsCreate => 'Let\'s create';

  @override
  String get onboardingSlide1Eyebrow => 'WELCOME';

  @override
  String get onboardingSlide1Title =>
      'An Arabic AI studio that respects your wallet';

  @override
  String get onboardingSlide1Body =>
      'Faceless Lab generates cinematic Arabic horror shorts and original Arabic songs from a single sentence. You\'ll write the premise; we\'ll handle the rest.';

  @override
  String get onboardingSlide2Eyebrow => 'TWO MODES';

  @override
  String get onboardingSlide2Title => 'Horror shorts. AI songs. One studio.';

  @override
  String get onboardingSlide2Body =>
      'Switch between Horror (cinematic Arabic shorts in 6 dialects) and Songs (full Suno-vocal tracks with AI cover art). Each render lives in your library and stays sharable forever.';

  @override
  String get onboardingSlide3Eyebrow => 'FAIR PRICING';

  @override
  String get onboardingSlide3Title =>
      'Free drafts. You only pay when you generate.';

  @override
  String get onboardingSlide3Body =>
      'Scripts and lyrics preview at zero cost. Approve when you\'re happy. If a render fails, the credits come back automatically — you never pay for video that didn\'t deliver.';

  @override
  String get onboardingSlide4Eyebrow => 'LET\'S GO';

  @override
  String get onboardingSlide4Title => 'Your first draft is free.';

  @override
  String get onboardingSlide4Body =>
      'Tap below and write a sentence. The system will produce a full Arabic script or song lyrics for you to review — all before any credit is spent.';

  @override
  String get settingsResetDefaultsTitle => 'Reset to launcher defaults?';

  @override
  String get settingsResetDefaultsBody =>
      'This clears your saved Server URL from the device. The app will fall back to whatever the launcher script (run-app.sh) baked in via --dart-define on the next launch. Use this when the tunnel URL has changed and the saved value is stale.';

  @override
  String get settingsReset => 'Reset';

  @override
  String get settingsSignOutTitle => 'Sign out?';

  @override
  String get settingsSignOutBody =>
      'You\'ll need to sign in again to access your library and credits.';

  @override
  String get settingsSignOut => 'Sign out';

  @override
  String get settingsSectionSubscription => 'Subscription';

  @override
  String get settingsPlanCredits => 'Plan & credits';

  @override
  String get settingsPlanCreditsSubtitle =>
      'View plans, manage your subscription';

  @override
  String get settingsFreePlanSubtitle =>
      'You are on the Free plan — subscribe to render videos';

  @override
  String settingsManagePlanSubtitle(String plan) {
    return 'Manage your $plan plan';
  }

  @override
  String get settingsSectionAdvanced => 'Advanced';

  @override
  String get settingsSectionAbout => 'About';

  @override
  String get settingsTestConnected => '✓ Connected';

  @override
  String settingsTestFailed(String error) {
    return '✗ $error';
  }

  @override
  String get settingsResetDone => '✓ Reset — using launcher defaults';

  @override
  String get settingsNotSignedIn => 'Not signed in';

  @override
  String get settingsFreePlan => 'Free plan';

  @override
  String settingsPlanName(String plan) {
    return '$plan plan';
  }

  @override
  String get settingsServerConnection => 'Server connection';

  @override
  String get settingsServerConnectionSubtitle =>
      'Override the API URL — for self-hosters and debugging';

  @override
  String get settingsFirstTimeSetup =>
      'First-time setup. Paste the API URL printed by run-app.sh, then tap Test → Save.';

  @override
  String get settingsServerUrlLabel => 'Server URL';

  @override
  String get settingsUrlRequired => 'required';

  @override
  String get settingsUrlMustStartWithHttp =>
      'must start with http:// or https://';

  @override
  String get settingsTest => 'Test';

  @override
  String get settingsResetToLauncherDefaults => 'Reset to launcher defaults';

  @override
  String get settingsAboutApp => 'App';

  @override
  String get settingsAboutVersion => 'Version';

  @override
  String get settingsAboutMadeFor => 'Made for';

  @override
  String get settingsAboutMadeForValue => 'Arabic short-form storytelling';

  @override
  String get billingTitle => 'Billing';

  @override
  String get billingSubscriptions => 'Subscriptions';

  @override
  String billingPricePerMonth(String price) {
    return '$price / month';
  }

  @override
  String get billingManageSubscription => 'Manage subscription (Stripe)';

  @override
  String get billingRecentTransactions => 'Recent transactions';

  @override
  String get billingNoTransactions => 'No transactions yet.';

  @override
  String get billingBalance => 'Balance';

  @override
  String billingPlanLabel(String plan) {
    return 'Plan: $plan';
  }

  @override
  String get billingPlanFree => 'Free';

  @override
  String billingCancelsOn(String date) {
    return 'Cancels $date';
  }

  @override
  String billingRenewsOn(String date) {
    return 'Renews $date';
  }

  @override
  String get billingCurrentPlanChip => 'current';

  @override
  String get billingSubscribe => 'Subscribe';

  @override
  String get transactionsTitle => 'Transactions';

  @override
  String get transactionsKindSongSpend => 'Song spend';

  @override
  String get transactionsKindRefund => 'Refund';

  @override
  String get transactionsKindAdminCredit => 'Admin credit';

  @override
  String get transactionsKindWelcomeCredit => 'Welcome credit';

  @override
  String get transactionsKindSubscription => 'Subscription';

  @override
  String get transactionsKindTopup => 'Top-up';

  @override
  String transactionsLoadFailed(String error) {
    return 'Failed to load: $error';
  }

  @override
  String get transactionsEmpty =>
      'No transactions yet.\nGenerate a song or buy credits to see activity here.';

  @override
  String personasDeleteTitle(String name) {
    return 'Delete \"$name\"?';
  }

  @override
  String get personasDeleteBody =>
      'This removes the saved voice. Songs you already generated with it keep their audio — only future generations lose the lock to this voice.';

  @override
  String personasRemoved(String name) {
    return '\"$name\" removed';
  }

  @override
  String personasLoadFailed(String error) {
    return 'Failed to load voices: $error';
  }

  @override
  String get personasEmpty =>
      'No saved voices yet.\n\nGenerate a song, then tap \"Save this voice\" on its detail screen to pin the singer for future songs.';

  @override
  String personasFromSong(String runId, int take) {
    return 'From song $runId · take $take';
  }

  @override
  String get personasDeleteTooltip => 'Delete this voice';

  @override
  String get newRunTitle => 'New Episode';

  @override
  String get newRunTabAiGenerate => 'AI Generate';

  @override
  String get newRunTabPasteScript => 'Paste Script';

  @override
  String get newRunAiExplainer =>
      'AI generates a script from your premise. Pick the dialect, art style, character template, and narration style; the writer follows your choices.';

  @override
  String get newRunPremiseLabel => 'Premise (Arabic)';

  @override
  String get newRunPremiseTooShort => 'Premise too short';

  @override
  String get newRunThemeLabel => 'Theme';

  @override
  String get newRunDialectLabel => 'Dialect';

  @override
  String get newRunArtStyleLabel => 'Art style';

  @override
  String get newRunCharacterTemplateLabel => 'Character template';

  @override
  String get newRunEndingTypeLabel => 'Ending type';

  @override
  String get newRunNarrationStyleLabel => 'Narration style';

  @override
  String get newRunDialectMsa => 'MSA (الفصحى)';

  @override
  String get newRunDialectSyrian => 'Syrian / Levantine';

  @override
  String get newRunDialectEgyptian => 'Egyptian';

  @override
  String get newRunDialectKhaliji => 'Khaliji / Gulf';

  @override
  String get newRunDialectMaghrebi => 'Maghrebi';

  @override
  String get newRunDialectIraqi => 'Iraqi';

  @override
  String get newRunArtPixar3d => '3D Pixar';

  @override
  String get newRunArtAnime2d => '2D Anime';

  @override
  String get newRunArtCinematic => 'Cinematic photo-real';

  @override
  String get newRunArtClaymation => 'Claymation';

  @override
  String get newRunArtHandDrawn => 'Hand-drawn';

  @override
  String get newRunArtGhibli => 'Studio Ghibli';

  @override
  String get newRunAiChoose => 'Let the AI choose';

  @override
  String get newRunCharHuman => 'Human cast';

  @override
  String get newRunCharFruit => 'Fruit cast (Sunstoriz)';

  @override
  String get newRunCharAnimal => 'Animal cast';

  @override
  String get newRunCharSurreal => 'Surreal creatures';

  @override
  String get newRunEndingOpen => 'Open-ended';

  @override
  String get newRunEndingClosedTragic => 'Closed tragic';

  @override
  String get newRunEndingClosedHappy => 'Closed happy';

  @override
  String get newRunEndingTwist => 'Twist';

  @override
  String get newRunNarrCinematic => 'Cinematic (recommended)';

  @override
  String get newRunNarrFirstPerson => 'First-person monologue (TikTok)';

  @override
  String get newRunBeatsLabel => 'Beats:';

  @override
  String get newRunSecPerBeatLabel => 'Sec / beat:';

  @override
  String get newRunWriting => 'Writing…';

  @override
  String get newRunGenerateScript => 'Generate Script';

  @override
  String get newRunPasteExplainer =>
      'Your dialogue is used VERBATIM — no LLM rewrite. Use this for episode continuations where you want to control every line.';

  @override
  String get newRunPasteFromMarkdown => 'Paste from Markdown Script';

  @override
  String get newRunTitleLabel => 'Title (Arabic)';

  @override
  String get newRunTitleHint => 'مثلاً: العقد المقدس - الحلقة 4';

  @override
  String get newRunStoryContextLabel => 'Story context (optional, Arabic)';

  @override
  String get newRunStoryContextHint => 'الحلقة الرابعة من سلسلة العقد';

  @override
  String get newRunTitleRequired => 'Title is required';

  @override
  String get newRunBeatRequired => 'At least one beat is required';

  @override
  String get newRunVisualRequired =>
      'Every beat needs a visual description (English)';

  @override
  String newRunParsedBeats(int count, String method) {
    return 'Parsed $count beats ($method)';
  }

  @override
  String get newRunMethodRegex => 'regex';

  @override
  String get newRunMethodAiSplit => 'AI split';

  @override
  String get newRunMethodAuto => 'auto-segmented';

  @override
  String get newRunBadgeParsedMarkdown => 'Parsed from your markdown';

  @override
  String get newRunBadgeAiSplit => 'Split by AI — review before saving';

  @override
  String get newRunBadgeAutoSegmented => 'Auto-segmented — review carefully';

  @override
  String get newRunBeatsSection => 'Beats';

  @override
  String newRunAddBeat(int number) {
    return 'Add Beat ($number)';
  }

  @override
  String get newRunSaving => 'Saving…';

  @override
  String newRunUseScript(int count, String cost) {
    return 'Use This Script ($count beats, ~$cost)';
  }

  @override
  String get newRunPasteDialogTitle => 'Paste Markdown Script';

  @override
  String get newRunPasteFormatHelp =>
      'Recognised format: **العنوان: ...** title, **المشهد N – ...** scene headings, and **SPEAKER:**\\n\"dialogue\" blocks. Stage directions in plain prose are kept as silent context. Your Arabic is preserved character-for-character.';

  @override
  String get newRunPasteHint =>
      '**العنوان: القلادة المقدسة – الحلقة 4**\n\n**المشهد 1 – الفراغ**\nسكون مطلق...\n\n**الشاب (بهمس):**\n\"أنا… وين…؟\"\n\n...';

  @override
  String get newRunPasteRealScript =>
      'Paste a real script (at least a few scenes).';

  @override
  String get newRunTargetBeats => 'Target beats:';

  @override
  String get newRunParsing => 'Parsing…';

  @override
  String get newRunParseToBeats => 'Parse to Beats';

  @override
  String newRunBeatBadge(String number) {
    return 'BEAT $number';
  }

  @override
  String get newRunSpeakerLabel => 'Speaker (free-text)';

  @override
  String get newRunSpeakerHint => 'e.g. mother, narrator, warrior, …';

  @override
  String get newRunCharacterNameLabel => 'Character name (Arabic, optional)';

  @override
  String get newRunCharacterNameHint => 'e.g. خالد، فاطمة، أم يوسف';

  @override
  String get newRunArabicDialogueLabel =>
      'Arabic dialogue (leave empty for silent action beat)';

  @override
  String get newRunVisualDescLabel => 'Visual description (English) — required';

  @override
  String get newRunVisualDescHint =>
      'e.g. Strawberry son in stone room, golden light, looking at necklace';

  @override
  String get newRunClipDurationLabel => 'Clip duration:';

  @override
  String get runDetailStoryFallback => 'Story';

  @override
  String get runDetailActivityLog => 'Activity log';

  @override
  String get runDetailApprovedPreparing =>
      'Approved — preparing characters (~30s)…';

  @override
  String get runDetailApprovedGenerating => 'Approved — generating clips…';

  @override
  String runDetailApproveFailed(String error) {
    return 'Approve failed: $error';
  }

  @override
  String get runDetailRegenLookTitle => 'Regenerate character look?';

  @override
  String get runDetailRegenLookBody =>
      'This discards the current character look and generates a new one. Your credit balance is not affected.';

  @override
  String get runDetailKeep => 'Keep';

  @override
  String runDetailRerollFailed(String error) {
    return 'Reroll failed: $error';
  }

  @override
  String get runDetailRepairing =>
      'Repairing video — re-muxing for browser playback…';

  @override
  String get runDetailRepaired => 'Repaired. Tap Play again.';

  @override
  String runDetailRepairFailed(String error) {
    return 'Repair failed: $error';
  }

  @override
  String get runDetailResuming => 'Resuming pipeline…';

  @override
  String runDetailResumeFailed(String error) {
    return 'Resume failed: $error';
  }

  @override
  String get runDetailDiscardTitle => 'Discard this run?';

  @override
  String get runDetailDiscardBody =>
      'Cancelling will stop any running pipeline AND delete the run entirely. The script and any partially-generated artifacts will be removed. This cannot be undone.';

  @override
  String get runDetailRunDiscarded => 'Run discarded';

  @override
  String runDetailDiscardFailed(String error) {
    return 'Discard failed: $error';
  }

  @override
  String get runDetailNoScriptToReroll => 'No script — nothing to reroll';

  @override
  String runDetailRerollingClips(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Rerolling $count clips — $count credits',
      one: 'Rerolling 1 clip — 1 credit',
    );
    return '$_temp0';
  }

  @override
  String runDetailRerollClipTitle(String number) {
    return 'Reroll clip $number?';
  }

  @override
  String get runDetailRerollClipBody =>
      'This regenerates one clip and costs 1 credit.';

  @override
  String get runDetailRerollOneCredit => 'Reroll (1 credit)';

  @override
  String runDetailRerollingClip(String number) {
    return 'Rerolling clip $number — 1 credit';
  }

  @override
  String get runDetailStatusReady => 'Ready to watch';

  @override
  String get runDetailStatusScriptReady =>
      'Script ready — approve to generate the video';

  @override
  String get runDetailStatusCharacterReady =>
      'Character look ready — approve to generate clips';

  @override
  String get runDetailStatusGenerating => 'Generating your video…';

  @override
  String get runDetailStatusWriting => 'Writing the script…';

  @override
  String get runDetailStatusFailed => 'Generation failed — tap Resume to retry';

  @override
  String get runDetailRepairPlayback => 'Repair playback';

  @override
  String get runDetailRerollSelectedClips => 'Reroll selected clips';

  @override
  String get runDetailGenerationFailed => 'Generation failed';

  @override
  String get runDetailResume => 'Resume';

  @override
  String get runDetailCancelDiscard => 'Cancel & Discard';

  @override
  String runDetailCreditsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count credits',
      one: '1 credit',
    );
    return '$_temp0';
  }

  @override
  String runDetailScriptBeats(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Script ($count beats)',
      one: 'Script (1 beat)',
    );
    return '$_temp0';
  }

  @override
  String get runDetailDownloadScriptPdf => 'Download script (PDF)';

  @override
  String get runDetailRerollClipTooltip => 'Reroll this clip (1 credit)';

  @override
  String get runDetailSilentBeat => '(silent action beat — no dialogue)';

  @override
  String get runDetailStartingGeneration =>
      'Starting video generation — clips appear shortly…';

  @override
  String get runDetailApprovingPreparing =>
      'Approving — preparing characters (~30s)…';

  @override
  String runDetailApproveVeoLine(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Approve to generate the video — $count credits',
      one: 'Approve to generate the video — 1 credit',
    );
    return '$_temp0';
  }

  @override
  String runDetailApproveLine(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'Approve to start generation — $count credits total',
      one: 'Approve to start generation — 1 credit total',
    );
    return '$_temp0';
  }

  @override
  String get runDetailVeoGateHint =>
      'Once started, clips render one by one (~1 min each).';

  @override
  String get runDetailApproveHint =>
      'Characters are prepared first; the video starts once you confirm again.';

  @override
  String get runDetailApprove => 'Approve';

  @override
  String get runDetailStagePreparingCharacters => 'Preparing characters…';

  @override
  String runDetailStageGeneratingClip(int current, int total) {
    return 'Generating clip $current of $total…';
  }

  @override
  String get runDetailStageAligningCaptions => 'Aligning captions…';

  @override
  String get runDetailStageAssembling => 'Assembling final video…';

  @override
  String runDetailClipsDone(int done, int total) {
    return '$done / $total clips done';
  }

  @override
  String get runDetailCharacterLook => 'CHARACTER LOOK';

  @override
  String get runDetailDontLikeRegenerate => 'Don\'t like it? Regenerate';

  @override
  String get runDetailRerollWhichTitle => 'Reroll which clips?';

  @override
  String get runDetailRerollWhichBody =>
      'Pick the clips that need regenerating. Each costs 1 credit. The other clips stay; the final video re-stitches at the end.';

  @override
  String get runDetailNoClipsSelected => 'No clips selected';

  @override
  String runDetailSelectedClipsCredits(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count clips — $count credits',
      one: '1 clip — 1 credit',
    );
    return '$_temp0';
  }

  @override
  String get editScriptTitle => 'Edit Script';

  @override
  String get editScriptTitleLabel => 'Title';

  @override
  String get editScriptArabicDialogueLabel =>
      'Arabic dialogue (leave empty for silent beat)';

  @override
  String get editScriptVisualDescLabel => 'Visual description (English)';

  @override
  String get costTitle => 'Spend';

  @override
  String get costSortByDate => 'Sort by date';

  @override
  String get costSortByAmount => 'Sort by amount';

  @override
  String get costByAmount => 'BY AMOUNT';

  @override
  String get costByDate => 'BY DATE (newest first)';

  @override
  String get costTotalKieSpend => 'TOTAL KIE.AI SPEND';

  @override
  String get costRunsLabel => 'RUNS';

  @override
  String get costAvgPerRun => 'AVG / RUN';

  @override
  String costPercentOfTotal(String percent) {
    return '$percent % of total';
  }

  @override
  String get costFootnote =>
      'Counts Veo (\$0.10/sec) + Flux character sheet (\$0.05/run). Doesn\'t include ElevenLabs (~\$0.30/episode if used) or Anthropic / Groq script generation (<\$0.05/episode).';

  @override
  String videoPlayerClipTitle(String number) {
    return 'Clip $number';
  }

  @override
  String get videoPlayerUrlCopied => 'Video URL copied — paste anywhere';

  @override
  String get videoPlayerOpenLinkToDownload =>
      'Open the link in a new tab to download';

  @override
  String get videoPlayerPlaybackError => 'playback error';

  @override
  String get videoPlayerCantRepairBody =>
      'This video can\'t be repaired.\n\nThe mp4 file is corrupt at a level we can\'t fix without re-rendering. Use the Reroll button on the run page to regenerate the affected clips.';

  @override
  String get videoPlayerBackToRun => 'Back to run';

  @override
  String get videoPlayerRepairing => 'Repairing playback…';

  @override
  String logViewerTitle(String runId) {
    return 'Log — $runId';
  }

  @override
  String get logViewerCopyTooltip => 'Copy log';

  @override
  String get logViewerCopied => 'Log copied';

  @override
  String get logViewerEmpty => '(empty)';

  @override
  String get paywallOutOfCredits => 'Out of credits';

  @override
  String paywallNeedCredits(int needed, int balance, int missing) {
    return 'This video needs $needed credits. You have $balance — $missing more to go. Top up to keep generating.';
  }

  @override
  String get paywallSavedNotice =>
      'Your script and characters are saved. After topping up, tap Resume on this run to continue.';

  @override
  String get paywallTopUp => 'Top up';

  @override
  String get misconfiguredTitle => 'Backend not configured.';

  @override
  String get misconfiguredBody =>
      'Restart via scripts/run-app.sh so the Supabase + API URLs are baked into the build.';

  @override
  String get artistsSectionTitle => 'Artists';

  @override
  String get artistNewTile => 'New';

  @override
  String get artistEditTitleCreate => 'New artist';

  @override
  String get artistEditTitleEdit => 'Edit artist';

  @override
  String get artistNameLabel => 'Name';

  @override
  String get artistNameRequired => 'Name is required';

  @override
  String get artistHandleLabel => 'Handle';

  @override
  String get artistHandleHelper =>
      'Optional — leave empty and one is generated from the name';

  @override
  String get artistBioLabel => 'Bio';

  @override
  String get artistDefaultStyleLabel => 'Default style';

  @override
  String get artistVocalLabel => 'Default voice';

  @override
  String get artistChooseAvatar => 'Choose avatar image';

  @override
  String get artistAvatarSelected =>
      'New avatar selected — it uploads when you save';

  @override
  String artistAvatarUploadFailed(String error) {
    return 'Avatar upload failed: $error';
  }

  @override
  String get artistCreateButton => 'Create artist';

  @override
  String get artistSaveButton => 'Save changes';

  @override
  String get artistDeleteButton => 'Delete artist';

  @override
  String get artistDeleteConfirmTitle => 'Delete artist?';

  @override
  String get artistDeleteConfirmBody =>
      'Songs stay playable but leave this discography. The saved voice is kept.';

  @override
  String artistDeleteFailed(String error) {
    return 'Delete failed: $error';
  }

  @override
  String artistSongCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count songs',
      one: '1 song',
      zero: 'No songs yet',
    );
    return '$_temp0';
  }

  @override
  String get artistShare => 'Share';

  @override
  String get artistLinkCopied => 'Artist link copied';

  @override
  String get artistEdit => 'Edit';

  @override
  String artistNewSongCta(String name) {
    return 'New song as $name';
  }

  @override
  String get artistDiscographyTitle => 'Discography';

  @override
  String artistNoSongsYet(String name) {
    return 'No songs yet — release the first one as $name.';
  }

  @override
  String get artistPickerLabel => 'Sing as artist';

  @override
  String get artistPickerNone => 'None';

  @override
  String get artistMakeFromSongButton => 'Make this singer an artist';

  @override
  String get artistMakeFromSongBody =>
      'Saves this song\'s voice and creates an artist around it. This song joins the discography, and new songs can be made as this artist.';

  @override
  String artistCreatedSnack(String name) {
    return 'Artist \"$name\" created';
  }

  @override
  String artistCreateFailed(String error) {
    return 'Couldn\'t create artist: $error';
  }

  @override
  String get releaseButton => 'Release to stores';

  @override
  String get releaseButtonReleased => 'Released ✓';

  @override
  String get releaseDialogTitle => 'Release to stores';

  @override
  String get releaseDialogExplainer =>
      'Everything a distributor needs — audio, artwork, metadata, and lyrics — packed into one zip. Follow the steps below to get this song on Spotify, Apple Music, and more.';

  @override
  String get releaseArtistHint =>
      'Tip: assign an artist first for consistent branding.';

  @override
  String get releaseStep1 => 'Download the release package.';

  @override
  String get releaseStep2 => 'Unzip it.';

  @override
  String get releaseStep3 => 'Create a DistroKid (or any distributor) account.';

  @override
  String get releaseStep4 => 'Tap \"Upload\" and choose audio.mp3.';

  @override
  String get releaseStep5 => 'Use cover.jpg as the artwork.';

  @override
  String get releaseStep6 =>
      'Copy the title, artist, genre, and language from metadata.txt.';

  @override
  String get releaseStep7 => 'Paste lyrics.txt when asked for the lyrics.';

  @override
  String get releaseStep8 =>
      'Submit — stores go live in 1–7 days, then return here and tap \"Mark as released\".';

  @override
  String get releaseDownloadPackage => 'Download package';

  @override
  String get releaseMarkAsReleased => 'Mark as released';

  @override
  String get releaseMarkedSnack => 'Marked as released';

  @override
  String get releaseUnmarkedSnack => 'Release mark removed';

  @override
  String releaseMarkFailed(String error) {
    return 'Couldn\'t update release status: $error';
  }

  @override
  String get releaseBadge => 'Released';

  @override
  String get ytSettingsTitle => 'YouTube';

  @override
  String get ytSettingsSubtitleDisconnected => 'Publish songs to your channel';

  @override
  String ytSettingsConnected(String channel) {
    return 'Connected: $channel';
  }

  @override
  String get ytConnect => 'Connect';

  @override
  String get ytDisconnect => 'Disconnect';

  @override
  String get ytDisconnectConfirmTitle => 'Disconnect YouTube?';

  @override
  String get ytDisconnectConfirmBody =>
      'Publishing from the app stops until you connect again. Videos already on YouTube are not affected.';

  @override
  String get ytDisconnectedSnack => 'YouTube disconnected';

  @override
  String ytDisconnectFailed(String error) {
    return 'Couldn\'t disconnect: $error';
  }

  @override
  String get ytFinishInBrowser =>
      'Finish connecting in the browser, then pull to refresh.';

  @override
  String ytConnectFailed(String error) {
    return 'Couldn\'t start YouTube connect: $error';
  }

  @override
  String get ytPublishButton => 'Publish to YouTube';

  @override
  String get ytOnYoutubeButton => 'On YouTube';

  @override
  String get ytPublishDialogTitle => 'Publish to YouTube';

  @override
  String get ytPublishPreauditNote =>
      'The upload starts as private until Google approves the app — make it public from YouTube Studio.';

  @override
  String get ytPublish => 'Publish';

  @override
  String get ytPublishedSnack => 'Published to YouTube';

  @override
  String ytPublishFailed(String error) {
    return 'Publish failed: $error';
  }

  @override
  String get ytNotConnectedSnack =>
      'YouTube isn\'t connected — connect it from Settings first.';

  @override
  String get ytBadge => 'YouTube';

  @override
  String get ytAutoPublishLabel => 'Auto-publish new songs to YouTube';

  @override
  String get ytAutoPublishSubtitle =>
      'When a song finishes, it\'s uploaded to your channel automatically.';

  @override
  String ytAutoPublishSaveFailed(String error) {
    return 'Couldn\'t save the YouTube auto-publish setting: $error';
  }

  @override
  String get newSongFaithfulness => 'Faithfulness to the original';

  @override
  String get newSongFaithfulnessHigh =>
      'High — the cover closely follows the original\'s melody and feel.';

  @override
  String get newSongFaithfulnessLow =>
      'Low — more creative freedom, further from the original.';

  @override
  String get llmDegradedBanner =>
      'Lyric quality reduced — the primary writing model is unavailable (check Anthropic credits).';
}
