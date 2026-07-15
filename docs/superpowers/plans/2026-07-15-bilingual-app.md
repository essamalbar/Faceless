# Full Bilingual App (AR/EN) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every user-facing string in the Flutter app renders fully in the chosen language (Arabic or English) with correct RTL for Arabic, an instant in-app switcher, and build-time-enforced translation completeness.

**Architecture:** Flutter official `gen-l10n` (ARB files → generated `AppLocalizations`), a persisted `LocaleController` (`ValueNotifier<Locale?>`, null = follow device) bound to `MaterialApp.locale`, per-locale font selection in `FacelessTheme.build`, and a mechanical sweep converting hardcoded strings → l10n keys and direction-sensitive geometry → `*Directional` variants.

**Tech Stack:** flutter_localizations (SDK), intl (already present), gen-l10n, shared_preferences (already present), google_fonts (already present).

**Spec:** `docs/superpowers/specs/2026-07-15-bilingual-app-design.md`

---

## File structure

| File | Responsibility |
|---|---|
| `l10n.yaml` (new) | gen-l10n config (arb dir, template, output) |
| `lib/l10n/app_en.arb` (new) | English template — source of truth for keys |
| `lib/l10n/app_ar.arb` (new) | Arabic translations — must mirror every key |
| `lib/l10n/l10n.dart` (new) | `context.l10n` extension + `LocaleController` (persisted ValueNotifier) |
| `lib/main.dart` | localizationsDelegates/supportedLocales/locale wiring, rebuild on switch |
| `lib/theme.dart` | `build(Locale?)` — Cairo primary for ar, Inter/SpaceGrotesk for en |
| `lib/screens/*.dart` (17 files) | strings → `context.l10n.*`; geometry → Directional |
| `lib/widgets/*.dart` | same sweep |
| `lib/screens/settings_screen.dart` | Language row (Auto/العربية/English) |
| `lib/screens/landing_screen.dart` | nav 🌐 toggle |
| `test/l10n_test.dart` (new) | ARB key parity + no empty values |
| `test/locale_switch_test.dart` (new) | ar renders Arabic + RTL; en renders English; live switch |

## Conventions (used by every task)

- **Key naming:** `<screen><Element>` camelCase — `homeYourSongs`, `newSongThemeLabel`, `settingsLanguage`, `commonCancel` for cross-screen strings.
- **Placeholders**, never interpolation: `"creditsPill": "✦ {count} credits"` with `"placeholders": {"count": {"type": "int"}}` → `l10n.creditsPill(248)`.
- **Do not translate:** log strings, API payload values, debug-only text, Arabic *content* (song titles from data), font family names.
- **Access:** `final l10n = context.l10n;` at the top of `build`, or inline `context.l10n.key`. Where no `BuildContext` exists (rare), thread the `AppLocalizations` object in.
- After each task: `flutter analyze <files>` → 0 errors, `flutter gen-l10n` regenerates cleanly, commit.

---

### Task 1: gen-l10n infrastructure + LocaleController

**Files:** Create `l10n.yaml`, `lib/l10n/app_en.arb`, `lib/l10n/app_ar.arb`, `lib/l10n/l10n.dart`; Modify `pubspec.yaml`, `lib/main.dart`, `lib/theme.dart`.

- [ ] **Step 1: pubspec + l10n.yaml**

`pubspec.yaml` — add under dependencies and enable generation:
```yaml
  flutter_localizations:
    sdk: flutter
```
and under the existing `flutter:` section:
```yaml
flutter:
  generate: true
```
`l10n.yaml` (repo root):
```yaml
arb-dir: lib/l10n
template-arb-file: app_en.arb
output-localization-file: app_localizations.dart
untranslated-messages-file: build/untranslated.json
```

- [ ] **Step 2: seed ARB files (structure + first strings)**

