# Luxury Redesign — Phase 1 (Flutter App) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reskin the Flutter app end-to-end into the "Obsidian & Champagne" luxury design system, and hand-craft the AI-magic screens — without changing any functional behavior.

**Architecture:** Flip token VALUES + brand-widget rendering in the shared layer (`theme.dart`, `ui/brand.dart`) with token/widget NAMES kept stable, so every screen inherits the look for free (the `fe128e7` mechanism). Add new shared primitives, decompose the oversized `home_screen.dart` into section widgets, then hand-craft the ~4 signature screens and sweep the rest.

**Tech Stack:** Flutter (Material 3), `google_fonts`, Dart. Verification via `dart analyze` + `flutter test` + `./scripts/run-app.sh` + headless-Chrome PNG spot-checks.

**Spec:** `docs/superpowers/specs/2026-09-09-luxury-redesign-design-system.md`

**Visual target (exact look, colours, spacing):**
- `docs/superpowers/specs/redesign-artboards/DirectionA-Home.png` (+ `.dc.html` source)
- `docs/superpowers/specs/redesign-artboards/DirectionA-Composing.png` (+ `.dc.html` source)

## Global Constraints

- **No functional behavior changes.** API calls, approve/spend gates, credits, i18n keys, routing — untouched. Visual layer + behavior-preserving widget extraction only.
- **`canvasColor` / `surface` / popup / dialog grounds stay OPAQUE** = `#16151A`. (`test/dropdown_theme_test.dart` asserts `theme.canvasColor.a == 1.0`.)
- **No violet / pink / magenta** anywhere. Champagne (`#C9A96E` / `#E4CE9E`) used sparingly: hairlines, one accent word, one primary CTA, small status dots — never large gold fills.
- **Text is warm off-white `#EFE9DE`, never pure `#FFFFFF`.**
- **Bilingual + RTL parity**: every screen correct in both `ar` (Amiri/Tajawal, RTL) and `en` (Cormorant/Manrope, LTR).
- **Verification commands:** use `dart analyze <files>` (NOT `flutter analyze` — it hangs in this repo). Authed screens render blank headless — verify via `./scripts/run-app.sh` (NOT the IDE Run button — it strips `--dart-define`). The 25 existing tests must stay green.
- Keep every commit green (`dart analyze` clean + `flutter test` passing).

**Token values (copy verbatim from spec §2/§3):**
`bg #0C0B0E` · `bgDeep #08070A` · `surface #16151A` (opaque) · `surface2 #1E1C22` (opaque) · `glass rgba(255,255,255,0.03)` · `glassStrong rgba(255,255,255,0.06)` · `border rgba(238,233,222,0.10)` · `borderAccent rgba(201,169,110,0.35)` · `accent #C9A96E` · `accent2 #E4CE9E` · `accentMid #D4B483` · `accentDeep #B4915A` · `textPrimary #EFE9DE` · `textSecondary #A39C8E` · `faint #6E685D` · `success #9DBB9C` · `danger #C6564E` · `info #6E8BA6`. Fonts: display Cormorant Garamond (EN) / Amiri (AR); UI Manrope (EN) / Tajawal (AR).

---

### Task 0: Baseline & unblock

**Files:**
- Modify: `lib/main.dart:31,:105` (pre-existing invalid Dart — missing type names on `.fromSeed(...)` and `.center`)

- [ ] **Step 1: Establish the test baseline**

Run: `flutter test` and `dart analyze lib/`
Expected: note current pass count (should be 25 passing) and any pre-existing analyzer errors. Record them.

- [ ] **Step 2: Read the theme-sensitive tests** so later token edits don't break them

Read `test/dropdown_theme_test.dart` (asserts `canvasColor.a == 1.0`), `test/widget_test.dart`, `test/genre_grid_test.dart`, `test/perform_sheet_test.dart`. Note any hard-coded colour/token expectations (currently: only `canvasColor` opacity).

- [ ] **Step 3: Fix `lib/main.dart:31` and `:105`**

