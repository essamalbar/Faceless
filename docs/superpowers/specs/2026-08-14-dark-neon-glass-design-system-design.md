# Dark-Neon Glass Design System

- **Date:** 2026-08-14
- **Status:** Approved (design) — implementing this phase directly
- **Surface:** Flutter app (`lib/theme.dart`, `lib/ui/brand.dart`, + the shared-component consumers)
- **Origin:** User pivot to an InsMelo-style **glassy dark-neon** aesthetic (pink→purple), replacing the current light/glass theme, validated on real-screen mockups.

---

## 1. Summary

Flip the app from the current **light/glass** look to a **glassy dark-neon** design system: near-black background lit by blurred pink/purple/cyan glow, frosted translucent cards with bright glass edges, a pink→purple gradient for primary actions and selection, Space Grotesk display + Inter/Cairo body.

**Strategy (the whole point):** the design system lives in two files that every screen already consumes — `FacelessTheme` tokens (`lib/theme.dart`) and shared widgets (`lib/ui/brand.dart`). **Keep the token and widget NAMES identical; change only their VALUES/rendering.** The app then flips through the shared layer with near-zero screen edits. Screens that hardcode light colors are the exception and are handled by a bounded straggler pass (this phase covers the first-run path; the rest is Phase B).

This is **Phase A** of a larger program (A = design system → B = migrate all screens + UX pass → C = "Make me sing this" photo→video feature). This spec is **A only**.

## 2. Goals

- Every screen that uses `FacelessTheme.*` tokens or the `brand.dart` widgets renders dark-neon glass **without being edited**.
- **Zero unreadable text on the first-run path** (landing/login → home → create → song detail). This is the acceptance bar — usability, not polish.
- Solid, opaque dark surfaces where the framework paints menus (dropdowns/popups/dialogs) — no see-through regressions.
- Arabic/RTL and existing widget tests keep passing (fix any test asserting a light-specific value).

## 3. Non-goals (explicit)

- **Not** a comprehensive per-screen polish of all 21 screens — only the first-run path must be *usable* this phase; the remaining ~17 screens' straggler cleanup + the UX pass are **Phase B**.
- **Not** the photo→video feature (Phase C).
- **No new navigation, no new components** beyond repurposing the existing shared widgets (a `NeonNav` etc. arrives with Phase B screen work).
- **No deploy.** "Implement" ends at local verification; the on-device QA + any prod deploy are a separate, user-gated step.

## 4. Current state (ground truth) & straggler measurement

- `lib/theme.dart` — `FacelessTheme`: light palette constants (`bg,surface,surface2,accent,accent2,accentMid,ink,textPrimary,textSecondary,faint,danger,success,warning,info`), `brandGradient` (green→teal), `glass/glassStrong/border/softShadow` getters, `display()` helper, `build({locale})` → `ThemeData.light` with all component sub-themes, legacy `heroGradient`/`cardGradient`.
- `lib/ui/brand.dart` — `MeshBackground` (pastel gradient + radial blobs), `GlassCard` (frosted white + `BackdropFilter` blur), `GradientButton` (**solid ink** fill today — name already non-literal), `GradientText` (green→teal shader), `BrandPill` (white pill), `coverGradient(seed)` (6 pastel pairs).
- `lib/ui/song_genres.dart` — 12 genre tiles carry **pastel light gradient pairs as data**.
- `lib/widgets/genre_grid.dart` — tile label `Color(0xFF3A2F36)` + unselected border `Colors.white.withValues(alpha:0.6)`.
- `main.dart` wraps the app in `MeshBackground` and uses `FacelessTheme.build()` — inherits the flip automatically.

**Straggler scope (measured):** 21 screens, **99** hardcoded color-literal hits total (`Colors.white|Colors.black|Color(0x`). First-run path: `landing`(8), `login`(6), `home`(38), `song_detail`(9), `new_song`(**0** — already token-clean). Heaviest overall: `home_screen`(38), `video_player`(13). The 99-hit full sweep is Phase B; this phase fixes only the first-run-path four (landing/login/home/song_detail) to the *usability* bar.