`lib/l10n/app_en.arb`:
```json
{
  "@@locale": "en",
  "appTitle": "Faceless Lab",
  "commonCancel": "Cancel",
  "commonSave": "Save",
  "commonRetry": "Retry",
  "commonClose": "Close",
  "settingsLanguage": "Language",
  "settingsLanguageAuto": "Auto (device)",
  "statusAnalyzing": "Analyzing",
  "statusAwaitingApproval": "Awaiting approval",
  "statusGeneratingSong": "Generating song",
  "statusGeneratingCover": "Generating cover",
  "statusAssembling": "Assembling",
  "statusComplete": "Complete",
  "statusFailed": "Failed"
}
```
`lib/l10n/app_ar.arb`:
```json
{
  "@@locale": "ar",
  "appTitle": "فيسلس لاب",
  "commonCancel": "إلغاء",
  "commonSave": "حفظ",
  "commonRetry": "إعادة المحاولة",
  "commonClose": "إغلاق",
  "settingsLanguage": "اللغة",
  "settingsLanguageAuto": "تلقائي (لغة الجهاز)",
  "statusAnalyzing": "جارٍ التحليل",
  "statusAwaitingApproval": "بانتظار الموافقة",
  "statusGeneratingSong": "جارٍ توليد الأغنية",
  "statusGeneratingCover": "جارٍ توليد الغلاف",
  "statusAssembling": "جارٍ التجميع",
  "statusComplete": "مكتملة",
  "statusFailed": "فشلت"
}
```

- [ ] **Step 3: `lib/l10n/l10n.dart`**

```dart
/// l10n access + persisted locale choice.
library;

import 'package:flutter/material.dart';
import 'package:flutter_gen/gen_l10n/app_localizations.dart';
import 'package:shared_preferences/shared_preferences.dart';

export 'package:flutter_gen/gen_l10n/app_localizations.dart';

extension L10nX on BuildContext {
  AppLocalizations get l10n => AppLocalizations.of(this)!;
}

/// App-wide locale override. null = follow device. Persisted.
class LocaleController extends ValueNotifier<Locale?> {
  LocaleController._(super.value);
  static const _prefsKey = 'faceless.locale';
  static final LocaleController instance = LocaleController._(null);

  static Future<void> load() async {
    final sp = await SharedPreferences.getInstance();
    final code = sp.getString(_prefsKey);
    if (code == 'ar' || code == 'en') {
      instance.value = Locale(code!);
    }
  }

  Future<void> set(Locale? locale) async {
    value = locale;
    final sp = await SharedPreferences.getInstance();
    if (locale == null) {
      await sp.remove(_prefsKey);
    } else {
      await sp.setString(_prefsKey, locale.languageCode);
    }
  }
}
```
(If the Flutter version generates into `lib/l10n/` instead of `flutter_gen`, adjust the import to `app_localizations.dart` — check `flutter gen-l10n` output.)

- [ ] **Step 4: wire `lib/main.dart`**

In `main()` before `runApp`: `await LocaleController.load();`
Wrap `MaterialApp` in a `ValueListenableBuilder<Locale?>`:
```dart
return ValueListenableBuilder<Locale?>(
  valueListenable: LocaleController.instance,
  builder: (context, locale, _) => MaterialApp(
    title: 'Faceless',
    debugShowCheckedModeBanner: false,
    theme: FacelessTheme.build(locale: locale),
    locale: locale,
    supportedLocales: const [Locale('en'), Locale('ar')],
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    builder: (context, child) => MeshBackground(child: child ?? const SizedBox()),
    home: /* existing */,
  ),
);
```

- [ ] **Step 5: per-locale fonts in `lib/theme.dart`**

`build({Locale? locale})`: when `locale?.languageCode == 'ar'` use
`GoogleFonts.cairoTextTheme(base.textTheme)` (fallback Inter) and make
`display()` accept the same switch (Cairo bold for display in ar). Keep the
existing English path untouched. All existing `FacelessTheme.build()` callers
compile because the parameter is optional.

- [ ] **Step 6: verify + commit**

Run: `flutter gen-l10n && flutter analyze lib/` → 0 errors.
Commit: `feat(i18n): gen-l10n infrastructure + persisted LocaleController`

### Task 2: parity + locale-switch tests (TDD for the sweep)

**Files:** Create `test/l10n_test.dart`, `test/locale_switch_test.dart`.

- [ ] **Step 1: parity test**

```dart
import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('ARB files have identical keys and no empty values', () {
    final en = jsonDecode(File('lib/l10n/app_en.arb').readAsStringSync()) as Map<String, dynamic>;
    final ar = jsonDecode(File('lib/l10n/app_ar.arb').readAsStringSync()) as Map<String, dynamic>;
    Set<String> keys(Map<String, dynamic> m) =>
        m.keys.where((k) => !k.startsWith('@')).toSet();
    expect(keys(ar), keys(en), reason: 'ar/en key sets must match');
    for (final m in [en, ar]) {
      for (final e in m.entries) {
        if (e.key.startsWith('@')) continue;
        expect((e.value as String).trim(), isNotEmpty, reason: '${e.key} empty');
      }
    }
  });
}
```

