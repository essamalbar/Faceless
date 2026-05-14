# Faceless marketing website

Public marketing surface — a separate Next.js project from the Flutter
app. Anyone (no auth) can visit it; the CTAs deep-link into the app at
`NEXT_PUBLIC_APP_URL`.

## Develop

```bash
cd website
npm install
npm run dev          # http://localhost:3001
```

## Deploy to Vercel (free)

```bash
npm install -g vercel
cd website
vercel               # follow the prompts; project root = website/
```

After the first deploy, set `NEXT_PUBLIC_APP_URL` in the Vercel dashboard
to point at where the Flutter app is hosted (currently the Cloud Run URL,
or a custom `app.faceless.com` once you have a domain).

## Configuration

| Env var | What it does | Default |
|---|---|---|
| `NEXT_PUBLIC_APP_URL` | Target of every "Start free" / "Sign in" / template CTA | `https://faceless-api-uplzdtffeq-uc.a.run.app` |

## Structure

```
website/
├── app/
│   ├── layout.tsx       OG metadata + global styles
│   ├── page.tsx         All marketing sections inline
│   └── globals.css      Tailwind base + brand vars
├── components/
│   └── sparkle-logo.tsx SVG mirror of lib/widgets/faceless_logo.dart
└── tailwind.config.ts   Palette pinned to FacelessTheme (lib/theme.dart)
```

The sparkle-logo math is duplicated between this SVG and the Flutter
widget — if you change the constellation layout in one place, change
both, or the brand will read differently on web vs in-app.