## 5. Design — the new token values

### 5.1 `theme.dart` — same names, dark-neon values
Palette (constants, names unchanged):
- `bg = 0xFF0B0810` (near-black base).
- `surface = 0xFF1A1327` — **solid opaque** dark card / menu ground (dropdowns/popups/dialogs/`canvasColor` paint on this — MUST stay opaque; `dropdown_theme_test` asserts it).
- `surface2 = 0xFF211830` (slightly lighter dark).
- `accent = 0xFFFF4D8D` (neon pink — primary). `accent2 = 0xFFA25BFF` (neon purple). `accentMid = 0xFFCF54C0` (between, for 3-stop gradients).
- `ink = 0xFF7C3AED` — repurposed as the **solid** color for framework FilledButton/ElevatedButton on dark (a deep neon violet; the custom `GradientButton` uses the pink→purple gradient instead).
- `textPrimary = 0xFFF5F0FB` (near-white). `textSecondary = 0xFFBEB0D6` (muted lavender). `faint = 0xFF84769C`.
- `danger = 0xFFFF5A67`, `success = 0xFF3FE0D0` (cyan-green, readable on dark), `warning = 0xFFFFC94D`, `info = 0xFF4D8DFF`.
- `brandGradient` → `LinearGradient([accent, accent2])` (pink→purple).
- Glass getters: `glass = Colors.white.withValues(alpha:0.055)`, `glassStrong = Colors.white.withValues(alpha:0.10)`, `border = Colors.white.withValues(alpha:0.14)`.
- `softShadow` → deeper for dark: `BoxShadow(Colors.black.withValues(alpha:0.38), blur 28, offset (0,8))`.

`build({locale})` changes:
- Base `ThemeData.dark(useMaterial3: true)`; `ColorScheme.fromSeed(seedColor: accent, brightness: Brightness.dark, surface: surface, primary: accent, secondary: accent2, error: danger)` (dark base + dark brightness together, or the framework asserts).
- `scaffoldBackgroundColor: Colors.transparent` (NeonBackground shows through — unchanged), **`canvasColor: surface` stays SOLID**.
- `popupMenuTheme/dropdownMenuTheme/dialogTheme` background → `surface` (solid), border `border`.
- Text theme: same Cairo/Inter logic; `bodyColor/displayColor → textPrimary` (now near-white). Keep the Arabic/Latin fallback logic.
- `cardTheme.color → surface`, border `border`.
- `appBarTheme`/`iconTheme`: `foregroundColor/color → textPrimary`.
- Filled/Elevated buttons: `backgroundColor: ink` (neon violet), white text (unchanged shape/padding).
- Outlined button: `foregroundColor: textPrimary`, `backgroundColor: glass`, side `border`.
- Chip: `backgroundColor: glass`, label `textPrimary`, side `border`.
- Segmented: selected `accent` fill / white text; unselected `glass` / `textSecondary`; side `border`.
- Input decoration: `fillColor: surface2` (or `glass`), hint `faint`, label `textSecondary`, focused border `accent`.

### 5.2 `brand.dart` — same widget names, dark-neon glass rendering
- **`MeshBackground`**: base `LinearGradient([0xFF0B0810, 0xFF140C1F, 0xFF0B0810])`; the three blobs become **neon** radial fades — pink (`accent`), purple (`accent2`), cyan (`0xFF3FE0D0`) — kept as `RadialGradient` fades (NO real blur filter on the background layer; blur stays only in `GlassCard`). Blob opacity ~0.35–0.5.
- **`GlassCard`**: keep the `BackdropFilter(blur 22)` structure; fill `FacelessTheme.glass` (dark translucent), border `FacelessTheme.border`, add a bright inset top edge via a subtle top-lighter overlay or a `BoxShadow` inset highlight; `softShadow`.
- **`GradientButton`**: fill becomes the **pink→purple `brandGradient`** (not solid ink); white text; glow shadow `accent.withValues(alpha:0.4)`; add a hairline `rgba(255,255,255,0.2)` border for the glass edge. (Signature unchanged.)
- **`GradientText`**: uses `brandGradient` (now pink→purple) — no code change needed beyond the token value.
- **`BrandPill`**: white → `glass` fill, `border`, `textPrimary` label, accent dot/icon.
- **`coverGradient(seed)`**: replace the 6 pastel pairs with 6 **dark saturated neon** pairs (plum/magenta/indigo/teal-dark families, e.g. `[0xFF3A2352,0xFF7A2E6E]`, `[0xFF1F3A5C,0xFF2E7A6E]`, `[0xFF5C1F3A,0xFFA2405B]`, `[0xFF2B2352,0xFF5A3AA6]`, `[0xFF5C3A1F,0xFFA2762E]`, `[0xFF1F5C4A,0xFF2EA27A]`).

