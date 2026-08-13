// ----------------------------------------------------------------------------
// SHARED SITE CHROME — server components used by the content/legal routes
// (/pricing, /terms, /privacy, /refund, /contact). Mirrors the landing-page
// dark/gold aesthetic (bg-bg / text-ink / text-accent) but is dependency-free
// (no framer-motion) so it can be imported by Server Components.
//
// The Footer intentionally links every legal + product page so any of them is
// reachable in <= 2 clicks from the homepage — a Paddle (Merchant of Record)
// verification requirement.
// ----------------------------------------------------------------------------
import Link from "next/link";
import { SparkleLogo } from "@/components/sparkle-logo";

const APP_URL =
  process.env.NEXT_PUBLIC_APP_URL || "https://app.faceless-lab.com";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/pricing", label: "Pricing" },
  { href: "/about", label: "About" },
  { href: "/contact", label: "Contact" },
];

export function SiteNav({ active }: { active?: string }) {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 backdrop-blur-xl bg-bg/85 border-b border-white/[0.06]">
      <div className="max-w-7xl mx-auto px-5 sm:px-8 h-16 flex items-center">
        <Link href="/" className="flex items-center gap-2.5">
          <SparkleLogo size={28} />
          <span className="font-semibold text-[15px] tracking-tight">Faceless Lab</span>
        </Link>
        <nav className="hidden md:flex items-center gap-7 ml-12 text-[13px]">
          {NAV.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`${active === l.href ? "text-ink" : "text-muted hover:text-ink"} transition-colors`}
            >
              {l.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-1 sm:gap-2">
          <a href={`${APP_URL}/`} className="text-[13px] text-muted hover:text-ink px-3 py-2">Sign in</a>
          <a
            href={`${APP_URL}/`}
            className="bg-accent text-bg font-semibold text-[13px] px-4 py-2 rounded-md hover:bg-accent/90 transition-colors"
          >
            Start free
          </a>
        </div>
      </div>
    </header>
  );
}

export function SiteFooter() {
  const year = new Date().getFullYear();
  const cols: { h: string; links: [string, string][] }[] = [
    { h: "Product", links: [["/", "Home"], ["/pricing", "Pricing"], ["/about", "About"], ["/press", "Press"]] },
    { h: "Legal", links: [["/terms", "Terms of Service"], ["/privacy", "Privacy Policy"], ["/refund", "Refund & Cancellation"], ["/contact", "Contact"]] },
  ];
  return (
    <footer className="border-t border-white/[0.06] py-12 px-5 sm:px-8">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row gap-10 sm:gap-16">
        <div className="flex items-start gap-2.5">
          <SparkleLogo size={22} />
          <span className="text-[13px] text-muted leading-relaxed">
            Faceless Lab · faceless-lab.com
            <br />Dubai, United Arab Emirates
          </span>
        </div>
        <div className="sm:ml-auto flex gap-12 sm:gap-16">
          {cols.map((c) => (
            <div key={c.h}>
              <div className="text-[11px] font-semibold text-ink/70 tracking-wide uppercase mb-3">{c.h}</div>
              <ul className="space-y-2 text-[13px] text-muted">
                {c.links.map(([href, label]) => (
                  <li key={href}>
                    <Link href={href} className="hover:text-ink transition-colors">{label}</Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
      <div className="max-w-7xl mx-auto mt-10 pt-6 border-t border-white/[0.04] text-[12px] text-muted/70 leading-relaxed">
        Payments are securely processed by{" "}
        <a href="https://www.paddle.com" className="underline hover:text-ink" rel="noopener noreferrer" target="_blank">Paddle.com</a>{" "}
        as our Merchant of Record. Billing, invoices, and tax are handled by Paddle. © {year} Faceless Lab.
      </div>
    </footer>
  );
}

export function SectionEyebrow({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-3 mb-4">
      <div className="w-8 h-px bg-accent" />
      <span className="text-[10px] font-bold text-accent tracking-[0.22em]">{text}</span>
    </div>
  );
}

// Wrapper for the text-heavy legal pages: nav, a titled hero with a
// "last updated" line + a plain-language review banner, a readable prose
// column, and the shared footer.
export function LegalShell({
  eyebrow,
  title,
  updated,
  children,
}: {
  eyebrow: string;
  title: string;
  updated: string;
  children: React.ReactNode;
}) {
  return (
    <main className="min-h-screen bg-bg text-ink overflow-x-clip">
      <SiteNav />
      <section className="pt-36 pb-10 sm:pt-44 px-5 sm:px-8 border-b border-white/[0.05]">
        <div className="max-w-3xl mx-auto">
          <SectionEyebrow text={eyebrow} />
          <h1 className="text-[38px] sm:text-5xl font-semibold tracking-[-0.03em] leading-[1.05] mb-4">{title}</h1>
          <p className="text-[13px] text-muted">Last updated: {updated}</p>
        </div>
      </section>
      <section className="py-14 px-5 sm:px-8">
        <div className="max-w-3xl mx-auto space-y-10 text-[15px] text-ink/85 leading-relaxed">
          {children}
        </div>
      </section>
      <SiteFooter />
    </main>
  );
}

// Small building blocks for legal prose.
export function H2({ children }: { children: React.ReactNode }) {
  return <h2 className="text-xl sm:text-2xl font-semibold tracking-tight text-ink mb-3 mt-2">{children}</h2>;
}
export function P({ children }: { children: React.ReactNode }) {
  return <p className="mb-3">{children}</p>;
}
export function UL({ children }: { children: React.ReactNode }) {
  return <ul className="list-disc pl-5 space-y-1.5 mb-3 marker:text-accent/60">{children}</ul>;
}
