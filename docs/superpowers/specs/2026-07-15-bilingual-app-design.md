# Full Bilingual App (Arabic / English) — Design Spec

**Date:** 2026-07-15
**Status:** Approved (walked through with user)
**Context:** Sub-project 1 of the Virtual Artist Label direction (order agreed:
i18n → Artist Core → Distribution). The app today is a mix — English UI chrome,
Arabic content, some Arabic labels — the user wants **two fully supported
languages, no mixing**.

## Goal

Every user-facing string in the Flutter app renders fully in the user's chosen
language — Arabic or English — with correct RTL layout for Arabic. No screen
shows a language the user didn't pick.

## Decisions (resolved during brainstorming)

| # | Question | Decision |
|---|---|---|
| 1 | Sub-project order | i18n first, so Artist Core screens are born bilingual |
| 2 | Language selection | Follow device on first launch; in-app switcher (Settings + landing) overrides; persisted; instant switch (no restart) |
| 3 | Mechanism | Flutter official `gen-l10n` (ARB files, compile-time-safe) over `easy_localization` (runtime keys) or hand-rolled maps |
| 4 | Backend text | Statuses/known error hints are stable codes → translated client-side; raw/unknown errors show as-is; API stays English-internal |
| 5 | Song lyrics language | Stays the per-song setting; UI language only becomes its default |

## Architecture

### 1. Translation infrastructure
- `flutter_localizations` (SDK) + `gen-l10n` via `l10n.yaml`.
- `lib/l10n/app_en.arb` (template) + `lib/l10n/app_ar.arb`.
- Generated `AppLocalizations` accessed as `context.l10n` via a small
  extension (`lib/l10n/l10n.dart`).
- ALL hardcoded UI strings (~205+ across 17 screens + widgets) move to keys.
  Naming: `screenElement` camelCase (e.g. `homeYourSongs`, `newSongGenerateCta`).
- Placeholders for dynamic values (`{count}`, `{credits}`, `{title}`) instead
  of string interpolation.

### 2. Locale state
- `LocaleController` (`lib/l10n/locale_controller.dart`): a
  `ValueNotifier<Locale?>` — `null` = follow device. Persisted in
  `shared_preferences` under `faceless.locale` (`'ar' | 'en'`, absent = follow
  device).
- `MaterialApp`: `supportedLocales: [en, ar]`,
  `localizationsDelegates: AppLocalizations.localizationsDelegates`, `locale`
  bound to the controller (rebuild on change → instant switch).

### 3. RTL correctness
- Arabic locale flips layout automatically via `Directionality`.
- Sweep: replace direction-sensitive `EdgeInsets.only(left:/right:)`,
  `Alignment.centerLeft/Right`, `Positioned(left:/right:)` (where mirroring is
  wanted) with `EdgeInsetsDirectional` / `AlignmentDirectional` /
  `PositionedDirectional`. Media/cover art and play icons do NOT mirror.
- Existing explicit `textDirection: TextDirection.rtl` on Arabic *content*
  (song titles) stays — content direction is driven by the content's language,
  not the UI locale.

### 4. Typography per locale
- Arabic UI: **Cairo** becomes the primary font (currently only a fallback);
  English UI: Inter body + Space Grotesk display (unchanged).
- `FacelessTheme.build(locale)` picks the family; `display()` keeps Cairo
  fallback so mixed-script lines still render.

### 5. Language switcher UI
- Settings: a "Language / اللغة" row with three options — Auto (device),
  العربية, English.
- Landing page nav: compact 🌐 toggle (ar ⇄ en) for pre-auth visitors.

### 6. Backend-originated text
- Run/song **status codes** (`analyzing`, `awaiting_approval`, `generating_song`,
  `assembling`, `complete`, `failed`, …) map to localized labels client-side
  (extend the existing `_songStatusStyle` pattern to read from ARB).
- Known API error hints keep stable substrings → client maps them to localized
  messages; anything unrecognized displays raw (operator/debug text).

### 7. Content language (unchanged behavior)
- The per-song `language` field continues to control lyrics/Suno language.
- Its default value in the New Song form = current UI locale.

## Error handling
- Missing translation = **build failure** (gen-l10n `untranslated-messages-file`
  check + a CI-style test asserting `app_en.arb` and `app_ar.arb` key parity).
- Corrupt/unknown persisted locale value → treated as `null` (follow device).

## Testing
- Unit: ARB key parity (both files expose identical key sets, no empty values).
- Widget: pump key screens (landing, home scaffold, new song, settings) under
  `Locale('ar')` → assert a known Arabic string is present and
  `Directionality.of == rtl`; same under `Locale('en')` for English.
- Widget: switching the controller rebuilds with the other language without
  restart.
- Existing tests must stay green (`flutter analyze` zero errors; `flutter test`).

## Explicit non-goals
- No backend/API localization (English-internal logs and payloads unchanged).
- No third language; no per-string A/B copy work — a faithful translation pass.
- No redesign of screens (the light theme ships as-is; this is a strings +
  direction pass).

## Rollout
Single PR/merge to `main`, deployed via the standard clean
`flutter clean && ./scripts/build-and-push.sh` (stale-cache lesson applies).