### 5.3 `song_genres.dart` + `genre_grid.dart`
- `song_genres.dart`: swap the 12 pastel `gradient` pairs for dark saturated neon pairs (per the approved mockup); keys/emoji/arabicOnly/labels unchanged (genre tests find by text → survive).
- `genre_grid.dart`: tile label `Color(0xFF3A2F36)` → `FacelessTheme.textPrimary`; unselected border `Colors.white.withValues(0.6)` → `FacelessTheme.border`; **unselected tiles become frosted glass** (fill `glass`), **selected tile keeps a solid gradient + neon ring** (so the choice stays obvious). Auto tile keeps a cyan-tinted treatment.

### 5.4 First-run-path straggler fixes (usability bar)
For `landing_screen`, `login_screen`, `home_screen`, `song_detail_screen`: replace hardcoded `Colors.white`/`Colors.black`/light `Color(0x…)` used for **text or fills** with the appropriate token (`textPrimary`/`textSecondary`/`glass`/`surface`), so **no text is invisible and no card is a light island**. `new_song_screen` needs nothing (0 literals). Scope = readability, not full polish. Everything not on this path is Phase B (leave as-is even if slightly off, as long as it's not the first-run path).

## 6. Files touched
| File | Change |
|---|---|
| `lib/theme.dart` | Token values + `ThemeData` → dark-neon (names unchanged). |
| `lib/ui/brand.dart` | Shared widgets → dark-neon glass rendering (names unchanged). |
| `lib/ui/song_genres.dart` | 12 genre gradient pairs → dark neon. |
| `lib/widgets/genre_grid.dart` | Label/border tokens; glass unselected tiles. |
| `lib/screens/{landing,login,home,song_detail}_screen.dart` | First-run-path readability fixes only. |
| `test/*` | Update any test asserting a light-specific color value (see §7). |

## 7. Testing & verification
- **Static:** `dart analyze lib/theme.dart lib/ui/brand.dart lib/ui/song_genres.dart lib/widgets/genre_grid.dart` + the four screens → clean. (`flutter analyze` hangs — use `dart analyze`.)
- **Tests:** `flutter test`. Existing tests that must still pass: `dropdown_theme_test` (asserts `canvasColor` opaque — holds, surface stays opaque), `genre_grid_test`/`song_genres_test` (find by text — hold), `l10n`/`locale_switch` (unaffected). Fix any test asserting a now-changed light color value.
- **Visual (bounded):** headless-Chrome screenshot of the **unauthenticated** screens only (`/` landing + login) via the PIL harness — authed screens render blank headless (known). Confirm dark-neon applied + text readable.
- **On-device QA (user, gated):** the authenticated first-run path (home → create → song detail) is verified by the user via `./scripts/run-app.sh`. **No deploy** until they sign off.

## 8. Rollout & follow-ups
- Ship on branch `redesign/dark-neon-glass-design-system`; **do not deploy** — hand off `run-app.sh` QA.
- **Phase B:** straggler sweep across the remaining ~17 screens (video_player 13, settings 6, cost 5, run_detail 3, …) + the UX pass + a proper `NeonNav`/bottom-nav.
- **Phase C:** "Make me sing this" photo→video (Kling Avatar on Kie).
- On merge, update the `project_light_theme_redesign` memory (it says "LIGHT, NO dark neon" — now false).
