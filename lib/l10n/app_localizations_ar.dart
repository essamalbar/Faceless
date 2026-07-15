// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Arabic (`ar`).
class AppLocalizationsAr extends AppLocalizations {
  AppLocalizationsAr([String locale = 'ar']) : super(locale);

  @override
  String get appTitle => 'فيسلس لاب';

  @override
  String get commonCancel => 'إلغاء';

  @override
  String get commonSave => 'حفظ';

  @override
  String get commonRetry => 'إعادة المحاولة';

  @override
  String get commonClose => 'إغلاق';

  @override
  String get commonDelete => 'حذف';

  @override
  String get commonSignIn => 'تسجيل الدخول';

  @override
  String get commonGetStarted => 'ابدأ الآن';

  @override
  String get settingsLanguage => 'اللغة';

  @override
  String get settingsLanguageAuto => 'تلقائي (لغة الجهاز)';

  @override
  String get statusAnalyzing => 'جارٍ التحليل';

  @override
  String get statusAwaitingApproval => 'بانتظار الموافقة';

  @override
  String get statusGeneratingSong => 'جارٍ توليد الأغنية';

  @override
  String get statusGeneratingCover => 'جارٍ توليد الغلاف';

  @override
  String get statusAssembling => 'جارٍ التجميع';

  @override
  String get statusComplete => 'مكتملة';

  @override
  String get statusFailed => 'فشلت';

  @override
  String get statusRunning => 'قيد التشغيل';

  @override
  String get statusCancelled => 'أُلغيت';

  @override
  String get homeCleanupFailedTitle => 'حذف العمليات الفاشلة؟';

  @override
  String get homeCleanupFailedBody =>
      'سيؤدي هذا إلى الحذف النهائي لكل عملية في حالة الفشل حاليًا. لن تتأثر العمليات الجارية والمكتملة.';

  @override
  String get homeDeleteAllFailed => 'حذف كل الفاشلة';

  @override
  String homeRemovedFailedRuns(int count) {
    return 'تمت إزالة $count من العمليات الفاشلة';
  }

  @override
  String homeCleanupError(String error) {
    return 'فشل التنظيف: $error';
  }

  @override
  String get homeDeleteRunTitle => 'حذف هذه العملية؟';

  @override
  String homeDeleteRunBody(String name) {
    return 'سيؤدي هذا إلى إزالة مجلد العملية نهائيًا، بما في ذلك أي مقاطع مولّدة وملف final.mp4. $name';
  }

  @override
  String homeDeletedItem(String name) {
    return 'تم حذف $name';
  }

  @override
  String homeDeleteError(String error) {
    return 'فشل الحذف: $error';
  }

  @override
  String get homeRefresh => 'تحديث';

  @override
  String get homeSavedVoices => 'الأصوات المحفوظة';

  @override
  String get homeSettings => 'الإعدادات';

  @override
  String get homeTabHorror => 'رعب';

  @override
  String get homeTabSong => 'أغنية';

  @override
  String get homeNoRunsMatchFilter => 'لا توجد عمليات تطابق هذا الفلتر.';

  @override
  String get homeShowAll => 'عرض الكل';

  @override
  String get homeAllRuns => 'كل العمليات';

  @override
  String get homeNewSong => 'أغنية جديدة';

  @override
  String get homeRecent => 'الأحدث';

  @override
  String homeTracksCount(int count) {
    return '$count مقطوعة';
  }

  @override
  String get homeResults => 'النتائج';

  @override
  String get homeYourSongs => 'أغانيك';

  @override
  String get homeNoSongsMatchSearch => 'لا توجد أغانٍ تطابق بحثك';

  @override
  String get homeUntitled => '(بلا عنوان)';

  @override
  String get homeSearchHint => 'ابحث في أغانيك…';

  @override
  String get homeLatestRelease => '◆  أحدث إصدار';

  @override
  String get homePlay => 'تشغيل';

  @override
  String get homeDetails => 'التفاصيل';

  @override
  String homeEpisodesCount(int count) {
    return '$count حلقات';
  }

