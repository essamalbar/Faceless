import type { Metadata } from "next";
import { Check, Sparkles, ArrowRight } from "lucide-react";
import { SiteNav, SiteFooter, SectionEyebrow } from "@/components/site-chrome";

// ----------------------------------------------------------------------------
// PRICING — /pricing
// Names + amounts MUST match the live Paddle catalog (Silver / Gold / Platinum,
// $9 / $29 / $79 monthly) so what a customer sees here matches Paddle Checkout.
// Paddle is the Merchant of Record; checkout opens in the app.
// ----------------------------------------------------------------------------

const APP_URL =
  process.env.NEXT_PUBLIC_APP_URL || "https://app.faceless-lab.com";

export const metadata: Metadata = {
  title: "Pricing — Simple monthly plans",
  description:
    "Faceless Lab pricing: Silver $9/mo (12 credits), Gold $29/mo (60 credits), Platinum $79/mo (200 credits). One credit makes one song. Free drafts; pay only when you generate. Billed securely via Paddle.",
  alternates: { canonical: "/pricing" },
  openGraph: {
    type: "website",
    url: "/pricing",
    title: "Faceless Lab — Pricing",
    description: "Silver $9 · Gold $29 · Platinum $79 per month. Free drafts, pay only when you generate.",
  },
};

const PLANS = [
  {
    name: "Silver",
    price: 9,
    credits: 12,
    blurb: "For trying ideas.",
    features: ["12 credits / month", "AI Arabic songs", "Free lyric drafts", "Standard support"],
    featured: false,
  },
  {
    name: "Gold",
    price: 29,
    credits: 60,
    blurb: "For weekly drops.",
    features: ["60 credits / month", "Everything in Silver", "Voice persona save & reuse", "Priority queue"],
    featured: true,
  },
  {
    name: "Platinum",
    price: 79,
    credits: 200,
    blurb: "For daily output.",
    features: ["200 credits / month", "Everything in Gold", "Highest priority", "Early access to new features"],
    featured: false,
  },
];

export default function PricingPage() {
  return (
    <main className="min-h-screen bg-bg text-ink overflow-x-clip">
      <SiteNav active="/pricing" />

      <section className="pt-36 pb-8 sm:pt-44 px-5 sm:px-8 text-center">
        <div className="max-w-3xl mx-auto">
          <div className="flex justify-center"><SectionEyebrow text="PRICING" /></div>
          <h1 className="text-[40px] sm:text-6xl font-semibold tracking-[-0.035em] leading-[1.03] mb-5">
            Simple monthly plans.
          </h1>
          <p className="text-lg text-muted max-w-xl mx-auto">
            One credit makes one song. Drafts are free — you only spend a credit when you approve a full generation.
          </p>
        </div>
      </section>

      <section className="px-5 sm:px-8 pb-6">
        <div className="max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-4">
          {PLANS.map((p) => (
            <div
              key={p.name}
              className={`rounded-2xl p-7 flex flex-col ${
                p.featured
                  ? "border-2 border-accent bg-gradient-to-br from-accent/[0.08] to-transparent"
                  : "border border-white/10 bg-white/[0.02]"
              }`}
            >
              {p.featured && (
                <div className="self-start text-[10px] font-bold text-accent tracking-[0.18em] mb-3">MOST POPULAR</div>
              )}
              <h2 className="text-xl font-semibold tracking-tight">{p.name}</h2>
              <p className="text-[13px] text-muted mb-5">{p.blurb}</p>
              <div className="flex items-baseline gap-1 mb-1">
                <span className="text-4xl font-semibold tracking-tight">${p.price}</span>
                <span className="text-muted text-sm">/ month</span>
              </div>
              <div className="text-[13px] text-accent mb-6">{p.credits} credits / month</div>
              <ul className="space-y-2.5 mb-8 flex-1">
                {p.features.map((f) => (
                  <li key={f} className="flex items-start gap-2.5 text-[14px] text-ink/85">
                    <Check className="w-4 h-4 text-accent mt-0.5 shrink-0" />
                    {f}
                  </li>
                ))}
              </ul>
              <a
                href={`${APP_URL}/`}
                className={`inline-flex items-center justify-center gap-2 font-semibold text-[14px] px-5 py-3 rounded-lg transition-colors ${
                  p.featured
                    ? "bg-accent text-bg hover:bg-accent/90"
                    : "bg-white/[0.06] text-ink hover:bg-white/[0.1]"
                }`}
              >
                Choose {p.name}
                <ArrowRight className="w-4 h-4" />
              </a>
            </div>
          ))}
        </div>
      </section>

      <section className="px-5 sm:px-8 py-12">
        <div className="max-w-3xl mx-auto grid grid-cols-1 sm:grid-cols-3 gap-4 text-center">
          {[
            ["Free drafts", "Preview lyrics and cover prompts before spending a single credit."],
            ["Refund on failure", "If a song fails to generate, the credit is returned automatically."],
            ["Cancel anytime", "Manage or cancel your subscription from the app — no lock-in."],
          ].map(([h, b]) => (
            <div key={h} className="border border-white/10 rounded-xl p-5 bg-white/[0.02]">
              <div className="flex justify-center mb-2"><Sparkles className="w-4 h-4 text-accent" /></div>
              <div className="font-semibold text-[15px] mb-1">{h}</div>
              <p className="text-[13px] text-muted leading-relaxed">{b}</p>
            </div>
          ))}
        </div>
        <p className="max-w-3xl mx-auto text-center text-[12px] text-muted/70 mt-8 leading-relaxed">
          Prices in USD. Payments, invoices, and any applicable taxes are processed by Paddle.com, our Merchant of Record.
          See our{" "}
          <a href="/refund" className="underline hover:text-ink">Refund &amp; Cancellation Policy</a> and{" "}
          <a href="/terms" className="underline hover:text-ink">Terms of Service</a>.
        </p>
      </section>

      <SiteFooter />
    </main>
  );
}
