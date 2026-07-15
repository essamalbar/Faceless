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
}