Read the two lines. `:31` is a `ColorScheme.fromSeed(...)` missing its seed type/arg; `:105` is a `.center` missing its widget/type. Repair them minimally so Dart parses (match the surrounding code's intent — a valid `fromSeed(seedColor: …)` and a valid `Center`/`Alignment.center`).

- [ ] **Step 4: Verify analyzer + tests**

Run: `dart analyze lib/main.dart` → Expected: no errors on those lines.
Run: `flutter test` → Expected: still 25 passing.

- [ ] **Step 5: Commit**

```bash
git add lib/main.dart
git commit -m "fix(app): repair pre-existing invalid Dart in main.dart (:31, :105)"
```

---

### Task 1: Colour + type tokens (`lib/theme.dart`)

**Files:**
- Modify: `lib/theme.dart` (values only; keep every token NAME and `build()` structure)
- Test: `test/theme_tokens_test.dart` (create)

**Interfaces:**
- Produces: `FacelessTheme.bg/surface/surface2/accent/accent2/accentMid/accentDeep/textPrimary/textSecondary/faint/success/danger/info` (Colors); `FacelessTheme.brandGradient` (champagne LinearGradient); `FacelessTheme.glass/glassStrong/border` (Colors); `FacelessTheme.borderAccent` (new Color); `FacelessTheme.display({...})` (locale-aware serif TextStyle); `FacelessTheme.build({Locale? locale})` (ThemeData).

- [ ] **Step 1: Write the failing test**

```dart
// test/theme_tokens_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:faceless/theme.dart';

void main() {
  test('palette is obsidian + champagne, no neon', () {
    expect(FacelessTheme.bg, const Color(0xFF0C0B0E));
    expect(FacelessTheme.accent, const Color(0xFFC9A96E));   // champagne
    expect(FacelessTheme.accent2, const Color(0xFFE4CE9E));
    expect(FacelessTheme.textPrimary, const Color(0xFFEFE9DE));
    // no pure white text
    expect(FacelessTheme.textPrimary, isNot(const Color(0xFFFFFFFF)));
  });

  test('dropdown ground stays opaque (drop.png invariant)', () {
    expect(FacelessTheme.build().canvasColor.a, 1.0);
    expect(FacelessTheme.surface.a, 1.0);
  });

  test('build() works for both locales', () {
    expect(FacelessTheme.build(locale: const Locale('en')), isA<ThemeData>());
    expect(FacelessTheme.build(locale: const Locale('ar')), isA<ThemeData>());
  });
}
```

- [ ] **Step 2: Run it — expect FAIL** (`accent` is still neon pink `0xFFFF4D8D`).

Run: `flutter test test/theme_tokens_test.dart`

- [ ] **Step 3: Remap the tokens.** Edit `lib/theme.dart`:
  - Replace the palette constants with the Global-Constraints values; add `static const accentDeep = Color(0xFFB4915A);` and `static Color get borderAccent => const Color(0xFFC9A96E).withValues(alpha: 0.35);`.
  - `brandGradient` colors → `[accent2, accentDeep]`.
  - `border` → `Colors.white.withValues(alpha: … )` becomes warm: `const Color(0xFFEEE9DE).withValues(alpha: 0.10)`. `glass`/`glassStrong` → 0.03 / 0.06.
  - `ColorScheme.fromSeed(seedColor: accent, …, surface: surface, primary: accent, secondary: accent2)`; keep `canvasColor: surface` (opaque).
  - **Fonts:** `display({...})` → `GoogleFonts.cormorantGaramond` for LTR, `GoogleFonts.amiri` for `ar`; body `textTheme` → `GoogleFonts.manropeTextTheme` (en) / `GoogleFonts.tajawalTextTheme` (ar), with the other as `fontFamilyFallback`. Keep the isArabic switch already in `build()`.
  - Filled/elevated buttons: `backgroundColor: surface`, `foregroundColor: accent2`, add `side: BorderSide(color: borderAccent)`.
  - `textButtonTheme` / `chipTheme` / `segmentedButtonTheme` / `inputDecorationTheme`: swap accent references (they already use `accent`, so they inherit the new champagne automatically); confirm focus border uses `accent`.

- [ ] **Step 4: Run tests — expect PASS**

Run: `flutter test test/theme_tokens_test.dart test/dropdown_theme_test.dart` → Expected: PASS.
Run: `dart analyze lib/theme.dart` → Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add lib/theme.dart test/theme_tokens_test.dart
git commit -m "feat(ui): obsidian+champagne tokens & editorial fonts (theme.dart)"
```

---

### Task 2: Brand widgets rerender (`lib/ui/brand.dart`)

**Files:**
- Modify: `lib/ui/brand.dart` (rendering only; keep NAMES `MeshBackground`, `GlassCard`, `GradientButton`, `GradientText`, `BrandPill`, `coverGradient`)
- Test: `test/brand_widgets_test.dart` (create)

**Interfaces:**
- Consumes: Task 1 tokens.
- Produces: same widget names, new look; `coverGradient(String seed) -> LinearGradient` returning colours from the jewel set only.

- [ ] **Step 1: Write the failing test**

```dart
// test/brand_widgets_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:faceless/ui/brand.dart';

const _forbidden = [0xFFFF4D8D, 0xFFA25BFF, 0xFF7C3AED, 0xFFCF54C0]; // old neon

void main() {
  testWidgets('brand widgets build', (t) async {
    await t.pumpWidget(const MaterialApp(home: Scaffold(body: MeshBackground(
      child: GlassCard(child: Text('x'))))));
    expect(find.text('x'), findsOneWidget);
  });

  test('coverGradient uses jewel set, never violet/pink', () {
    for (final s in ['a','song','رحلة','xyz','12','artist']) {
      final g = coverGradient(s);
      for (final c in g.colors) {
        expect(_forbidden.contains(c.toARGB32()), isFalse,
          reason: 'no neon in cover gradients');
      }
    }
  });
}
```

- [ ] **Step 2: Run it — expect FAIL** (old `coverGradient` contains violet/plum entries).

- [ ] **Step 3: Rerender the widgets** (mirror `redesign-artboards/DirectionA-Home.dc.html`):
  - `MeshBackground`: obsidian vertical gradient `[#0C0B0E, #08070A]` + a top champagne radial wash (`accent` @0.10) + a base teal breath (`#2E7A6E` @0.14). One optional slow "breathe" via `TweenAnimationBuilder`/implicit; static if `MediaQuery.disableAnimations`. Keep `IgnorePointer`.
  - `GlassCard`: keep `BackdropFilter(blur ~16)` + `glass` fill + `border` hairline + `softShadow`; add optional `accentEdge` bool → `borderAccent`. On web, cap to one blur layer.
  - `GradientButton`: dark ground (`glass` over `accent` @0.06) + `borderAccent` hairline + champagne label (`accent2`) + subtle inner sheen; NOT a solid gold fill. Keep `expand`, `loading`, `icon`.
  - `GradientText`: same ShaderMask, `brandGradient` (now champagne).
  - `BrandPill`: champagne-hairline pill; keep `dot`, `icon`.
  - `coverGradient`: replace `palettes` with jewel set only:
    ```dart
    const palettes = [
      [Color(0xFF233A44), Color(0xFF2E7A6E)], // teal
      [Color(0xFF3E2E1C), Color(0xFFA0762E)], // bronze
      [Color(0xFF3A1E1C), Color(0xFF7A3A2E)], // garnet
      [Color(0xFF1F3A30), Color(0xFF2E7A5C)], // emerald
    ];
    ```

- [ ] **Step 4: Run tests — expect PASS**

Run: `flutter test test/brand_widgets_test.dart` → PASS. `dart analyze lib/ui/brand.dart` → clean.

- [ ] **Step 5: Commit**

```bash
git add lib/ui/brand.dart test/brand_widgets_test.dart
git commit -m "feat(ui): luxe brand widgets (ambient bg, glass, champagne CTA, jewel covers)"
```

---

### Task 3: New shared primitives (`lib/ui/primitives.dart`)

**Files:**
- Create: `lib/ui/primitives.dart`
- Test: `test/primitives_test.dart` (create)

**Interfaces:**
- Produces: `Eyebrow(String)`, `EditorialHeading(String, {double size, bool accentLast})`, `Hairline()`, `LivingWaveform({int bars, bool animate, double height, Color? color})`, `StatusPill({required String label, required StatusKind kind})` with `enum StatusKind { ready, composing, review }`, `ArtistBadge({required String monogram, Gradient? gradient, bool alive})`, `StepList(List<StepItem>)` with `class StepItem { final String label; final StepState state; final int? percent; }` and `enum StepState { done, active, pending }`.

- [ ] **Step 1: Write the failing test**

```dart
// test/primitives_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:faceless/ui/primitives.dart';

void main() {
  testWidgets('LivingWaveform renders the requested bar count', (t) async {
    await t.pumpWidget(const MaterialApp(home: Scaffold(
      body: LivingWaveform(bars: 18, animate: false))));
    expect(find.byType(LivingWaveform), findsOneWidget);
    // 18 bar containers
    expect(tester_barCount(t), 18);
  });

  testWidgets('StatusPill shows its label', (t) async {
    await t.pumpWidget(const MaterialApp(home: Scaffold(
      body: StatusPill(label: 'Composing', kind: StatusKind.composing))));
    expect(find.text('Composing'), findsOneWidget);
  });

  testWidgets('StepList renders one row per item', (t) async {
    await t.pumpWidget(MaterialApp(home: Scaffold(body: StepList(const [
      StepItem(label: 'Analyse', state: StepState.done),
      StepItem(label: 'Melody', state: StepState.active, percent: 40),
      StepItem(label: 'Cover', state: StepState.pending),
    ]))));
    expect(find.text('Analyse'), findsOneWidget);
    expect(find.text('Melody'), findsOneWidget);
    expect(find.text('Cover'), findsOneWidget);
  });
}

int tester_barCount(WidgetTester t) =>
  t.widgetList(find.byKey(const ValueKey('wavebar'))).length;
```

- [ ] **Step 2: Run it — expect FAIL** (file/classes don't exist).

- [ ] **Step 3: Implement `lib/ui/primitives.dart`** mirroring the artboards:
  - `Eyebrow`: Manrope (Tajawal for AR), 10.5px, `letterSpacing 0.30em` (Latin), uppercase, `textSecondary`.
  - `EditorialHeading`: `FacelessTheme.display(...)` serif; `accentLast` wraps the final word in `GradientText`.
  - `Hairline`: 1px `border` divider.
  - `LivingWaveform`: a `Row` of thin bars (each `Container` with `key: ValueKey('wavebar')`, width ~2.5, champagne gradient, varying height); when `animate`, one `AnimationController` drives opacity/`scaleY` with per-bar staggered phase; honour `MediaQuery.disableAnimations`.
  - `StatusPill` + dot: `ready`→sage dot + "muted"; `composing`→pulsing `accent2` dot; `review`→`borderAccent` outline pill.
  - `ArtistBadge`: gradient circle + serif monogram; `alive` adds a pulsing champagne halo.
  - `StepList`/`StepItem`/`StepState`: done→champagne check; active→halo dot + optional `percent` + highlighted row; pending→hollow ring, dimmed. RTL-aware (use `EdgeInsetsDirectional`, `Directionality`).

- [ ] **Step 4: Run tests — expect PASS.** `dart analyze lib/ui/primitives.dart` → clean.

- [ ] **Step 5: Commit**

```bash
git add lib/ui/primitives.dart test/primitives_test.dart
git commit -m "feat(ui): shared luxe primitives (waveform, status, steps, editorial heading)"
```

---

### Task 4: Decompose + reskin the home screen

**Files:**
- Create: `lib/widgets/home/home_header.dart`, `hero_greeting.dart`, `compose_cta.dart`, `artists_row.dart`, `latest_release_card.dart`, `song_row.dart`, `trending_section.dart`, `morning_drafts_section.dart`, `llm_banner.dart`
- Modify: `lib/screens/home_screen.dart` (extract sections; keep ALL state/logic/i18n)

**Interfaces:**
- Consumes: Tasks 1–3. Each section widget receives already-fetched data + callbacks from `_HomeScreenState` (no new data fetching in the widgets).

- [ ] **Step 1: Extract behavior-preserving section widgets.** Move each home section's *build* code into its own stateless widget, passing in the data/futures/callbacks it currently reads from `_HomeScreenState`. Do NOT move fetching or state — the screen still owns `_runsFuture/_songsFuture/_artistsFuture/_trendsFuture/_spend/_plan/_filter/_songQuery/_llmDegraded`.

- [ ] **Step 2: Reskin each section** to `redesign-artboards/DirectionA-Home.png`: `HomeHeader` (wordmark + champagne credits `BrandPill` + settings), `HeroGreeting` (`Eyebrow` + `EditorialHeading` with accent word), `ComposeCTA` (`GradientButton` full-width), `ArtistsRow` (`ArtistBadge` + add), `LatestReleaseCard` (jewel cover + `LivingWaveform` + play), `SongRow` (cover + serif title + `StatusPill`), trending/drafts/banner reskinned with primitives.

- [ ] **Step 3: Verify no behavior/i18n regressions**

Run: `flutter test` → Expected: 25 still pass (home isn't unit-tested but ensure no compile breakage). `dart analyze lib/screens/home_screen.dart lib/widgets/home/` → clean.

- [ ] **Step 4: Visual check (both locales)**

Run: `./scripts/run-app.sh` — walk the home screen in EN and AR (switch language in Settings). Confirm: champagne restraint, serif hero, RTL correct, no violet, credits/artists/songs render, dropdowns still opaque.

- [ ] **Step 5: Commit**

```bash
git add lib/screens/home_screen.dart lib/widgets/home/
git commit -m "feat(ui): decompose + reskin home into luxe section widgets"
```

---

### Task 5: Composing — the signature AI-magic screen

**Files:**
- Modify: `lib/screens/run_detail_screen.dart` (and/or a dedicated composing view it routes to)

**Interfaces:** Consumes Tasks 1–3 (esp. `LivingWaveform`, `StepList`, `ArtistBadge(alive:true)`).

- [ ] **Step 1: Rebuild the in-progress state** to match `redesign-artboards/DirectionA-Composing.png`: `ArtistBadge(alive:true)` with halo → `Eyebrow` ("جارٍ الآن" / "Now") → `EditorialHeading` accent word ("أغنيتك" / "sing") → artist·title → `LivingWaveform(animate:true)` → `StepList` mapped from the real run statuses (`statusAnalyzing` → lyrics → `statusGeneratingSong` → `statusGeneratingCover` → `statusAssembling`) with the active step's percent when available → footer ETA + "we'll notify you". Keep the existing polling/refresh and the cancel action.
- [ ] **Step 2:** Map every status string to a `StepItem` via the existing l10n keys (`context.l10n.status*`). Preserve failure/awaiting-approval/complete states (route to their existing screens).
- [ ] **Step 3: Verify** `dart analyze` clean; `flutter test` green.
- [ ] **Step 4: Visual check** a live/awaiting run via `./scripts/run-app.sh` in AR + EN; confirm animation is smooth on web and respects reduced-motion.
- [ ] **Step 5: Commit** `feat(ui): cinematic composing screen (living waveform + step list)`

---

### Task 6: Artist comes alive (`lib/screens/artist_screen.dart`)

- [ ] **Step 1:** Reskin as an editorial artist page: `ArtistBadge(alive:true)` reveal, serif name (`EditorialHeading`), `Eyebrow`-labelled sections (voice, discography, earnings), `SongRow` list, champagne hairlines. Keep all data/actions (edit, publish toggles, public page link).
- [ ] **Step 2:** Staggered `TweenAnimationBuilder` entrance on first load (reduced-motion aware).
- [ ] **Step 3:** `dart analyze` clean; `flutter test` green.
- [ ] **Step 4:** Visual check AR + EN via `run-app.sh`.
- [ ] **Step 5: Commit** `feat(ui): editorial 'artist comes alive' screen`

---

### Task 7: Lyric reveal (`lib/screens/song_approve_screen.dart`, `edit_script_screen.dart`)

- [ ] **Step 1:** Render Arabic/English lyric lines in the editorial serif (`FacelessTheme.display`), fading in line-by-line (staggered, reduced-motion aware). This is the pay-gate review moment — keep the cost estimate, approve, and edit actions exactly as they are.
- [ ] **Step 2:** Reskin the cost/approve controls with `GradientButton` (approve) + champagne hairlines; keep the dollar-figure + "no lip sync" disclosures verbatim.
- [ ] **Step 3:** `dart analyze` clean; `flutter test` green (esp. anything covering approve flow).
- [ ] **Step 4:** Visual check AR + EN.
- [ ] **Step 5: Commit** `feat(ui): editorial lyric-reveal on the approve/edit screens`

---

### Task 8: Cover materialising (`lib/screens/song_detail_screen.dart`)

- [ ] **Step 1:** When a cover image resolves, reveal it with a champagne shimmer/fade (placeholder = `coverGradient`). Reskin the detail page: serif title, `StatusPill`, `LivingWaveform` for the player, champagne controls. Keep play/download/release/publish actions.
- [ ] **Step 2:** `dart analyze` clean; `flutter test` green.
- [ ] **Step 3:** Visual check AR + EN.
- [ ] **Step 4: Commit** `feat(ui): cover-materialise reveal + luxe song detail`

---

### Task 9: Leftover sweep (remaining screens)

**Files (reskin, inherit-first — only touch where a leftover shows):** `login_screen.dart`, `landing_screen.dart`, `onboarding_screen.dart`, `new_song_screen.dart`, `new_run_screen.dart`, `settings_screen.dart`, `billing_screen.dart`, `cost_screen.dart`, `transactions_screen.dart`, `personas_screen.dart`, `artist_edit_screen.dart`, `reset_password_screen.dart`, `legal_screen.dart`, `log_viewer_screen.dart`, `video_player_screen.dart`; widgets `paywall_dialog.dart`, `perform_sheet.dart`, `genre_grid.dart`, `artist_avatar.dart`, `faceless_logo.dart`.

- [ ] **Step 1:** Audit each for hard-coded old-era literals (grep for the old neon hexes `FF4D8D`, `A25BFF`, `7C3AED`, `CF54C0`, `Space Grotesk`, pure-white `0xFFFFFFFF` text). Replace with tokens/primitives. Most will already be carried by the token flip (last redesign found only one real leftover).
- [ ] **Step 2:** Apply primitives where each screen has an eyebrow/heading/CTA/status/waveform.
- [ ] **Step 3:** `dart analyze lib/` fully clean; `flutter test` → 25 green.
- [ ] **Step 4:** Visual check the high-traffic ones (login, landing, settings, billing, new_song, onboarding) AR + EN.
- [ ] **Step 5: Commit** `feat(ui): luxe sweep across remaining screens & dialogs`

---

### Task 10: Full verification & branch finish

- [ ] **Step 1:** `dart analyze lib/ test/` → zero errors.
- [ ] **Step 2:** `flutter test` → all green (25 + the new theme/brand/primitives tests).
- [ ] **Step 3:** `./scripts/run-app.sh` — full walkthrough in **AR (RTL)** and **EN (LTR)**: home → new song → composing → approve/lyrics → song detail → artist → billing → settings. Confirm the guardrails (opaque dropdowns, champagne restraint, no violet, warm-white text, smooth/reduced-motion).
- [ ] **Step 4:** Headless-Chrome PNG spot-checks of logged-out screens (landing/login), sampling pixels to confirm obsidian bg + champagne accents.
- [ ] **Step 5:** Invoke **superpowers:finishing-a-development-branch** to decide merge/PR.

---

## Self-Review

**Spec coverage:** §2 tokens → T1; §3 type → T1; §4.1 theme → T1; §4.2 brand → T2; §4.3 primitives → T3; §5 motion → T2/T3 + used in T5–T8; §6 magic moments → T5 (composing), T6 (artist), T7 (lyric reveal), T8 (cover); §7 decomposition → T4; §8 phase-1 order → T0–T10; §9 verification → T0/T10 + per-task; §10 risks (blur perf, fonts, reduced-motion) → T2/T3/T5. Website (§8 Phase 2) and touchpoints (Phase 3) are intentionally out of scope — separate plans. No gaps.

**Placeholder scan:** token values are given verbatim; test code is concrete; reskin tasks point at the committed artboard PNG/HTML as the exact visual source and name the primitives/tokens to apply (not "make it nice"). Acceptable for an app-wide reskin where per-widget code = the implementation itself.

**Type consistency:** `StatusKind{ready,composing,review}`, `StepItem{label,state,percent}`, `StepState{done,active,pending}`, `LivingWaveform(bars:,animate:,height:,color:)`, `ArtistBadge(monogram:,gradient:,alive:)`, `EditorialHeading(text,{size,accentLast})` — used consistently in T3 (defined) and T4–T8 (consumed). `FacelessTheme.borderAccent`/`accentDeep` added in T1 and used in T2. Consistent.
