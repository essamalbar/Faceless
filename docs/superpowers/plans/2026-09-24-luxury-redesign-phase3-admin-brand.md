# Luxury Redesign — Phase 3 (Admin Dashboard + Brand Assets) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Bring the two remaining off-brand surfaces onto the "Obsidian & Champagne" system: the server-rendered super-admin control panel, and the app's PWA/brand raster assets (favicon, icons, manifest) — which are still default Flutter.

**Architecture:** The admin panel (`pipeline/admin_page.py`) is a self-contained HTML page driven by a CSS `:root` token block — flip the token *values* (like the app's theme flip) and the whole panel inherits, leaving all JS/auth/fetch behavior untouched. Brand assets are regenerated (champagne mark on obsidian) + the manifest rebranded.

**Tech Stack:** Python/FastAPI (admin HTML string + tests via `uv run pytest`), inline HTML/CSS/JS, PIL/Pillow for icon generation, JSON manifest.

**Spec / design target:** `docs/superpowers/specs/2026-09-09-luxury-redesign-design-system.md`. The **live app** is the visual reference. Palette (verbatim): bg `#0C0B0E`, bgDeep `#08070A`, surface `#16151A`, surface2 `#1E1C22`, accent/champagne `#C9A96E`, accent bright `#E4CE9E`, accentDeep `#B4915A`, text `#EFE9DE` (warm off-white, never pure white), muted `#A39C8E`, success `#9DBB9C`, warning/amber `#D9A441`, danger `#C6564E`.

## Global Constraints

- **BEHAVIOR-PRESERVING.** No functional/JS/auth/endpoint changes. Admin: every fetch call, the sessionStorage token handling, the login flow, and all button/label TEXT stay exactly as-is — only colors/style values change.
- **Admin CSP is inline-only.** `pipeline/admin_page.py` forbids external scripts/stylesheets/**fonts**/images (strict prod CSP + the comment header). So NO web fonts (Cormorant/Amiri/Manrope) in the admin panel — it keeps `system-ui`. That's correct for a utility tool; obsidian + champagne colors carry the luxe feel. Add NO `http(s)://` / `googleapis` references.
- **Admin test markers must survive.** `tests/test_admin_dashboard.py::test_admin_dashboard_page_served` asserts the served HTML contains: `Control Panel`, `Sign in`, `Sign out`, `type="password"`, `/admin/login`, `sessionStorage`, `/admin/overview`, `/admin/users`, `/admin/runs`, `/admin/transactions`, and analytics/audio markers. Keep all of them. Keep the whole suite green.
- No violet/pink/magenta anywhere. Champagne used with restraint. Warm off-white text, never pure white.
- **Verification:** `uv run pytest tests/test_admin_dashboard.py -q` (and the broader suite) green; the admin HTML still parses/serves 200 at `/admin`. Icons: generate at exact sizes, eyeball the rendered PNG.

---

### Task 1: Reskin the admin panel + public interstitials

**Files:** `pipeline/admin_page.py` (the `ADMIN_HTML` string — mainly its `:root` CSS token block + any stray inline hexes), `pipeline/api.py` (the two tiny inline HTML interstitials in the YouTube-callback handlers: the `#F2EFF7` "Connected" page + the plain "cancelled" page).

- [ ] **Step 1: Map the light→dark tokens.** In `admin_page.py`'s `:root` block, remap every custom property to the obsidian+champagne palette:
  - `--bg1/--bg2/--bg3` → obsidian family (`#0C0B0E`/`#100E15`/`#08070A`); the body `background:` radial+linear → an obsidian wash (warm near-black), not the white radial.
  - `--card #ffffff → #16151A`; `--ink #1b1e28 → #EFE9DE`; `--muted → #A39C8E`; `--faint → #6E685D`; `--line/--line2 → warm hairlines` (`rgba(238,233,222,0.10)` / softer).
  - **Primary accent → champagne:** the panel uses green (`--green #1f9d63` / `--green-ink`) as its primary/link/focus color — remap the PRIMARY usage (links `a{}`, focus rings, primary buttons) to champagne (`--green`→`#C9A96E`, `--green-ink`→`#E4CE9E`, `--green-bg`→`rgba(201,169,110,0.10)`, `--green-line`→`rgba(201,169,110,0.30)`). Keep semantic status colors as muted app versions: `--amber → #D9A441` (+ dark bg/line), `--red → #C6564E` (+ dark bg/line), `--blue-ink → #6E8BA6`, `--grey → #A39C8E`. Where "green" was used specifically as a SUCCESS signal (not primary), a muted sage `#9DBB9C` is fine — use judgment, but the dominant brand accent is champagne.
  - Shadows → deepen for dark (`rgba(0,0,0,.4)`), input `background:#fff → var(--card)` / `#1E1C22`.
- [ ] **Step 2: Sweep stray inline hexes.** Grep `admin_page.py` for any `#[0-9A-Fa-f]{6}` / `#fff` / `rgb(255` / `Colors`/pure-white outside the `:root` block and route them through tokens or the palette. No pure-white text; no violet/pink.
- [ ] **Step 3: Reskin the two api.py interstitials.** The `#F2EFF7` "✅ Connected" page and the plain "cancelled" page → inline obsidian bg (`#0C0B0E`) + warm off-white text (`#EFE9DE`) + a champagne heading accent, `system-ui`, centered. Keep the copy and status codes.
- [ ] **Step 4: Verify.** `uv run pytest tests/test_admin_dashboard.py -q` → all green (esp. `test_admin_dashboard_page_served` — the text markers). Grep `admin_page.py` for `http://|https://|googleapis` → none (CSP). Grep the whole `ADMIN_HTML` for `#ffffff|#fff\b|1b1e28|1f9d63|f6f7fb` (old light values) → none left. Confirm no `#[0-9A-Fa-f]{6}` violet/pink introduced.
- [ ] **Step 5: Commit** `feat(admin): obsidian+champagne reskin of the control panel + interstitials`

---

### Task 2: Brand raster assets + PWA manifest

**Files:** `web/manifest.json`, `web/icons/{Icon-192,Icon-512,Icon-maskable-192,Icon-maskable-512}.png`, `web/favicon.png`, `web/index.html` (theme-color/loading bg if present), and add `website/app/icon.svg` (or `icon.png`) for the marketing site's browser-tab favicon. Optional helper: a one-off generation script in the scratchpad (do NOT commit the script).

- [ ] **Step 1: Rebrand the manifest.** `web/manifest.json`: `name` "Faceless Lab", `short_name` "Faceless", `description` a real one-liner ("AI Arabic song studio — turn an idea into a finished song."), `background_color` `#0C0B0E`, `theme_color` `#0C0B0E` (both were the default `#0175C2`). Keep the `icons` array + `display`/`orientation`.
- [ ] **Step 2: Generate the icon set with PIL** (Pillow 10.4.0 is available via `/Users/gileshannah/miniforge3/bin/python3`). Draw the brand mark — a champagne 4-point sparkle (matching the app's `FacelessLogo`/`sparkle-logo`) on an obsidian ground with a soft champagne ring — and export:
  - `web/icons/Icon-192.png` (192×192), `Icon-512.png` (512×512) — full-bleed obsidian bg + centered champagne sparkle.
  - `web/icons/Icon-maskable-192.png`, `Icon-maskable-512.png` — same but with ~20% safe-zone padding (mark within the inner 80% so Android's mask doesn't clip it).
  - `web/favicon.png` (regenerate at 32×32, was 16×16 — 32 is crisper; keep it a PNG the index.html references) — champagne sparkle on obsidian.
  - Champagne gradient `#E4CE9E → #B4915A`; obsidian `#0C0B0E`. Antialias. No violet/pink.
- [ ] **Step 3: index.html + website favicon.** In `web/index.html`, set/add `<meta name="theme-color" content="#0C0B0E">` and any loading-screen bg to obsidian (keep the existing title/apple-mobile metas). Add `website/app/icon.svg` — a small inline-SVG champagne sparkle on obsidian (Next.js serves `app/icon.svg` as the favicon automatically).
- [ ] **Step 4: Verify.** `file web/icons/*.png web/favicon.png` → correct dimensions. Open/eyeball at least `Icon-512.png` + `favicon.png` (they must show a champagne sparkle on obsidian, not the Flutter logo, not blank). `web/manifest.json` parses (`python3 -c "import json;json.load(open('web/manifest.json'))"`). No test regressions (`uv run pytest -q` unaffected — assets aren't tested).
- [ ] **Step 5: Commit** `feat(brand): champagne-on-obsidian app icons, favicon, PWA manifest`

---

## Self-Review

**Spec coverage:** admin dashboard → T1 (token flip + sweep) + the interstitials; brand assets (favicon/icons/manifest/theme-color) → T2; website favicon → T2 Step 3. No email templates exist to reskin (Supabase/Paddle handle those). No gaps for the agreed scope (admin + brand assets).
**Placeholder scan:** exact palette values given; the admin test markers to preserve are enumerated verbatim; icon sizes/colors are concrete; verification is concrete (pytest + `file` + parse + eyeball). No "make it nice."
**Consistency:** palette values match Phase 1/2 exactly. Deploy note: both surfaces ship in the `faceless-api` image (admin = Python, app assets = `flutter build web`), so `build-and-push.sh` deploys both; the website favicon ships via the website deploy.
