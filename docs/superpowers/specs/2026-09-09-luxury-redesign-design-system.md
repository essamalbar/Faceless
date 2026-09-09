# Faceless Lab — Luxury Redesign · Design-System Spec

**Date:** 2026-09-09
**Status:** Draft for review
**Direction chosen:** A · **Obsidian & Champagne** (from the `Faceless Lab — Luxury Redesign` design canvas)
**Supersedes:** the glassy dark-neon (pink→purple) system in `docs/superpowers/specs/2026-08-14-dark-neon-glass-design-system-design.md`

---

## 1. Purpose & design language

Faceless Lab is a **Virtual Artist Label** — an AI Arabic (and multi-genre) song studio where the unit is the *artist*. The redesign turns the app from a "trendy neon" consumer look into a **timeless, professional, quietly luxurious** product, and makes the AI generation moments feel like real magic instead of a spinner.

The look is one system across **all surfaces** (Flutter app, Next.js website, and login/landing/touchpoints).

**Five principles:**

1. **Restraint is the luxury.** Warm obsidian grounds; a single champagne-gold accent used *only* on hairlines, one accent word, one primary CTA, and small status dots — **never** large gold fills. Quantity + saturation is the entire difference between "luxury" and "casino-gold."
2. **Editorial typography.** A high-contrast serif for display (English **Cormorant Garamond**, Arabic **Amiri**) paired with a refined UI sans (English **Manrope**, Arabic **Tajawal**). Warm off-white text — never pure white.
3. **Cinematic, not loud.** Depth from layered translucency, hairlines, soft shadows, and *one* slow ambient breath — not gradients-as-decoration. **Zero violet / pink / magenta** anywhere in the app system (that is the previously-rejected territory).
4. **One brand signature: the living waveform** — "sound made visible." A thin champagne waveform that breathes. It appears in the app *and* the website, and it is the visual anchor of every AI-magic moment.
5. **Bilingual & RTL are first-class.** Every screen is designed in Arabic + RTL and English + LTR; the type system is locale-aware.

---

## 2. Design tokens (colours)

Warm obsidian + champagne, with a small set of desaturated jewel tones for cover art / avatars / atmosphere.

| Role | Token | Value | Usage |
|---|---|---|---|
| Base ground | `bg` | `#0C0B0E` | app background (warm near-black) |
| Deep edge | `bgDeep` | `#08070A` | vignette / bottom fade |
| **Solid** card/menu | `surface` | `#16151A` | cards, **dropdown/popup/dialog grounds — MUST stay opaque** |
| **Solid** raised | `surface2` | `#1E1C22` | inputs, raised chips |
| Glass fill | `glass` | `rgba(255,255,255,0.03)` | translucent panels over ambient |
| Glass strong | `glassStrong` | `rgba(255,255,255,0.06)` | brighter glass edge |
| Hairline | `border` | `rgba(238,233,222,0.10)` | warm-white hairline |
| Champagne hairline | `borderAccent` | `rgba(201,169,110,0.35)` | CTA / emphasis edges |
| **Accent** | `accent` | `#C9A96E` | champagne — the one metallic accent |
| Accent bright | `accent2` | `#E4CE9E` | highlight / gradient top / accent word |
| Accent mid | `accentMid` | `#D4B483` | 3-stop gradient middle |
| Accent deep | `accentDeep` | `#B4915A` | gradient bottom |
| Text primary | `textPrimary` | `#EFE9DE` | warm off-white (never `#FFFFFF`) |
| Text secondary | `textSecondary` | `#A39C8E` | muted warm grey |
| Text faint | `faint` | `#6E685D` | hints, disabled |
| Success / ready | `success` | `#9DBB9C` | muted sage (not neon) |
| Active / composing | (uses `accent2`) | `#E4CE9E` | pulsing champagne dot |
| Warning / review | (uses `accent`) | `#C9A96E` | champagne outline |
| Danger | `danger` | `#C6564E` | muted brick red |
| Info | `info` | `#6E8BA6` | muted steel |

**Brand gradient** (`brandGradient`): `[#E4CE9E → #B4915A]` @135° — logo mark, one accent word, CTA inner sheen, waveform bars.

**Jewel tones** (cover art / avatars / atmosphere — the *only* saturated colours, all warm or teal, **no violet/plum/indigo**):