  @override
  String homeEpisodeAbbrev(int number) {
    return 'الحلقة $number';
  }

  @override
  String get homeYourStories => 'قصصك';

  @override
  String get homeNoRenderedVideos => 'لا توجد فيديوهات جاهزة بعد';

  @override
  String get homeApproveScriptHint => 'وافق على نصٍّ وسيظهر الفيديو هنا.';

  @override
  String get homeServerUnreachable => 'تعذّر الوصول إلى الخادم.';

  @override
  String get homeHeroTagline => 'قصص رعب عربية قصيرة بالذكاء الاصطناعي';

  @override
  String get homeHeroSubtitle => 'اصنع قصصك القصيرة بالذكاء الاصطناعي';

  @override
  String get homeStartCreating => 'ابدأ الإبداع';

  @override
  String get homeFreeToWrite => 'الكتابة مجانية · اشترك لإخراج الفيديو';

  @override
  String get homeChooseTheme => 'اختر ثيمة';

  @override
  String get homeChooseThemeSubtitle => 'انقر لبدء قصة جديدة بهذا الأسلوب';

  @override
  String get homeHowItWorks => 'كيف تعمل';

  @override
  String get homePlans => 'الخطط';

  @override
  String homeRunsCount(int count) {
    return '($count عملية)';
  }

  @override
  String homeCleanFailed(int count) {
    return 'تنظيف $count فاشلة';
  }

  @override
  String get homeFilterAll => 'الكل';

  @override
  String get homeFilterComplete => 'مكتملة';

  @override
  String get homeFilterAwaiting => 'بالانتظار';

  @override
  String get homeFilterRunning => 'قيد التشغيل';

  @override
  String get homeFilterFailed => 'فاشلة';

  @override
  String get homeStatusWritingLyrics => 'جارٍ كتابة الكلمات';

  @override
  String get homeStatusReviewApprove => 'راجِع ووافِق';

  @override
  String get homeStatusComposing => 'جارٍ تلحين الموسيقى';

  @override
  String get homeStatusDesigningCover => 'جارٍ تصميم الغلاف';

  @override
  String get homeStatusSyncingBeat => 'جارٍ المزامنة مع الإيقاع';

  @override
  String get homeStatusSyncingLyrics => 'جارٍ مزامنة الكلمات';

  @override
  String get homeStatusRendering => 'جارٍ إخراج الفيديو';

  @override
  String get homeStatusReady => 'جاهزة';

  @override
  String get homeStatusPending => 'قيد الانتظار';

  @override
  String get homeYourPlan => 'خطتك';

  @override
  String get homeRecommended => 'موصى بها';

  @override
  String homeCreditsCount(int count) {
    return '$count رصيد';
  }

  @override
  String get homeSeeFullPlans => 'عرض جميع الخطط';

  @override
  String get homePlanStarter => 'المبتدئ';

  @override
  String get homePlanCreator => 'المبدع';

  @override
  String get homePlanPro => 'الاحترافي';

  @override
  String get homeStep1Title => 'اكتب فكرة القصة';

  @override
  String get homeStep1Subtitle => 'جملة واحدة تكفي';

  @override
  String get homeStep2Title => 'الذكاء الاصطناعي يكتب النص';

  @override
  String get homeStep2Subtitle => 'بالعربية، في ثوانٍ — مجانًا للجميع';

  @override
  String get homeStep3Title => 'اشترك لإخراج الفيديو';

  @override
  String get homeStep3Subtitle => 'كل مقطع يستهلك رصيدًا واحدًا';

  @override
  String get homeMakeFirstSong => 'اصنع أول أغنية لك بالذكاء الاصطناعي';

  @override
  String get homePickSampleHint =>
      'اختر نموذجًا للبدء، أو انقر «أغنية جديدة» لكتابة أغنيتك.';

  @override
  String get homeNewSongFromScratch => 'أغنية جديدة من الصفر';

  @override
  String get homeThemeFolkloric => 'فلكلوري';

