import type { Metadata } from "next";
import { Mail, CreditCard, ShieldAlert, MapPin } from "lucide-react";
import { SiteNav, SiteFooter, SectionEyebrow } from "@/components/site-chrome";

export const metadata: Metadata = {
  title: "Contact",
  description:
    "Get in touch with Faceless Lab — support, billing (via Paddle), and copyright/abuse reports. Based in Dubai, United Arab Emirates.",
  alternates: { canonical: "/contact" },
};

const SUPPORT = "support@faceless-lab.com";
const ABUSE = "abuse@faceless-lab.com";

export default function ContactPage() {
  const cards = [
    {
      icon: Mail,
      title: "Support",
      body: "Questions about your account, generations, or how something works.",
      email: SUPPORT,
    },
    {
      icon: CreditCard,
      title: "Billing",
      body: "Payments, invoices, and refunds are handled by Paddle, our Merchant of Record — reply to any Paddle receipt, or email us and we'll help.",
      email: SUPPORT,
    },
    {
      icon: ShieldAlert,
      title: "Copyright / DMCA & abuse",
      body: "Report content that infringes your rights or violates our acceptable-use rules.",
      email: ABUSE,
    },
  ];

  return (
    <main className="min-h-screen bg-bg text-ink overflow-x-clip">
      <SiteNav active="/contact" />

      <section className="pt-36 pb-8 sm:pt-44 px-5 sm:px-8">
        <div className="max-w-3xl mx-auto">
          <SectionEyebrow text="CONTACT" />
          <h1 className="text-[40px] sm:text-6xl font-semibold tracking-[-0.035em] leading-[1.03] mb-5">
            Get in touch.
          </h1>
          <p className="text-lg text-muted max-w-xl">
            We&apos;re a small team and read every message. We aim to reply within two business days.
          </p>
        </div>
      </section>

      <section className="px-5 sm:px-8 pb-6">
        <div className="max-w-3xl mx-auto grid grid-cols-1 sm:grid-cols-3 gap-4">
          {cards.map((c) => (
            <div key={c.title} className="border border-white/10 rounded-xl p-6 bg-white/[0.02] flex flex-col">
              <c.icon className="w-5 h-5 text-accent mb-3" />
              <div className="font-semibold text-[15px] mb-1.5">{c.title}</div>
              <p className="text-[13px] text-muted leading-relaxed flex-1">{c.body}</p>
              <a href={`mailto:${c.email}`} className="mt-4 text-[13px] text-accent hover:underline break-all">
                {c.email}
              </a>
            </div>
          ))}
        </div>
      </section>

      <section className="px-5 sm:px-8 py-10">
        <div className="max-w-3xl mx-auto border border-white/10 rounded-xl p-6 bg-white/[0.02] flex items-start gap-3">
          <MapPin className="w-5 h-5 text-accent mt-0.5 shrink-0" />
          <div className="text-[14px] text-ink/85 leading-relaxed">
            <div className="font-semibold mb-1">Faceless Lab</div>
            Dubai, United Arab Emirates
            <div className="text-[12px] text-muted/70 mt-2">
              Order fulfillment and payments are provided by Paddle.com Market Ltd as our Merchant of Record.
            </div>
          </div>
        </div>
      </section>

      <SiteFooter />
    </main>
  );
}