```
teal     #233A44 → #2E7A6E
bronze   #3E2E1C → #A0762E
garnet   #3A1E1C → #7A3A2E
emerald  #1F3A30 → #2E7A5C
```

`coverGradient(seed)` is reseeded from exactly this set (the current palette's plum/indigo/violet/wine entries are removed).

**Ambient background:** obsidian vertical gradient + a soft champagne wash from the top (`accent` @~10% alpha, radial) + a low teal breath at the base (~14% alpha). RadialGradients only — **no per-frame blur** in the background layer.

---

## 3. Typography

| Slot | English | Arabic | Weights |
|---|---|---|---|
| Display / editorial | **Cormorant Garamond** | **Amiri** | 500, 600 (+ italic EN) |
| UI / body | **Manrope** | **Tajawal** | 400, 500, 600, 700 |

- Loaded via `google_fonts` (already a dependency). Locale decides the primary; the other language is the fallback stack so mixed strings still shape correctly.
- **Eyebrows** (section labels): Manrope, uppercase, `letter-spacing: 0.30em`, ~10.5px, `textSecondary`. Arabic eyebrows use Tajawal (no uppercase — Arabic has no case), weight 700, subtle tracking.
- **Accent word**: exactly one word per hero rendered in the champagne gradient (`GradientText`) — e.g. *sing* / *أغنيتك*.
- Replaces the current Space Grotesk / Inter / Cairo stack.

---

## 4. Shared layer — the low-risk flip (`lib/theme.dart` + `lib/ui/brand.dart`)

The last redesign proved that **changing token VALUES + brand-widget rendering while keeping NAMES stable carries the whole app** (commit `fe128e7`). We reuse that mechanism — ~80% of the visual redesign at low risk — then hand-craft the signature screens.

### 4.1 `lib/theme.dart` (token values only; names unchanged)
Remap every existing token to §2. `ThemeData.build` keeps its structure; only:
- `ColorScheme.fromSeed(seedColor: accent…)` → champagne seed.
- Filled/elevated buttons → obsidian ground (`surface`) + champagne label + champagne hairline (not a solid gold fill).
- `textTheme` → Manrope (EN) / Tajawal (AR) with cross-fallback; `display()` helper → Cormorant (EN) / Amiri (AR), locale-aware.
- **`canvasColor` / `surface` / popup / dialog stay SOLID** (`#16151A`) — carries the dropdown-overlap fix (`drop.png` bug) forward.

### 4.2 `lib/ui/brand.dart` (rendering only; names unchanged)
- `MeshBackground` → **ambient obsidian + champagne wash + teal breath** (per §2). One optional slow breath; static fallback for reduced-motion / low-end web.
- `GlassCard` → luxe translucent surface: glass fill + hairline + soft shadow; `tint`/champagne-hairline variant. Blur sigma reduced (~16–18) with a solid fallback path for Flutter **web** perf.
- `GradientButton` → **champagne CTA**: dark ground + `borderAccent` hairline + champagne label + subtle inner sheen (no heavy gold fill).
- `GradientText` → champagne accent text (unchanged mechanism, new gradient).
- `BrandPill` → champagne-hairline pill (credits/status).
- `coverGradient(seed)` → jewel set from §2 (violet removed).

### 4.3 New primitives (added, not renamed)
`Eyebrow`, `EditorialHeading` (locale-aware serif), `Hairline`, `LivingWaveform` (the signature — a breathing bar row / `CustomPainter`), `StatusPill` + status dot (ready / composing / review), `ArtistBadge` (avatar with optional "alive" halo), `StepList` (the composing progress list).

---

## 5. Motion (cheap, Flutter-web-safe)

One well-orchestrated feel, not scattered micro-interactions:
- **Living waveform** — breathing opacity + `scaleY` on bars (one controller; staggered delays), the shared signature.
- **Alive halo** — scale + opacity pulse on the active artist / active step.
- **Section entrance** — staggered fade + slide-up on first build only (`TweenAnimationBuilder`).
- Respect `MediaQuery.disableAnimations` / reduced-motion. **No blur animated per frame.** Verify on Flutter web (canvaskit) — animation there is not free.

---

## 6. Signature AI-magic moments (hand-crafted)

These are the screens that must feel like magic, built beyond the token flip:

1. **Composing** — the minutes-long song-generation wait (the canvas's second artboard). Artist "alive" + living waveform + Arabic/EN step list (analyse → lyrics w/ tashkeel → melody & vocal → cover → assemble) + honest ETA + "we'll notify you." **The** surface. (Rework of `run_detail_screen` / a dedicated composing view.)
2. **Artist comes alive** — `artist_screen`: halo + reveal when an artist loads; discography, voice, earnings as an editorial page.
3. **Cover materialising** — a shimmer/reveal when the cover image resolves (`song_detail` / composing).
4. **Lyric reveal** — `song_approve_screen` / `edit_script_screen`: Arabic lyric lines fade in, line-by-line, in the editorial serif — this is where the writer-approval gate lives, so it doubles as the "review before you pay" moment.

---

## 7. Architecture / decomposition

- **`home_screen.dart` is 3472 lines.** A 360° redesign decomposes it into behavior-preserving section widgets (under `lib/widgets/home/` or `lib/screens/home/`): `HomeHeader`, `HeroGreeting`, `PrimaryComposeCTA`, `ArtistsRow`, `LatestReleaseCard`, `SongList`/`SongRow`, `TrendingSection`, `MorningDraftsSection`, `LlmBanner`. Logic/state unchanged — only extraction + reskin. This is targeted improvement, not scope creep: the file is too large to edit reliably.
- Every other screen inherits the look through the shared layer (§4); the ~5 signature screens get hand-crafted polish; the rest get a leftover-sweep (like Phase B of the last redesign, which found only one real light-era leftover).
- **No functional behavior changes** anywhere (API calls, gates, credits, i18n keys untouched).

---

## 8. Phasing (build order)

**Phase 1 — Flutter app** (the real work):
- 1a. Token + type foundation (`theme.dart`, `brand.dart`, new primitives) — the flip. Fix pre-existing invalid Dart in `lib/main.dart:31,:105` (blocks `flutter analyze`).
- 1b. Home decomposition + luxe home screen.
- 1c. Signature magic screens (§6).
- 1d. Leftover sweep across remaining screens (login, settings, billing, artists, personas, cost, transactions, logs, video player, onboarding, landing).
- 1e. Verify (§9).

**Phase 2 — Website** (`website/`, already ~70% aligned on gold/serif — a lighter pass):
- Replace saturated `#E7B53C` gold with champagne `#C9A96E`; add obsidian tokens in `tailwind.config.ts`; wire Cormorant/Amiri + Manrope/Tajawal via `next/font`.
- Reskin components (`aurora.tsx`, `sparkle-logo.tsx`, `prompt-input.tsx`, `site-chrome.tsx`) and page sections to the luxe system; keep the living-waveform signature. Fix the stale "mirrors lib/theme.dart" comment (the surfaces had diverged).

**Phase 3 — Touchpoints:** app login/landing/onboarding/legal/reset; website legal/pricing/about; `opengraph-image.tsx`; any email-style templates.

Each phase is its own implementation plan (via the writing-plans skill) and its own PR/branch.

---

## 9. Verification & invariants

- `dart analyze <files>` per changed file (**`flutter analyze` hangs** in this repo — use `dart analyze`).
- Keep the **25 Flutter tests** green; **read what they assert about theme/tokens before flipping** values.
- Authed screens render blank in headless Chrome — verify them via `./scripts/run-app.sh` (not the IDE Run button — it strips `--dart-define`). Logged-out screens + PNG spot-checks can use headless Chrome (`--headless=new --enable-unsafe-swiftshader --virtual-time-budget`).
- **Invariants that must hold:** `canvasColor`/`surface` SOLID; no violet/pink/magenta; champagne used sparingly (hairlines / one word / one CTA / small dots); warm off-white text, never pure white; RTL + Arabic parity on every screen; all functional behavior preserved.

## 10. Risks

- **Flutter-web blur perf** — limit `BackdropFilter` layers; solid fallback; validate on canvaskit before shipping motion.
- **Runtime font loading** (`google_fonts` fetches Cormorant/Amiri/Manrope/Tajawal) — consider bundling faces for offline/first-paint; verify Arabic shaping.
- **Whiplash history** — mitigated: Direction A is grounded in the website's existing gold DNA, was explicitly chosen by the user, and visually confirmed (Desktop preview PNGs). If the user sours, re-surface this history before re-pivoting.
