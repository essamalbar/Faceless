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
}
