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

  @override
  String get settingsResetDefaultsTitle =>
      'إعادة الضبط إلى إعدادات المشغّل الافتراضية؟';

  @override
  String get settingsResetDefaultsBody =>
      'يمسح هذا عنوان الخادم المحفوظ من الجهاز. سيعود التطبيق عند التشغيل التالي إلى القيمة التي ضمّنها سكربت التشغيل (run-app.sh) عبر ‎--dart-define. استخدم هذا عندما يتغيّر عنوان النفق وتصبح القيمة المحفوظة قديمة.';

  @override
  String get settingsReset => 'إعادة الضبط';

  @override
  String get settingsSignOutTitle => 'تسجيل الخروج؟';

  @override
  String get settingsSignOutBody =>
      'ستحتاج إلى تسجيل الدخول مجددًا للوصول إلى مكتبتك ورصيدك.';

  @override
  String get settingsSignOut => 'تسجيل الخروج';

  @override
  String get settingsSectionSubscription => 'الاشتراك';

  @override
  String get settingsPlanCredits => 'الخطة والرصيد';

  @override
  String get settingsPlanCreditsSubtitle => 'اعرض الخطط وأدر اشتراكك';

  @override
  String get settingsFreePlanSubtitle =>
      'أنت على الخطة المجانية — اشترك لإخراج الفيديوهات';

  @override
  String settingsManagePlanSubtitle(String plan) {
    return 'أدر خطة $plan الخاصة بك';
  }

  @override
  String get settingsSectionAdvanced => 'متقدم';

  @override
  String get settingsSectionAbout => 'حول التطبيق';

  @override
  String get settingsTestConnected => '✓ تم الاتصال';

  @override
  String settingsTestFailed(String error) {
    return '✗ $error';
  }

  @override
  String get settingsResetDone =>
      '✓ تمت إعادة الضبط — تُستخدم إعدادات المشغّل الافتراضية';

  @override
  String get settingsNotSignedIn => 'لم يتم تسجيل الدخول';

  @override
  String get settingsFreePlan => 'الخطة المجانية';

  @override
  String settingsPlanName(String plan) {
    return 'خطة $plan';
  }

  @override
  String get settingsServerConnection => 'الاتصال بالخادم';

  @override
  String get settingsServerConnectionSubtitle =>
      'تجاوز عنوان API — للاستضافة الذاتية وتصحيح الأخطاء';

  @override
  String get settingsFirstTimeSetup =>
      'الإعداد لأول مرة. الصق عنوان API الذي يطبعه run-app.sh، ثم انقر «اختبار» ثم «حفظ».';

  @override
  String get settingsServerUrlLabel => 'عنوان الخادم';

  @override
  String get settingsUrlRequired => 'مطلوب';

  @override
  String get settingsUrlMustStartWithHttp =>
      'يجب أن يبدأ بـ http:// أو https://';

  @override
  String get settingsTest => 'اختبار';

  @override
  String get settingsResetToLauncherDefaults =>
      'إعادة الضبط إلى إعدادات المشغّل الافتراضية';

  @override
  String get settingsAboutApp => 'التطبيق';

  @override
  String get settingsAboutVersion => 'الإصدار';

  @override
  String get settingsAboutMadeFor => 'صُنع من أجل';

  @override
  String get settingsAboutMadeForValue => 'القصص العربية القصيرة';

  @override
  String get billingTitle => 'الفوترة';

  @override
  String get billingSubscriptions => 'الاشتراكات';

  @override
  String billingPricePerMonth(String price) {
    return '$price / شهريًا';
  }

  @override
  String get billingManageSubscription => 'إدارة الاشتراك (Stripe)';

  @override
  String get billingRecentTransactions => 'أحدث المعاملات';

  @override
  String get billingNoTransactions => 'لا توجد معاملات بعد.';

  @override
  String get billingBalance => 'الرصيد';

  @override
  String billingPlanLabel(String plan) {
    return 'الخطة: $plan';
  }

  @override
  String get billingPlanFree => 'مجانية';

  @override
  String billingCancelsOn(String date) {
    return 'يُلغى في $date';
  }

  @override
  String billingRenewsOn(String date) {
    return 'يتجدد في $date';
  }

  @override
  String get billingCurrentPlanChip => 'الحالية';

  @override
  String get billingSubscribe => 'اشترك';

  @override
  String get transactionsTitle => 'المعاملات';

  @override
  String get transactionsKindSongSpend => 'إنفاق أغنية';

  @override
  String get transactionsKindRefund => 'استرداد';

  @override
  String get transactionsKindAdminCredit => 'رصيد إداري';

  @override
  String get transactionsKindWelcomeCredit => 'رصيد ترحيبي';

  @override
  String get transactionsKindSubscription => 'اشتراك';

  @override
  String get transactionsKindTopup => 'تعبئة رصيد';

  @override
  String transactionsLoadFailed(String error) {
    return 'فشل التحميل: $error';
  }

  @override
  String get transactionsEmpty =>
      'لا توجد معاملات بعد.\nأنشئ أغنية أو اشترِ رصيدًا لترى النشاط هنا.';

  @override
  String personasDeleteTitle(String name) {
    return 'حذف \"$name\"؟';
  }

  @override
  String get personasDeleteBody =>
      'يزيل هذا الصوت المحفوظ. الأغاني التي أنشأتها به سابقًا تحتفظ بصوتها — الإنشاءات المستقبلية فقط هي التي تفقد التثبيت على هذا الصوت.';

  @override
  String personasRemoved(String name) {
    return 'تمت إزالة \"$name\"';
  }

  @override
  String personasLoadFailed(String error) {
    return 'فشل تحميل الأصوات: $error';
  }

  @override
  String get personasEmpty =>
      'لا توجد أصوات محفوظة بعد.\n\nأنشئ أغنية، ثم انقر «حفظ هذا الصوت» في شاشة تفاصيلها لتثبيت المغني للأغاني القادمة.';

  @override
  String personasFromSong(String runId, int take) {
    return 'من الأغنية $runId · اللقطة $take';
  }

  @override
  String get personasDeleteTooltip => 'حذف هذا الصوت';

  @override
  String get newRunTitle => 'حلقة جديدة';

  @override
  String get newRunTabAiGenerate => 'توليد بالذكاء الاصطناعي';

  @override
  String get newRunTabPasteScript => 'لصق نص';

  @override
  String get newRunAiExplainer =>
      'يولّد الذكاء الاصطناعي نصًا من فكرتك. اختر اللهجة والأسلوب الفني وقالب الشخصيات وأسلوب السرد؛ وسيلتزم الكاتب باختياراتك.';

  @override
  String get newRunPremiseLabel => 'الفكرة (بالعربية)';

  @override
  String get newRunPremiseTooShort => 'الفكرة قصيرة جدًا';

  @override
  String get newRunThemeLabel => 'الثيمة';

  @override
  String get newRunDialectLabel => 'اللهجة';

  @override
  String get newRunArtStyleLabel => 'الأسلوب الفني';

  @override
  String get newRunCharacterTemplateLabel => 'قالب الشخصيات';

  @override
  String get newRunEndingTypeLabel => 'نوع النهاية';

  @override
  String get newRunNarrationStyleLabel => 'أسلوب السرد';

  @override
  String get newRunDialectMsa => 'الفصحى (MSA)';

  @override
  String get newRunDialectSyrian => 'سورية / شامية';

  @override
  String get newRunDialectEgyptian => 'مصرية';

  @override
  String get newRunDialectKhaliji => 'خليجية';

  @override
  String get newRunDialectMaghrebi => 'مغاربية';

  @override
  String get newRunDialectIraqi => 'عراقية';

  @override
  String get newRunArtPixar3d => 'بيكسار ثلاثي الأبعاد';

  @override
  String get newRunArtAnime2d => 'أنمي ثنائي الأبعاد';

  @override
  String get newRunArtCinematic => 'سينمائي واقعي';

  @override
  String get newRunArtClaymation => 'تحريك بالصلصال';

  @override
  String get newRunArtHandDrawn => 'رسم يدوي';

  @override
  String get newRunArtGhibli => 'ستوديو جيبلي';

  @override
  String get newRunAiChoose => 'دع الذكاء الاصطناعي يختار';

  @override
  String get newRunCharHuman => 'شخصيات بشرية';

  @override
  String get newRunCharFruit => 'شخصيات فواكه (Sunstoriz)';

  @override
  String get newRunCharAnimal => 'شخصيات حيوانات';

  @override
  String get newRunCharSurreal => 'كائنات سريالية';

  @override
  String get newRunEndingOpen => 'نهاية مفتوحة';

  @override
  String get newRunEndingClosedTragic => 'نهاية مأساوية مغلقة';

  @override
  String get newRunEndingClosedHappy => 'نهاية سعيدة مغلقة';

  @override
  String get newRunEndingTwist => 'نهاية بمفاجأة';

  @override
  String get newRunNarrCinematic => 'سينمائي (موصى به)';

  @override
  String get newRunNarrFirstPerson => 'مونولوج بضمير المتكلم (تيك توك)';

  @override
  String get newRunBeatsLabel => 'المشاهد:';

  @override
  String get newRunSecPerBeatLabel => 'ثانية / مشهد:';

  @override
  String get newRunWriting => 'جارٍ الكتابة…';

  @override
  String get newRunGenerateScript => 'توليد النص';

  @override
  String get newRunPasteExplainer =>
      'يُستخدم حوارك حرفيًا — دون أي إعادة صياغة بالذكاء الاصطناعي. استخدم هذا لتكملة الحلقات عندما تريد التحكم في كل سطر.';

  @override
  String get newRunPasteFromMarkdown => 'لصق من نص ماركداون';

  @override
  String get newRunTitleLabel => 'العنوان (بالعربية)';

  @override
  String get newRunTitleHint => 'مثلاً: العقد المقدس - الحلقة 4';

  @override
  String get newRunStoryContextLabel => 'سياق القصة (اختياري، بالعربية)';

  @override
  String get newRunStoryContextHint => 'الحلقة الرابعة من سلسلة العقد';

  @override
  String get newRunTitleRequired => 'العنوان مطلوب';

  @override
  String get newRunBeatRequired => 'مطلوب مشهد واحد على الأقل';

  @override
  String get newRunVisualRequired => 'كل مشهد يحتاج إلى وصف بصري (بالإنجليزية)';

  @override
  String newRunParsedBeats(int count, String method) {
    return 'تم تحليل $count من المشاهد ($method)';
  }

  @override
  String get newRunMethodRegex => 'تحليل نمطي';

  @override
  String get newRunMethodAiSplit => 'تقسيم بالذكاء الاصطناعي';

  @override
  String get newRunMethodAuto => 'تقسيم تلقائي';

  @override
  String get newRunBadgeParsedMarkdown =>
      'تم التحليل من نص الماركداون الخاص بك';

  @override
  String get newRunBadgeAiSplit => 'قسّمه الذكاء الاصطناعي — راجعه قبل الحفظ';

  @override
  String get newRunBadgeAutoSegmented => 'تقسيم تلقائي — راجعه بعناية';

  @override
  String get newRunBeatsSection => 'المشاهد';

  @override
  String newRunAddBeat(int number) {
    return 'إضافة مشهد ($number)';
  }

  @override
  String get newRunSaving => 'جارٍ الحفظ…';

  @override
  String newRunUseScript(int count, String cost) {
    return 'استخدام هذا النص ($count مشاهد، ~$cost)';
  }

  @override
  String get newRunPasteDialogTitle => 'لصق نص ماركداون';

  @override
  String get newRunPasteFormatHelp =>
      'الصيغة المدعومة: عنوان **العنوان: ...**، وعناوين مشاهد **المشهد N – ...**، وكتل **المتحدث:**\\n\"الحوار\". تُحفظ الإرشادات المسرحية المكتوبة نثرًا كسياق صامت. يُحفظ نصك العربي حرفًا بحرف.';

  @override
  String get newRunPasteHint =>
      '**العنوان: القلادة المقدسة – الحلقة 4**\n\n**المشهد 1 – الفراغ**\nسكون مطلق...\n\n**الشاب (بهمس):**\n\"أنا… وين…؟\"\n\n...';

  @override
  String get newRunPasteRealScript =>
      'الصق نصًا حقيقيًا (بضعة مشاهد على الأقل).';

  @override
  String get newRunTargetBeats => 'عدد المشاهد المستهدف:';

  @override
  String get newRunParsing => 'جارٍ التحليل…';

  @override
  String get newRunParseToBeats => 'تحليل إلى مشاهد';

  @override
  String newRunBeatBadge(String number) {
    return 'مشهد $number';
  }

  @override
  String get newRunSpeakerLabel => 'المتحدث (نص حر)';

  @override
  String get newRunSpeakerHint => 'مثال: mother، narrator، warrior…';

  @override
  String get newRunCharacterNameLabel => 'اسم الشخصية (بالعربية، اختياري)';

  @override
  String get newRunCharacterNameHint => 'مثال: خالد، فاطمة، أم يوسف';

  @override
  String get newRunArabicDialogueLabel =>
      'الحوار العربي (اتركه فارغًا لمشهد صامت)';

  @override
  String get newRunVisualDescLabel => 'الوصف البصري (بالإنجليزية) — مطلوب';

  @override
  String get newRunVisualDescHint =>
      'مثال: Strawberry son in stone room, golden light, looking at necklace';

  @override
  String get newRunClipDurationLabel => 'مدة المقطع:';

  @override
  String get runDetailStoryFallback => 'قصة';

  @override
  String get runDetailActivityLog => 'سجل النشاط';

  @override
  String get runDetailApprovedPreparing =>
      'تمت الموافقة — جارٍ تجهيز الشخصيات (~30 ث)…';

  @override
  String get runDetailApprovedGenerating =>
      'تمت الموافقة — جارٍ توليد المقاطع…';

  @override
  String runDetailApproveFailed(String error) {
    return 'فشلت الموافقة: $error';
  }

  @override
  String get runDetailRegenLookTitle => 'إعادة توليد مظهر الشخصيات؟';

  @override
  String get runDetailRegenLookBody =>
      'يتجاهل هذا مظهر الشخصيات الحالي ويولّد مظهرًا جديدًا. لن يتأثر رصيدك.';

  @override
  String get runDetailKeep => 'إبقاء';

  @override
  String runDetailRerollFailed(String error) {
    return 'فشلت إعادة التوليد: $error';
  }

  @override
  String get runDetailRepairing =>
      'جارٍ إصلاح الفيديو — إعادة تجميع للتشغيل في المتصفح…';

  @override
  String get runDetailRepaired => 'تم الإصلاح. انقر «تشغيل» مرة أخرى.';

  @override
  String runDetailRepairFailed(String error) {
    return 'فشل الإصلاح: $error';
  }

  @override
  String get runDetailResuming => 'جارٍ استئناف المعالجة…';

  @override
  String runDetailResumeFailed(String error) {
    return 'فشل الاستئناف: $error';
  }

  @override
  String get runDetailDiscardTitle => 'تجاهل هذه العملية؟';

  @override
  String get runDetailDiscardBody =>
      'سيوقف الإلغاء أي معالجة جارية وسيحذف العملية بالكامل. سيُزال النص وأي ملفات مولّدة جزئيًا. لا يمكن التراجع عن هذا.';

  @override
  String get runDetailRunDiscarded => 'تم تجاهل العملية';

  @override
  String runDetailDiscardFailed(String error) {
    return 'فشل التجاهل: $error';
  }

  @override
  String get runDetailNoScriptToReroll => 'لا يوجد نص — لا شيء لإعادة توليده';

  @override
  String runDetailRerollingClips(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'جارٍ إعادة توليد $count مقطع — $count رصيد',
      many: 'جارٍ إعادة توليد $count مقطعًا — $count رصيدًا',
      few: 'جارٍ إعادة توليد $count مقاطع — $count أرصدة',
      two: 'جارٍ إعادة توليد مقطعين — رصيدان',
      one: 'جارٍ إعادة توليد مقطع واحد — رصيد واحد',
    );
    return '$_temp0';
  }

  @override
  String runDetailRerollClipTitle(String number) {
    return 'إعادة توليد المقطع $number؟';
  }

  @override
  String get runDetailRerollClipBody =>
      'يعيد هذا توليد مقطع واحد ويكلّف رصيدًا واحدًا.';

  @override
  String get runDetailRerollOneCredit => 'إعادة توليد (رصيد واحد)';

  @override
  String runDetailRerollingClip(String number) {
    return 'جارٍ إعادة توليد المقطع $number — رصيد واحد';
  }

  @override
  String get runDetailStatusReady => 'جاهز للمشاهدة';

  @override
  String get runDetailStatusScriptReady => 'النص جاهز — وافق لتوليد الفيديو';

  @override
  String get runDetailStatusCharacterReady =>
      'مظهر الشخصيات جاهز — وافق لتوليد المقاطع';

  @override
  String get runDetailStatusGenerating => 'جارٍ توليد الفيديو الخاص بك…';

  @override
  String get runDetailStatusWriting => 'جارٍ كتابة النص…';

  @override
  String get runDetailStatusFailed =>
      'فشل التوليد — انقر «استئناف» لإعادة المحاولة';

  @override
  String get runDetailRepairPlayback => 'إصلاح التشغيل';

  @override
  String get runDetailRerollSelectedClips => 'إعادة توليد المقاطع المحددة';

  @override
  String get runDetailGenerationFailed => 'فشل التوليد';

  @override
  String get runDetailResume => 'استئناف';

  @override
  String get runDetailCancelDiscard => 'إلغاء وتجاهل';

  @override
  String runDetailCreditsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count رصيد',
      many: '$count رصيدًا',
      few: '$count أرصدة',
      two: 'رصيدان',
      one: 'رصيد واحد',
    );
    return '$_temp0';
  }

  @override
  String runDetailScriptBeats(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'النص ($count مشهد)',
      many: 'النص ($count مشهدًا)',
      few: 'النص ($count مشاهد)',
      two: 'النص (مشهدان)',
      one: 'النص (مشهد واحد)',
    );
    return '$_temp0';
  }

  @override
  String get runDetailDownloadScriptPdf => 'تنزيل النص (PDF)';

  @override
  String get runDetailRerollClipTooltip => 'إعادة توليد هذا المقطع (رصيد واحد)';

  @override
  String get runDetailSilentBeat => '(مشهد صامت — بلا حوار)';

  @override
  String get runDetailStartingGeneration =>
      'جارٍ بدء توليد الفيديو — ستظهر المقاطع قريبًا…';

  @override
  String get runDetailApprovingPreparing =>
      'جارٍ الموافقة — يجري تجهيز الشخصيات (~30 ث)…';

  @override
  String runDetailApproveVeoLine(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'وافق لتوليد الفيديو — $count رصيد',
      many: 'وافق لتوليد الفيديو — $count رصيدًا',
      few: 'وافق لتوليد الفيديو — $count أرصدة',
      two: 'وافق لتوليد الفيديو — رصيدان',
      one: 'وافق لتوليد الفيديو — رصيد واحد',
    );
    return '$_temp0';
  }

  @override
  String runDetailApproveLine(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: 'وافق لبدء التوليد — $count رصيد إجمالًا',
      many: 'وافق لبدء التوليد — $count رصيدًا إجمالًا',
      few: 'وافق لبدء التوليد — $count أرصدة إجمالًا',
      two: 'وافق لبدء التوليد — رصيدان إجمالًا',
      one: 'وافق لبدء التوليد — رصيد واحد إجمالًا',
    );
    return '$_temp0';
  }

  @override
  String get runDetailVeoGateHint =>
      'بعد البدء، تُولَّد المقاطع واحدًا تلو الآخر (~دقيقة لكل مقطع).';

  @override
  String get runDetailApproveHint =>
      'تُجهَّز الشخصيات أولًا؛ ويبدأ الفيديو بعد تأكيدك مرة أخرى.';

  @override
  String get runDetailApprove => 'موافقة';

  @override
  String get runDetailStagePreparingCharacters => 'جارٍ تجهيز الشخصيات…';

  @override
  String runDetailStageGeneratingClip(int current, int total) {
    return 'جارٍ توليد المقطع $current من $total…';
  }

  @override
  String get runDetailStageAligningCaptions => 'جارٍ مزامنة الترجمات…';

  @override
  String get runDetailStageAssembling => 'جارٍ تجميع الفيديو النهائي…';

  @override
  String runDetailClipsDone(int done, int total) {
    return 'اكتمل $done / $total من المقاطع';
  }

  @override
  String get runDetailCharacterLook => 'مظهر الشخصيات';

  @override
  String get runDetailDontLikeRegenerate => 'لم يعجبك؟ أعد التوليد';

  @override
  String get runDetailRerollWhichTitle => 'أي المقاطع تريد إعادة توليدها؟';

  @override
  String get runDetailRerollWhichBody =>
      'اختر المقاطع التي تحتاج إلى إعادة توليد. يكلّف كل مقطع رصيدًا واحدًا. تبقى المقاطع الأخرى كما هي؛ ويُعاد تجميع الفيديو النهائي في النهاية.';

  @override
  String get runDetailNoClipsSelected => 'لم تُحدد أي مقاطع';

  @override
  String runDetailSelectedClipsCredits(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count مقطع — $count رصيد',
      many: '$count مقطعًا — $count رصيدًا',
      few: '$count مقاطع — $count أرصدة',
      two: 'مقطعان — رصيدان',
      one: 'مقطع واحد — رصيد واحد',
    );
    return '$_temp0';
  }

  @override
  String get editScriptTitle => 'تعديل النص';

  @override
  String get editScriptTitleLabel => 'العنوان';

  @override
  String get editScriptArabicDialogueLabel =>
      'الحوار العربي (اتركه فارغًا لمشهد صامت)';

  @override
  String get editScriptVisualDescLabel => 'الوصف البصري (بالإنجليزية)';

  @override
  String get costTitle => 'الإنفاق';

  @override
  String get costSortByDate => 'ترتيب حسب التاريخ';

  @override
  String get costSortByAmount => 'ترتيب حسب المبلغ';

  @override
  String get costByAmount => 'حسب المبلغ';

  @override
  String get costByDate => 'حسب التاريخ (الأحدث أولًا)';

  @override
  String get costTotalKieSpend => 'إجمالي الإنفاق على KIE.AI';

  @override
  String get costRunsLabel => 'العمليات';

  @override
  String get costAvgPerRun => 'المتوسط / عملية';

  @override
  String costPercentOfTotal(String percent) {
    return '$percent % من الإجمالي';
  }

  @override
  String get costFootnote =>
      'يشمل Veo ‏(\$0.10/ثانية) + ورقة شخصيات Flux ‏(\$0.05/عملية). لا يشمل ElevenLabs ‏(~\$0.30/حلقة إن استُخدم) ولا توليد النصوص عبر Anthropic / Groq ‏(أقل من \$0.05/حلقة).';

  @override
  String videoPlayerClipTitle(String number) {
    return 'مقطع $number';
  }

  @override
  String get videoPlayerUrlCopied => 'تم نسخ رابط الفيديو — الصقه في أي مكان';

  @override
  String get videoPlayerOpenLinkToDownload =>
      'افتح الرابط في تبويب جديد للتنزيل';

  @override
  String get videoPlayerPlaybackError => 'خطأ في التشغيل';

  @override
  String get videoPlayerCantRepairBody =>
      'يتعذر إصلاح هذا الفيديو.\n\nملف mp4 تالف إلى درجة لا يمكن إصلاحها دون إعادة الرندرة. استخدم زر «إعادة التوليد» في صفحة العملية لإعادة توليد المقاطع المتأثرة.';

  @override
  String get videoPlayerBackToRun => 'العودة إلى العملية';

  @override
  String get videoPlayerRepairing => 'جارٍ إصلاح التشغيل…';

  @override
  String logViewerTitle(String runId) {
    return 'السجل — $runId';
  }

  @override
  String get logViewerCopyTooltip => 'نسخ السجل';

  @override
  String get logViewerCopied => 'تم نسخ السجل';

  @override
  String get logViewerEmpty => '(فارغ)';

  @override
  String get paywallOutOfCredits => 'نفد الرصيد';

  @override
  String paywallNeedCredits(int needed, int balance, int missing) {
    return 'يحتاج هذا الفيديو إلى $needed من الأرصدة. لديك $balance — ينقصك $missing. عبّئ رصيدك لمواصلة التوليد.';
  }

  @override
  String get paywallSavedNotice =>
      'نصّك وشخصياتك محفوظة. بعد تعبئة الرصيد، انقر «استئناف» على هذه العملية للمتابعة.';

  @override
  String get paywallTopUp => 'تعبئة الرصيد';

  @override
  String get misconfiguredTitle => 'الخادم غير مُهيّأ.';

  @override
  String get misconfiguredBody =>
      'أعد التشغيل عبر scripts/run-app.sh حتى تُدمَج روابط Supabase وواجهة API في البناء.';
}