- [ ] **Step 2: locale switch widget test**

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:faceless/l10n/l10n.dart';

void main() {
  testWidgets('ar locale renders Arabic + RTL; switch flips live', (t) async {
    Widget app(Locale? l) => MaterialApp(
      locale: l,
      supportedLocales: const [Locale('en'), Locale('ar')],
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      home: Builder(builder: (c) => Scaffold(
        body: Text(c.l10n.settingsLanguage,
            key: const Key('probe')))),
    );
    await t.pumpWidget(app(const Locale('ar')));
    await t.pumpAndSettle();
    expect(find.text('اللغة'), findsOneWidget);
    final ctx = t.element(find.byKey(const Key('probe')));
    expect(Directionality.of(ctx), TextDirection.rtl);
    await t.pumpWidget(app(const Locale('en')));
    await t.pumpAndSettle();
    expect(find.text('Language'), findsOneWidget);
  });
}
```

- [ ] **Step 3: run + commit**

Run: `flutter test test/l10n_test.dart test/locale_switch_test.dart` → PASS.
Commit: `test(i18n): ARB parity + locale switch tests`

### Task 3–8: string extraction sweeps (per screen group)

Each sweep task follows the same recipe. Groups (by size/coupling):
- **Task 3:** `home_screen.dart` (~3000 lines, biggest)
- **Task 4:** `new_song_screen.dart`, `song_approve_screen.dart`, `song_detail_screen.dart`
- **Task 5:** `landing_screen.dart`, `login_screen.dart`, `onboarding_screen.dart`
- **Task 6:** `settings_screen.dart`, `billing_screen.dart`, `transactions_screen.dart`, `personas_screen.dart`
- **Task 7:** `new_run_screen.dart`, `run_detail_screen.dart`, `edit_script_screen.dart`, `cost_screen.dart`
- **Task 8:** `video_player_screen.dart`, `log_viewer_screen.dart`, `lib/widgets/*.dart`, `lib/main.dart` (_MisconfiguredScreen)

**Recipe for every sweep task:**

- [ ] **Step 1: enumerate candidates**

Run: `grep -nE "'[A-Z][A-Za-z]|\"[A-Z][A-Za-z]|labelText:|hintText:|tooltip:|title: Text|label: Text" lib/screens/<file>.dart`
Every user-visible literal must move; skip log/debug/API values per Conventions.

- [ ] **Step 2: add keys to BOTH arb files** (en text = the current literal; ar = faithful Arabic translation). Interpolations become placeholders:

Before: `Text('You have $n songs')`
ARB en: `"homeSongCount": "You have {n} songs", "@homeSongCount": {"placeholders": {"n": {"type": "int"}}}`
ARB ar: `"homeSongCount": "لديك {n} أغنية"`
After: `Text(context.l10n.homeSongCount(n))`

Before: `decoration: const InputDecoration(labelText: 'Theme')`
After (const must drop): `decoration: InputDecoration(labelText: context.l10n.newSongThemeLabel)`

- [ ] **Step 3: regenerate + analyze**

Run: `flutter gen-l10n && flutter analyze lib/screens/<file>.dart` → 0 errors; `flutter test test/l10n_test.dart` → parity holds.

- [ ] **Step 4: commit** — `feat(i18n): localize <screens>`

### Task 9: RTL geometry sweep

**Files:** all `lib/screens/*.dart`, `lib/ui/brand.dart`, `lib/widgets/*.dart`.

- [ ] **Step 1: enumerate**

Run: `grep -rnE "EdgeInsets\.only\((left|right)|Alignment\.center(Left|Right)|Alignment\.(top|bottom)(Left|Right)|Positioned\((\s*)(left|right)" lib/`

- [ ] **Step 2: convert where mirroring is correct**

`EdgeInsets.only(left: 16)` → `EdgeInsetsDirectional.only(start: 16)`;
`Alignment.centerLeft` → `AlignmentDirectional.centerStart`;
`Positioned(left: 12, …)` → `PositionedDirectional(start: 12, …)`.
Do NOT convert: video/canvas overlays tied to media geometry, cover-art badges, waveform painting. Existing `textDirection: TextDirection.rtl` on Arabic content stays.

- [ ] **Step 3: analyze + commit** — `feat(i18n): direction-aware geometry for RTL`

### Task 10: language switcher UI

**Files:** Modify `lib/screens/settings_screen.dart`, `lib/screens/landing_screen.dart`.

- [ ] **Step 1: Settings row** (in the account/general section):

```dart
ListTile(
  leading: const Icon(Icons.language),
  title: Text(context.l10n.settingsLanguage),
  trailing: DropdownButton<String>(
    value: LocaleController.instance.value?.languageCode ?? 'auto',
    items: [
      DropdownMenuItem(value: 'auto', child: Text(context.l10n.settingsLanguageAuto)),
      const DropdownMenuItem(value: 'ar', child: Text('العربية')),
      const DropdownMenuItem(value: 'en', child: Text('English')),
    ],
    onChanged: (v) => LocaleController.instance
        .set(v == null || v == 'auto' ? null : Locale(v)),
  ),
),
```

- [ ] **Step 2: Landing nav toggle** (next to Sign in):

```dart
TextButton.icon(
  icon: const Icon(Icons.language, size: 18),
  label: Text(Localizations.localeOf(context).languageCode == 'ar' ? 'EN' : 'العربية'),
  onPressed: () {
    final cur = Localizations.localeOf(context).languageCode;
    LocaleController.instance.set(Locale(cur == 'ar' ? 'en' : 'ar'));
  },
),
```

- [ ] **Step 3: analyze + commit** — `feat(i18n): language switcher (settings + landing)`

### Task 11: status/error label mapping

**Files:** Modify the status-label helpers in `lib/screens/home_screen.dart` (`_songStatusStyle`) and wherever raw `status` strings render (`song_detail_screen.dart`, `run_detail_screen.dart`, `song_approve_screen.dart`).

- [ ] **Step 1:** add a shared mapper in `lib/l10n/l10n.dart`:

```dart
String statusLabel(AppLocalizations l10n, String status) => switch (status) {
      'analyzing' => l10n.statusAnalyzing,
      'awaiting_approval' => l10n.statusAwaitingApproval,
      'generating_song' => l10n.statusGeneratingSong,
      'generating_cover' => l10n.statusGeneratingCover,
      'assembling' => l10n.statusAssembling,
      'complete' => l10n.statusComplete,
      'failed' => l10n.statusFailed,
      _ => status, // unknown codes show raw (debug text)
    };
```

- [ ] **Step 2:** replace raw status renders with `statusLabel(context.l10n, status)`; keep pill colors keyed off the raw code. Analyze + commit — `feat(i18n): localized status labels`.

### Task 12: full verification + visual proof + deploy

- [ ] **Step 1:** `flutter gen-l10n && flutter analyze lib/` → 0 errors; `flutter test` → all pass; `build/untranslated.json` empty (`{}` or absent).
- [ ] **Step 2:** grep for stragglers: `grep -rnE "Text\('[A-Z][a-z]+" lib/screens lib/widgets | grep -v l10n` → only justified hits (log/debug).
- [ ] **Step 3:** visual proof — build web, serve, and headless-screenshot the landing with `?lang` forced both ways (or by patching localStorage locale): confirm Arabic landing renders RTL with Cairo, English unchanged. (Established pipeline: `flutter build web` → `python3 -m http.server` → headless Chrome `--screenshot`.)
- [ ] **Step 4:** commit, push (`gh auth switch --user essamalbar` first), then clean deploy: `flutter clean && flutter pub get && ./scripts/build-and-push.sh`; verify live bundle md5 changed.

---

## Self-review

- **Spec coverage:** infra (§1→T1), locale state (§2→T1), RTL (§3→T9), fonts (§4→T1.5), switcher (§5→T10), backend text (§6→T11), content language unchanged (§7 — no task needed, behavior untouched), error handling (§ tests→T2/T12), testing (§→T2, T12). ✔
- **Placeholders:** sweep tasks give recipe + worked examples instead of listing all 205 strings — deliberate; the executor has codebase access and the parity test enforces completeness. ✔
- **Type consistency:** `LocaleController.instance.set(Locale?)`, `context.l10n`, `FacelessTheme.build({Locale? locale})`, `statusLabel(AppLocalizations, String)` used consistently. ✔
