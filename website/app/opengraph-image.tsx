// Auto-generates the social-share OG card at /opengraph-image.
//
// Next.js 13+ App Router convention: this file becomes the OG image
// referenced from layout.tsx's metadata.openGraph.images automatically.
// No need to ship a static og.jpg — the PNG is rendered at build time
// from this JSX via @vercel/og's ImageResponse.
//
// Arabic glyphs need a font that supports the script — Inter (the
// ImageResponse default) renders Arabic as tofu boxes. We fetch Noto
// Naskh Arabic from Google Fonts and pass it via the `fonts` option.
// Fetch happens at build time so there's no runtime latency.

import { ImageResponse } from "next/og";

// Node.js runtime (default) — has full HTTP fetch support for the Google
// Fonts download, no special platform requirements. Edge runtime works
// for ImageResponse on Vercel but fails when next start runs locally
// without an edge function host, so keep this on Node.js.
export const alt = "Faceless Lab — AI Arabic song generator";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// Inter for Latin (heavier weight = bigger visual presence in OG cards
// where the image renders at small sizes in Twitter/WhatsApp feeds).
const INTER_BOLD =
  "https://fonts.gstatic.com/s/inter/v18/UcCO3FwrK3iLTeHuS_nVMrMxCp50ojIw2boKoduKmMEVuLyfMZhrib2Bg-4.ttf";
// Tajawal Bold — Latin + Arabic, designed for UI. Satori (the JSX→PNG
// engine inside ImageResponse) can't parse some OpenType lookups in Noto
// Naskh Arabic ("substFormat: 3 is not yet supported"). Tajawal uses a
// simpler GSUB table and renders cleanly in satori.
const TAJAWAL_ARABIC_BOLD =
  "https://fonts.gstatic.com/s/tajawal/v11/Iurf6YBj_oCad4k1l_6gLrZjiLlJ-G0.ttf";

async function loadFont(url: string): Promise<ArrayBuffer> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`failed to fetch font: ${url}`);
  return res.arrayBuffer();
}

export default async function Image() {
  const [inter, arabic] = await Promise.all([
    loadFont(INTER_BOLD),
    loadFont(TAJAWAL_ARABIC_BOLD),
  ]);

  return new ImageResponse(
    (
      <div
        style={{
          height: "100%",
          width: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "72px 80px",
          background:
            "linear-gradient(135deg, #0a0a0f 0%, #1a0f0a 60%, #0a0a0f 100%)",
          position: "relative",
        }}
      >
        {/* Accent gold blob — subtle radial glow in the top-right */}
        <div
          style={{
            position: "absolute",
            top: -200,
            right: -200,
            width: 600,
            height: 600,
            borderRadius: "50%",
            background:
              "radial-gradient(circle, rgba(231,181,60,0.32) 0%, rgba(231,181,60,0) 70%)",
          }}
        />
        {/* Accent at bottom-left for asymmetric balance */}
        <div
          style={{
            position: "absolute",
            bottom: -250,
            left: -180,
            width: 550,
            height: 550,
            borderRadius: "50%",
            background:
              "radial-gradient(circle, rgba(231,181,60,0.18) 0%, rgba(231,181,60,0) 70%)",
          }}
        />

        {/* Top row: brand mark + tagline */}
        <div style={{ display: "flex", alignItems: "center", gap: 16, zIndex: 1 }}>
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: 12,
              background:
                "linear-gradient(135deg, #e7b53c 0%, #d9961f 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 28,
              fontWeight: 700,
              color: "#0a0a0f",
            }}
          >
            F
          </div>
          <div
            style={{
              fontSize: 24,
              fontWeight: 600,
              color: "#fafafa",
              letterSpacing: "-0.01em",
            }}
          >
            Faceless
          </div>
          <div
            style={{
              marginLeft: "auto",
              fontSize: 14,
              fontWeight: 600,
              color: "#e7b53c",
              letterSpacing: "0.18em",
              textTransform: "uppercase",
            }}
          >
            AI · Arabic · Song
          </div>
        </div>

        {/* Title block */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 28,
            zIndex: 1,
          }}
        >
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              fontSize: 86,
              fontWeight: 700,
              letterSpacing: "-0.045em",
              lineHeight: 0.96,
              maxWidth: 1000,
            }}
          >
            <div style={{ color: "#fafafa" }}>Write one line.</div>
            <div
              style={{
                background:
                  "linear-gradient(135deg, #e7b53c 0%, #fde68a 50%, #d9961f 100%)",
                backgroundClip: "text",
                color: "transparent",
              }}
            >
              Get a full Arabic song.
            </div>
          </div>

          {/* Arabic subtitle — RTL, Noto Naskh font */}
          <div
            style={{
              fontFamily: "NotoArabic",
              fontSize: 40,
              fontWeight: 700,
              color: "rgba(250,250,250,0.78)",
              direction: "rtl",
              maxWidth: 1000,
            }}
          >
            من جملة واحدة إلى أغنية عربية كاملة
          </div>
        </div>

        {/* Bottom row: value props */}
        <div
          style={{
            display: "flex",
            gap: 28,
            fontSize: 18,
            color: "rgba(250,250,250,0.7)",
            zIndex: 1,
            alignItems: "center",
          }}
        >
          <span>Original vocals</span>
          <span style={{ color: "rgba(231,181,60,0.5)" }}>·</span>
          <span>Written lyrics</span>
          <span style={{ color: "rgba(231,181,60,0.5)" }}>·</span>
          <span>Free draft first</span>
        </div>
      </div>
    ),
    {
      ...size,
      fonts: [
        { name: "Inter", data: inter, style: "normal", weight: 700 },
        { name: "NotoArabic", data: arabic, style: "normal", weight: 700 },
      ],
    },
  );
}