  @override
  String get homeThemeFolkloricDesc => 'حكايات الأجداد والجن والآبار القديمة';

  @override
  String get homeThemeUrban => 'مدني';

  @override
  String get homeThemeUrbanDesc => 'أساطير المدينة وشوارع آخر الليل';

  @override
  String get homeThemeWilderness => 'البرية';

  @override
  String get homeThemeWildernessDesc => 'غابات وصحارى والمجهول';

  @override
  String get homeThemeMemory => 'الذاكرة';

  @override
  String get homeThemeMemoryDesc => 'نفسي، وذكريات نصف منسية';

  @override
  String get homeThemeDomestic => 'منزلي';

  @override
  String get homeThemeDomesticDesc => 'البيت والعائلة حين ينقلب المألوف';

  @override
  String get homeThemeTravel => 'سفر';

  @override
  String get homeThemeTravelDesc => 'على الطريق، بعيدًا عن الديار';

  @override
  String get homeThemeTech => 'تقني';

  @override
  String get homeThemeTechDesc => 'شاشات وإشارات وآلات';

  @override
  String get homeThemeWorkplace => 'العمل';

  @override
  String get homeThemeWorkplaceDesc => 'مكاتب ومتاجر وما بعد الدوام';

  @override
  String get newSongTitle => 'أغنية جديدة';

  @override
  String get newSongModeTheme => 'اكتب فكرة';

  @override
  String get newSongModeUpload => 'ارفع أغنية';

  @override
  String get newSongUploadExplainer =>
      'ارفع أغنية وسينشئ الذكاء الاصطناعي نسخة وفية منها — يحافظ على اللحن والكلمات بأداء صوت جديد. سيختلف الصوت عن الأصل. راجع الكلمات وعدّلها قبل إنفاق أي رصيد.';

  @override
  String get newSongThemeExplainer =>
      'سيكتب الذكاء الاصطناعي الكلمات ووصف صورة الغلاف. يمكنك مراجعتهما وتعديلهما قبل إنفاق أي رصيد.';

  @override
  String get newSongFileReadError => 'تعذّرت قراءة هذا الملف — جرّب ملفًا آخر.';

  @override
  String newSongFilePickerError(String error) {
    return 'تعذّر فتح منتقي الملفات: $error';
  }

  @override
  String get newSongChooseAudioError => 'اختر ملفًا صوتيًا لعمل نسخة منه';

  @override
  String get newSongThemeRequired => 'الموضوع مطلوب';

  @override
  String get newSongChooseAudioFile => 'اختر ملفًا صوتيًا (mp3، m4a، wav…)';

  @override
  String newSongSelectedFile(String name) {
    return 'المحدد: $name';
  }

  @override
  String get newSongThemeLabel => 'الموضوع';

  @override
  String get newSongThemeHint => 'أغنية حزينة عن القمر';

  @override
  String get newSongCustomLyricsLabel => 'كلمات مخصصة (اختياري)';

  @override
  String get newSongCustomLyricsHint => 'اتركه فارغًا ليكتبها الذكاء الاصطناعي';

  @override
  String get newSongQuickStyles => 'أنماط سريعة';

  @override
  String get newSongPresetRomanticArabic => 'عربي رومانسي (مرجعي)';

  @override
  String get newSongPresetSadArabicBallad => 'أغنية عربية حزينة';

  @override
  String get newSongPresetKhaleejiRomantic => 'خليجي رومانسي';

  @override
  String get newSongPresetUpbeatArabicPop => 'بوب عربي حيوي';

  @override
  String get newSongPresetAcousticSlow => 'أكوستيك هادئ';

  @override
  String get newSongPresetEnglishPopBallad => 'بوب إنجليزي عاطفي';

  @override
  String get newSongStyleHintLabel => 'وصف الأسلوب';

  @override
  String get newSongYourTouchLabel => 'لمستك (اختياري)';

  @override
  String get newSongStyleHintHint =>
      'اختر نمطًا سريعًا أعلاه أو اكتب وصفك الخاص. اتركه فارغًا ليختار الذكاء الاصطناعي تلقائيًا.';

