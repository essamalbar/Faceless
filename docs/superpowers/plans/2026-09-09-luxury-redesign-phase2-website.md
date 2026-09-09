# Luxury Redesign — Phase 2 (Marketing Website) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reskin the Next.js marketing website (`website/`) to the app's "Obsidian & Champagne" system so `faceless-lab.com` matches the live app — same palette, editorial type, and living-waveform signature — with zero violet/pink.

**Architecture:** Flip the Tailwind theme tokens + `globals.css` + the `next/font` families (the site is token-driven, so this carries most of it), then reskin the shared components and page sections, then sweep the sub-pages. Content/structure preserved; visual system only.

**Tech Stack:** Next.js 15 (App Router), React 19, Tailwind CSS, framer-motion, lucide-react, `next/font/google`. Verify with `npm run build` + `npm run lint` + headless-Chrome render.

**Spec:** `docs/superpowers/specs/2026-09-09-luxury-redesign-design-system.md` (§8 Phase 2). The **live app** is the visual target: obsidian ground, champagne used sparingly, editorial serif hero with one champagne accent word, jewel tones, the living waveform. Reference PNGs: `docs/superpowers/specs/redesign-artboards/DirectionA-Home.png`.

## Global Constraints

- **Match the app's tokens exactly.** Palette: `bg #0C0B0E`, `bgDeep #08070A`, `surface #16151A`, `surface2 #1E1C22`, `accent #C9A96E` (champagne), `accent2 #E4CE9E` (champagne bright), `accentDeep #B4915A`, `ink`/text `#EFE9DE` (warm off-white, never pure white), `muted` a warm grey that clears WCAG AA 4.5:1 on `#0C0B0E` (keep/raise the existing `#B4BAC4`-style value, re-verify contrast), `warning #D9A441` (amber), `danger #C6564E`, `success #9DBB9C`.
- **NO violet/pink/magenta.** Delete `accent2 #8B5CF6` (violet) and `rose #EC8FA9` (pink) from the theme; replace their usages with champagne or a jewel teal. Grep must come back clean for `8B5CF6`, `E7B53C`, `EC8FA9`, `Fraunces`.
- **Champagne used sparingly** — hairlines, one accent word per hero, CTAs, small dots; never large gold fills.
- **Type:** display **Cormorant Garamond** (EN) / **Amiri** (AR); body **Manrope** (EN) / **Tajawal** (AR) — via `next/font/google`, exposed as the existing CSS vars (`--font-display`, `--font-sans`/`--font-inter`, `--font-arabic`) so consumers don't all need editing. Give each a real fallback stack.
- **Keep the living-waveform signature** ("sound made visible") — it already exists on the site; restyle it champagne, don't remove it.
- **Behavior/content preserved:** all links, routes, marketing copy, the AR/EN language toggle, and section structure stay. Restyle only. (Small copy tweaks to match the app's editorial voice are allowed only where they clearly help — flag them.)
- **Reduced-motion:** keep the existing `prefers-reduced-motion` kill-switch working for the aurora + any new motion.
- **Verification per task:** `cd website && npm run build` succeeds AND `npm run lint` clean; plus a grep for banned tokens. `flutter`/`dart` do NOT apply here — this is the JS/TS site.

---

### Task 1: Theme tokens + globals

**Files:** `website/tailwind.config.ts`, `website/app/globals.css`

- [ ] **Step 1:** In `tailwind.config.ts`, replace the `colors` block with the app palette (Global Constraints): `bg #0C0B0E`, `bgDeep #08070A`, `surface #16151A`, `surface2 #1E1C22`, `accent #C9A96E`, `accent2 #E4CE9E`, `accentDeep #B4915A`, `ink #EFE9DE`, `muted` (keep AA-clearing warm grey), `warning #D9A441`, `danger #C6564E`, `success #9DBB9C`. **Remove** the `rose` key. Keep the `animation`/`keyframes` (float) block.
- [ ] **Step 2:** In `globals.css`, change `html,body` `background:#0A0E1A → #0C0B0E`, `color:#E5E7EB → #EFE9DE`; change the focus-ring `outline` color `#E7B53C → #C9A96E`. Keep the reduced-motion block.
- [ ] **Step 3 (verify):** `cd website && npm run build && npm run lint`. Then `grep -rnE "8B5CF6|E7B53C|EC8FA9|0A0E1A" website/tailwind.config.ts website/app/globals.css` → **no matches**. Expected: build clean.
- [ ] **Step 4: Commit** `feat(web): obsidian+champagne theme tokens (tailwind + globals)`

---

### Task 2: Fonts

**Files:** `website/app/layout.tsx`

- [ ] **Step 1:** Replace the `next/font/google` imports: `Fraunces` → `Cormorant_Garamond` (bound to `--font-display`), `Inter` → `Manrope` (bound to `--font-sans`/`--font-inter` — keep the SAME css-var name the config/consumers use so nothing else breaks), and pair the Arabic: keep `Noto_Naskh_Arabic`→ switch to `Amiri` for `--font-arabic` display and add `Tajawal` for Arabic body if the config references a second arabic var (check tailwind `fontFamily.arabic`). Configure weights actually used (Cormorant 500/600 + italic; Manrope 400/500/600/700; Amiri 400/700).
- [ ] **Step 2:** Ensure the `tailwind.config.ts` `fontFamily` `display`/`sans`/`arabic` stacks reference the right vars with real fallbacks (Cormorant→Georgia/serif; Manrope→system-ui; Amiri→'Noto Naskh Arabic'/serif). If a var name changed, update both sides.
- [ ] **Step 3 (verify):** `cd website && npm run build && npm run lint`. `grep -rn "Fraunces\|Inter(" website/app/layout.tsx` → no matches. Expected: build clean, fonts resolve.
- [ ] **Step 4: Commit** `feat(web): editorial fonts — Cormorant/Amiri + Manrope/Tajawal`

---

### Task 3: Shared components

**Files:** `website/components/aurora.tsx`, `sparkle-logo.tsx`, `site-chrome.tsx`, `prompt-input.tsx`

- [ ] **Step 1:** `aurora.tsx` — restyle the background aurora to amber/champagne + deep teal ONLY (no violet/indigo blobs); keep it subtle and reduced-motion-safe. `sparkle-logo.tsx` — champagne mark matching the app's gold logo. `site-chrome.tsx` — nav + footer on obsidian, champagne hairlines, warm off-white links, champagne "Start free"/CTA (hairline style, not a saturated gold fill gradient). `prompt-input.tsx` — obsidian field, champagne caret/accent, keep the typewriter (reduced-motion-safe).
- [ ] **Step 2:** Grep these four files for `8B5CF6|E7B53C|EC8FA9|violet|purple|from-accent2|rose` and remove/replace with champagne/teal tokens. Replace any raw hex with tailwind token classes (`text-accent`, `border-accent/30`, etc.).
- [ ] **Step 3 (verify):** `cd website && npm run build && npm run lint`; grep the four files → no banned tokens. Expected: clean.
- [ ] **Step 4: Commit** `feat(web): luxe shared components (aurora, logo, chrome, prompt)`

---

### Task 4: Landing page

**Files:** `website/app/page.tsx`

- [ ] **Step 1:** Reskin every section (`Nav`, `Hero`, `HowItWorks`, `WhatYouGet`, `Showcase`, `Why`, `PricingTeaser`, `FinalCTA`) to the app: obsidian sections, editorial `font-display` (Cormorant) hero with exactly ONE champagne accent word (e.g. the current gold gradient span → a single champagne word), champagne hairline dividers, champagne CTAs (the primary "Start free" repeated down the page), the living-waveform showcase in champagne. Remove the violet/rose gradient stops from the hero and any `from-accent via-rose to-accent2` gradients → champagne.
- [ ] **Step 2:** Keep all copy, links (`APP_URL`), anchors, and the section order. One primary action per section. Verify the champagne "large fill" restraint (CTAs are hairline/one-word gold, not full gold blocks).
- [ ] **Step 3 (verify):** `cd website && npm run build && npm run lint`; `grep -nE "8B5CF6|E7B53C|EC8FA9|rose|violet|purple" website/app/page.tsx` → no matches. Then a headless render check (controller does this at Task 6, but a spot build is enough here). Expected: clean.
- [ ] **Step 4: Commit** `feat(web): luxe landing page (editorial hero, champagne, waveform)`

---

### Task 5: Sub-pages + OG image sweep

**Files:** `website/app/{about,pricing,contact,privacy,terms,press,refund}/page.tsx`, `website/app/opengraph-image.tsx`

- [ ] **Step 1:** These inherit the tokens/fonts automatically; audit each for hard-coded old-era literals (`8B5CF6`, `E7B53C`, `EC8FA9`, `#0A0E1A`, `Fraunces`, `rose`, `violet/purple` gradient classes, pure-white text) and replace with tokens. Apply the editorial heading + champagne accent where each page has a title/CTA. `opengraph-image.tsx` — obsidian bg + champagne + Cormorant so shared links match.
- [ ] **Step 2 (verify):** `cd website && npm run build && npm run lint`; `grep -rnE "8B5CF6|E7B53C|EC8FA9|Fraunces|#0A0E1A" website/app/` → no matches (outside comments). Expected: clean.
- [ ] **Step 3: Commit** `feat(web): sweep sub-pages + OG image to the luxe system`

---

### Task 6: Verify + branch finish

- [ ] **Step 1:** `cd website && npm run build` → succeeds; `npm run lint` → clean.
- [ ] **Step 2:** Headless-Chrome render of the built site (or `npm run dev` on :3001) for **landing (EN)**, **landing (AR toggle)**, and **pricing** — confirm obsidian + champagne, editorial serif hero, no violet/pink, warm off-white text, the waveform signature, reduced-motion respected. Sample pixels to confirm the obsidian bg + champagne accents.
- [ ] **Step 3:** Repo-wide final grep: `grep -rnE "8B5CF6|E7B53C|EC8FA9|Fraunces" website/ --include=*.tsx --include=*.ts --include=*.css` → clean (comments OK).
- [ ] **Step 4:** Invoke **superpowers:finishing-a-development-branch**. (Deploy, when chosen, is `gcloud run deploy faceless-website --source website/`.)

---

## Self-Review

**Spec coverage:** §8 Phase 2 (tokens, fonts, components, keep-waveform, remove-violet) → T1 (tokens/globals), T2 (fonts), T3 (components), T4 (landing), T5 (sub-pages/OG), T6 (verify/finish). No gaps.
**Placeholder scan:** exact hex values given; each task names the files + the grep gate; verification is concrete (`npm run build`/`lint` + grep). No "make it nice."
**Consistency:** the app token values (accent `#C9A96E`, accent2 `#E4CE9E`, bg `#0C0B0E`, warning `#D9A441`) match Phase 1's `lib/theme.dart` exactly, so both surfaces share one system. Font var names kept stable (T2) so consumers inherit without per-file edits.