  @override
  String get newSongYourTouchHint =>
      'مثال: اجعلها أكثر حيوية، أضف عودًا، إيقاعًا أبطأ…';

  @override
  String get newSongLanguageLabel => 'اللغة';

  @override
  String get newSongLanguageArabic => 'العربية';

  @override
  String get newSongLanguageEnglish => 'الإنجليزية';

  @override
  String get newSongLanguageSpanish => 'الإسبانية';

  @override
  String get newSongLanguageFrench => 'الفرنسية';

  @override
  String get newSongLanguageTurkish => 'التركية';

  @override
  String get newSongVocalLabel => 'صوت الغناء';

  @override
  String get newSongVocalMale => 'ذكر';

  @override
  String get newSongVocalFemale => 'أنثى';

  @override
  String get newSongVocalAuto => 'تلقائي (يختار Suno)';

  @override
  String get newSongSunoModelLabel => 'نموذج Suno';

  @override
  String get newSongSunoModelHelper =>
      'الأحدث = جودة أفضل. V3_5 مستبعد (صوت اصطناعي واضح).';

  @override
  String get newSongSunoModelDefault => 'الافتراضي (V5_5)';

  @override
  String get newSongSunoModelLatest => 'V5_5 (الأحدث)';

  @override
  String get newSongSunoModelLegacy => 'V4 (قديم)';

  @override
  String get newSongVideoTypeLabel => 'نوع الفيديو';

  @override
  String get newSongVideoStatic => 'غلاف ثابت · رصيد واحد';

  @override
  String get newSongVideoCinematic => 'فيديو سينمائي · 3 أرصدة';

  @override
  String get newSongVoiceLabel => 'الصوت';

  @override
  String get newSongVoiceHelper => 'أعد استخدام صوت مغنٍّ محفوظ من أغنية سابقة';

  @override
  String get newSongVoiceAuto => 'تلقائي (دع Suno يختار)';

  @override
  String get newSongGenerating => 'جارٍ الإنشاء…';

  @override
  String get newSongGenerateButton => 'أنشئ أغنيتي';

  @override
  String get newSongReviewNotice =>
      'ستراجع الكلمات ووصف الغلاف قبل إنفاق أي رصيد.';

  @override
  String get approveReviewDraft => 'مراجعة المسودة';

  @override
  String get approveAnalyzing =>
      'جارٍ تحليل الأغنية…\nقد يستغرق هذا بضع دقائق عند الاستيراد.';

  @override
  String get approvePreparing => 'جارٍ التحضير…';

  @override
  String get approveAnalysisFailed => 'فشل التحليل — يرجى المحاولة مرة أخرى';

  @override
  String get approveTimedOut => 'انتهت مهلة انتظار الكلمات (تجاوزت 5 دقائق)';

  @override
  String get approveEditLyrics => 'تعديل الكلمات';

  @override
  String get approveKeepSectionTags =>
      'أبقِ وسوم المقاطع الخاصة بـ Suno ([Verse 1]، [Chorus]) كما هي — يستخدمها Suno لبناء التوزيع الموسيقي. حذفها يعطي أغنية بلا بنية.';

  @override
  String get approveLyricsTooLong => 'الكلمات تتجاوز 4000 حرف';

  @override
  String get approveLyricsSection => 'الكلمات';

  @override
  String get approveEdit => 'تعديل';

  @override
  String get approveReroll => 'إعادة توليد';

  @override
  String get approveStyleSection => 'الأسلوب';

  @override
  String get approveCoverPromptSection => 'وصف الغلاف';

  @override
  String approveCost(int count, String usd) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'التكلفة: $count رصيد (~$usd)',
      many: 'التكلفة: $count رصيدًا (~$usd)',
      few: 'التكلفة: $count أرصدة (~$usd)',
      two: 'التكلفة: رصيدان (~$usd)',
      one: 'التكلفة: رصيد واحد (~$usd)',
    );
    return '$_temp0';
  }

  @override
  String get approveDiscard => 'تجاهل';

  @override
  String get approveApproveGenerate => 'الموافقة والإنشاء';

  @override
  String get songDetailTitleFallback => 'أغنية';

  @override
  String get songDetailStatusWaitingApproval => 'في انتظار الموافقة';

  @override
  String get songDetailStatusGeneratingSong =>
      'جارٍ إنشاء الأغنية (Suno ~30 ث)…';

  @override
  String get songDetailStatusGeneratingCover => 'جارٍ إنشاء الغلاف (~15 ث)…';

  @override
  String get songDetailStatusAssembling => 'جارٍ تجميع الفيديو…';

  @override
  String get songDetailStatusDone => 'تم';

  @override
  String songDetailSwitchingTake(int take) {
    return 'جارٍ التبديل إلى اللقطة $take — جاهزة خلال دقيقة تقريبًا';
  }

  @override
  String songDetailSwapFailed(String error) {
    return 'فشل التبديل: $error';
  }

  @override
  String get songDetailRetryTitle => 'إعادة المحاولة ستخصم رصيدًا مجددًا';

  @override
  String get songDetailRetryBody =>
      'فشل إنشاء الأغنية. إعادة المحاولة ستطلق مهمة Suno جديدة وتخصم الرصيد مرة أخرى. هل تريد المتابعة؟';

  @override
  String songDetailRetryFailed(String error) {
    return 'فشلت إعادة المحاولة: $error';
  }

  @override
  String songDetailDownloadFailed(String error) {
    return 'فشل التنزيل: $error';
  }

  @override
  String get songDetailDeleteTitle => 'حذف هذه الأغنية؟';

  @override
  String songDetailDeleteBody(String title) {
    return 'سيؤدي هذا إلى إزالة الأغنية والغلاف واللقطات والفيديو النهائي لـ \"$title\" نهائيًا. الرصيد المنفق على Suno وFlux لا يُسترد.';
  }

  @override
  String get songDetailThisRun => 'هذا التشغيل';

  @override
  String get songDetailSongDeleted => 'تم حذف الأغنية';

  @override
  String songDetailDeleteFailed(String error) {
    return 'فشل الحذف: $error';
  }

  @override
  String get songDetailSaveVoiceTitle => 'حفظ هذا الصوت';

  @override
  String get songDetailSaveVoiceBody =>
      'يثبّت صوت المغني من هذه الأغنية لتتمكن من إعادة استخدامه في الإنشاءات القادمة.';

  @override
  String get songDetailVoiceNameLabel => 'اسم الصوت';

  @override
  String get songDetailDescriptionLabel => 'الوصف';

  @override
  String get songDetailDescriptionHelper =>
      'النوع الموسيقي، المزاج، خصائص الصوت';

  @override
  String songDetailVoiceSaved(String name) {
    return 'تم حفظ الصوت \"$name\". استخدمه في الأغنية القادمة من نموذج أغنية جديدة.';
  }

  @override
  String songDetailSaveFailed(String error) {
    return 'فشل الحفظ: $error';
  }

  @override
  String get songDetailShareTitle => 'مشاركة هذه الأغنية';

  @override
  String get songDetailShareBody =>
      'يمكن لأي شخص لديه هذا الرابط تشغيل الأغنية — دون الحاجة لتسجيل الدخول. الصقه في واتساب أو تويتر أو أي مكان؛ وستعرض المعاينة الغلاف.';

  @override
  String get songDetailOpen => 'فتح';

  @override
  String get songDetailCopyLink => 'نسخ الرابط';

  @override
  String get songDetailLinkCopied => 'تم نسخ الرابط إلى الحافظة';

  @override
  String songDetailShareFailed(String error) {
    return 'فشلت المشاركة: $error';
  }

  @override
  String get songDetailAiSongFallback => 'أغنية ذكاء اصطناعي';

  @override
  String get songDetailWatermarkTitle =>
      'إضافة العلامة المائية لـ Faceless Lab؟';

  @override
  String get songDetailWatermarkBody =>
      'يعيد تصيير فيديو الأغنية لدمج علامة الهوية (أعلى يمين الإطار) وتضمين بيانات حقوق النشر ورابط المشاركة في ملف MP4. يبقى الصوت والكلمات الأصلية دون تغيير.\n\nيستغرق حوالي 3–6 دقائق. يمكنك متابعة استخدام التطبيق — ستظهر العلامة المائية فور اكتمال التصيير.';

  @override
  String get songDetailApplyWatermark => 'إضافة العلامة المائية';

  @override
  String get songDetailApplyingWatermark =>
      'جارٍ إضافة العلامة المائية — يستغرق هذا 3–6 دقائق…';

  @override
  String songDetailWatermarkApplied(String seconds) {
    return 'تمت إضافة العلامة المائية خلال $seconds ثانية.';
  }

  @override
  String songDetailWatermarkFailed(String error) {
    return 'فشلت إضافة العلامة المائية: $error';
  }

  @override
  String get songDetailRerollTitle => 'إعادة توليد اللقطات الصوتية؟';

  @override
  String get songDetailRerollBody =>
      'ينشئ لقطتين صوتيتين جديدتين من Suno (~\$0.05). تبقى الكلمات والأسلوب والغلاف كما هي. استخدم هذا عندما تخفق اللقطتان الحاليتان في التعبير عن المزاج.';

  @override
  String get songDetailReroll => 'إعادة توليد';

  @override
  String get songDetailRerolling =>
      'جارٍ إعادة توليد لقطات Suno — جاهزة خلال دقيقتين تقريبًا';

  @override
  String songDetailRerollFailed(String error) {
    return 'فشلت إعادة التوليد: $error';
  }

  @override
  String get songDetailRegenCoverTitle => 'إعادة إنشاء الغلاف؟';

  @override
  String get songDetailRegenCoverBody =>
      'يستدعي Flux لإنشاء صورة غلاف جديدة (~\$0.03) ويعيد تجميع الفيديو بالغلاف الجديد. يبقى ناتج Suno محفوظًا. يستغرق دقيقتين تقريبًا.';

  @override
  String get songDetailRegenerate => 'إعادة الإنشاء';

  @override
  String get songDetailRegeneratingCover =>
      'جارٍ إعادة إنشاء الغلاف — حدّث خلال دقيقتين تقريبًا';

  @override
  String songDetailFailed(String error) {
    return 'فشل: $error';
  }

  @override
  String get songDetailDeleteTooltip => 'حذف هذه الأغنية';

  @override
  String get songDetailDownloadMp4 => 'تنزيل MP4';

  @override
  String get songDetailDownloadMp3 => 'تنزيل MP3';

  @override
  String get songDetailShare => 'مشاركة';

  @override
  String get songDetailRegenCoverButton => 'إعادة إنشاء الغلاف';

  @override
  String get songDetailRerollTakesButton => 'إعادة توليد اللقطات الصوتية';

  @override
  String get songDetailPlayVideo => 'تشغيل الفيديو';

  @override
  String get songDetailDownload => 'تنزيل';

  @override
  String songDetailVideoLoadError(String error) {
    return 'تعذّر تحميل الفيديو: $error';
  }

  @override
  String get songDetailActiveTake => 'اللقطة النشطة';

  @override
  String songDetailTakeChosen(int take) {
    return 'اللقطة $take ✓';
  }

  @override
  String songDetailUseTake(int take) {
    return 'استخدم اللقطة $take';
  }

  @override
  String get songDetailFailSongTitle => 'فشل إنشاء الأغنية';

  @override
  String get songDetailFailSongHint =>
      'إعادة المحاولة ستطلق مهمة Suno جديدة — وهذا يخصم رصيدًا مجددًا.';

  @override
  String get songDetailFailCoverTitle => 'فشلت صورة الغلاف';

  @override
  String get songDetailFailCoverHint =>
      'ناتج Suno محفوظ. إعادة المحاولة تعيد تشغيل Flux وffmpeg فقط (~\$0.03).';

  @override
  String get songDetailFailAssembleTitle => 'فشل تجميع الفيديو';

  @override
  String get songDetailFailAssembleHint =>
      'ناتج Suno والغلاف محفوظان. إعادة المحاولة تعيد تشغيل ffmpeg فقط (مجانًا).';

  @override
  String get songDetailErrorFallback => 'خطأ';

  @override
  String get songDetailUnknownError => 'خطأ غير معروف';

  @override
  String get landingHeroPill =>
      'استوديو موسيقى بالذكاء الاصطناعي · بالعربية وأبعد';

  @override
  String get landingHeroTitlePart1 => 'حوّل أي فكرة إلى ';

  @override
  String get landingHeroTitlePart2Accent => 'أغنية كاملة.';

  @override
  String get landingHeroSubtitle =>
      'اكتب فكرة، أو ارفع مقطعًا لصنع نسخة وفية منه. يؤلّف Faceless الكلمات، ويؤديها غناءً، ويصمم الغلاف، ويُخرج فيديو سينمائيًا — وأنت توافق قبل إنفاق رصيد واحد.';

  @override
  String get landingStartCreating => 'ابدأ الإبداع';

  @override
  String get landingTrustLine =>
      '★★★★★   يحبه صنّاع المحتوى · 60 رصيدًا مجانيًا للبدء';

  @override
  String get landingNowGenerating => 'قيد التوليد الآن';

  @override
  String get landingSampleTagline => 'سينمائي · 92 BPM · بوب عربي';

  @override
  String get landingSectionHowItWorks => 'كيف تعمل';

  @override
  String get landingSectionShowcase => 'ماذا تصنع';

  @override
  String get landingSectionPricing => 'الأسعار';

  @override
  String get landingStep1Title => 'اختر وضعًا';

  @override
  String get landingStep1Body =>
      'قصص الرعب القصيرة: جملة واحدة تتحول إلى قصة عربية سينمائية بشخصيات ولقطات. الأغاني: فكرة وأسلوب يتحولان إلى أغنية عربية كاملة مع غلاف فني.';

  @override
  String get landingStep2Title => 'راجِع قبل أن تنفق';

  @override
  String get landingStep2Body =>
      'يكتب الذكاء الاصطناعي النص أو الكلمات ووصف الغلاف مجانًا. ترى بالضبط ما سيُولَّد. لا توافق إلا عندما يعجبك.';

  @override
  String get landingStep3Title => 'نزّل أو شارك';

  @override
  String get landingStep3Body =>
      'فيديو MP4 مربّع بالموسيقى والمرئيات، جاهز لواتساب وإنستغرام. احفظ الكلمات أو النص بصيغة PDF. شارك رابطًا عامًا بمعاينة جاهزة للمشاركة.';

  @override
  String get landingShowcaseTagline1 => 'رعب · فلكلوري · دقيقتان';

  @override
  String get landingShowcaseTagline2 => 'رعب · مدني · 90 ثانية';

  @override
  String get landingShowcaseTagline3 => 'أغنية · بالاد رومانسي · 3 دقائق';

  @override
  String get landingPricingSubtitle =>
      'الرصيد يشغّل الوضعين معًا. أغنية واحدة ≈ رصيد واحد. مقطع رعب واحد = رصيد واحد (متوسط الفيديو القصير = 8–12).';

  @override
  String get landingTierStarter => 'المبتدئ';

  @override
  String get landingTierStarterDesc => 'لتجربة الأفكار';

  @override
  String get landingTierCreator => 'المبدع';

  @override
  String get landingTierCreatorDesc => 'لإصدارات أسبوعية';

  @override
  String get landingTierPro => 'الاحترافي';

  @override
  String get landingTierProDesc => 'لإنتاج يومي';

  @override
  String get landingRecommended => 'موصى بها';

  @override
  String get landingPerMonth => '/ شهريًا';

  @override
  String landingCreditsPerMonth(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count رصيد في الشهر',
      many: '$count رصيدًا في الشهر',
      few: '$count أرصدة في الشهر',
      two: 'رصيدان في الشهر',
      one: 'رصيد واحد في الشهر',
    );
    return '$_temp0';
  }

  @override
  String get landingStartFree => 'ابدأ مجانًا';

  @override
  String get landingFooterLine => 'Faceless Lab · faceless-lab.com';

  @override
  String get loginEmailLabel => 'البريد الإلكتروني';

  @override
  String get loginPasswordLabel => 'كلمة المرور';

  @override
  String get loginEmailRequired => 'البريد الإلكتروني مطلوب';

  @override
  String get loginEmailInvalid => 'أدخل بريدًا إلكترونيًا صحيحًا';

  @override
  String get loginPasswordRequired => 'كلمة المرور مطلوبة';

  @override
  String get loginPasswordMinLength => '8 أحرف على الأقل للحسابات الجديدة';

  @override
  String get loginAccountCreatedInfo =>
      'تم إنشاء الحساب. تحقق من بريدك الإلكتروني للتأكيد — أو سجّل الدخول مباشرة إذا كان تأكيد البريد معطّلًا.';

  @override
  String loginUnexpectedError(String error) {
    return 'خطأ غير متوقع: $error';
  }

  @override
  String get loginShowPassword => 'إظهار كلمة المرور';

  @override
  String get loginHidePassword => 'إخفاء كلمة المرور';

  @override
  String get loginCreateAccount => 'إنشاء الحساب';

  @override
  String get loginSignUp => 'إنشاء حساب';

  @override
  String get loginNoAccountYet => 'ليس لديك حساب بعد؟ ';

  @override
  String get loginAlreadyHaveAccount => 'لديك حساب بالفعل؟ ';

  @override
  String get loginSubtitle => 'سجّل الدخول لإدارة أعمالك';

  @override
  String get loginFooterTagline => 'Faceless · رعب عربي بقلم الذكاء الاصطناعي';

  @override
  String get onboardingSkip => 'تخطّي';

  @override
  String get onboardingNext => 'التالي';

  @override
  String get onboardingLetsCreate => 'هيا نبدع';

  @override
  String get onboardingSlide1Eyebrow => 'مرحبًا بك';

  @override
  String get onboardingSlide1Title =>
      'استوديو عربي بالذكاء الاصطناعي يحترم ميزانيتك';

  @override
  String get onboardingSlide1Body =>
      'ينشئ Faceless Lab قصص رعب عربية سينمائية قصيرة وأغاني عربية أصلية من جملة واحدة. أنت تكتب الفكرة، ونحن نتولى الباقي.';

  @override
  String get onboardingSlide2Eyebrow => 'وضعان';

  @override
  String get onboardingSlide2Title =>
      'قصص رعب قصيرة. أغانٍ بالذكاء الاصطناعي. استوديو واحد.';

  @override
  String get onboardingSlide2Body =>
      'بدّل بين الرعب (قصص عربية سينمائية قصيرة بست لهجات) والأغاني (مقطوعات كاملة بأصوات Suno مع غلاف فني بالذكاء الاصطناعي). كل عمل يبقى في مكتبتك وقابلًا للمشاركة إلى الأبد.';

  @override
  String get onboardingSlide3Eyebrow => 'تسعير عادل';

  @override
  String get onboardingSlide3Title =>
      'المسودات مجانية. لا تدفع إلا عند التوليد.';

  @override
  String get onboardingSlide3Body =>
      'تُعرض النصوص والكلمات دون أي تكلفة. وافق عندما ترضى. وإذا فشل الإخراج، يعود الرصيد تلقائيًا — لن تدفع أبدًا مقابل فيديو لم يكتمل.';

  @override
  String get onboardingSlide4Eyebrow => 'هيا بنا';

  @override
  String get onboardingSlide4Title => 'مسودتك الأولى مجانية.';

  @override
  String get onboardingSlide4Body =>
      'انقر أدناه واكتب جملة واحدة. سينتج النظام نصًا عربيًا كاملًا أو كلمات أغنية لتراجعها — كل ذلك قبل إنفاق أي رصيد.';
}
