import type { Metadata } from "next";
import { LegalShell, H2, P, UL } from "@/components/site-chrome";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description:
    "How Faceless Lab collects, uses, and protects your data. We store your account email and the content you generate; payments are handled by Paddle. You can export or delete your data at any time.",
  alternates: { canonical: "/privacy" },
};

const CONTACT = "support@faceless-lab.com";

export default function PrivacyPage() {
  return (
    <LegalShell eyebrow="LEGAL" title="Privacy Policy" updated="12 August 2026">
      <div className="rounded-xl border border-accent/25 bg-accent/[0.05] px-5 py-4 text-[13px] text-ink/80 leading-relaxed">
        This is a plain-language template for transparency, not legal advice. Please have it reviewed by a qualified
        professional before relying on it.
      </div>

      <div>
        <H2>1. What we collect</H2>
        <UL>
          <li><strong>Account data:</strong> your email address and authentication details (managed by our auth provider, Supabase).</li>
          <li><strong>Content you create:</strong> the prompts, themes, and lyrics you enter, and the songs, lyrics, and cover images you generate.</li>
          <li><strong>Usage &amp; technical data:</strong> logs, device/browser information, and diagnostics used to run and secure the Service.</li>
          <li><strong>Billing data:</strong> handled by <strong>Paddle</strong>, our Merchant of Record. Paddle processes your payment details — <strong>we do not store your full card numbers</strong>. We keep a record of your plan, credit ledger, and transaction references.</li>
        </UL>
      </div>

      <div>
        <H2>2. How we use it</H2>
        <UL>
          <li>To provide the Service — generate and deliver your content, and track your credit balance.</li>
          <li>To operate subscriptions and grant credits when Paddle confirms a payment.</li>
          <li>To secure the Service, prevent abuse, and comply with legal obligations.</li>
          <li>To communicate service and account notices.</li>
        </UL>
      </div>

      <div>
        <H2>3. Who we share it with</H2>
        <P>We share data only with service providers that help us run Faceless Lab:</P>
        <UL>
          <li><strong>Paddle</strong> — payments, invoicing, tax (Merchant of Record).</li>
          <li><strong>Supabase</strong> — authentication and database.</li>
          <li><strong>AI / model &amp; cloud infrastructure providers</strong> — to generate and host content.</li>
        </UL>
        <P>We do not sell your personal data.</P>
      </div>

      <div>
        <H2>4. Retention</H2>
        <P>
          We keep your account and content while your account is active. Financial records (e.g. the credit ledger and
          transaction references) may be retained longer where required for tax, accounting, or dispute purposes.
        </P>
      </div>

      <div>
        <H2>5. Your rights &amp; controls</H2>
        <P>
          You can <strong>export</strong> your data or <strong>delete</strong> your account and content at any time from
          the app&apos;s settings (Danger zone). Deleting your account removes your personal profile and generated content;
          retained financial records are anonymized where possible. To exercise any privacy right, contact us at {CONTACT}.
        </P>
      </div>

      <div>
        <H2>6. Cookies</H2>
        <P>
          We use essential cookies/local storage for sign-in and session management. Payment pages hosted by Paddle may
          set their own cookies under Paddle&apos;s privacy policy.
        </P>
      </div>

      <div>
        <H2>7. International transfers &amp; security</H2>
        <P>
          Your data may be processed in countries other than yours by the providers listed above. We rely on their
          security and contractual protections and take reasonable measures to protect your data, though no method of
          transmission or storage is 100% secure.
        </P>
      </div>

      <div>
        <H2>8. Children</H2>
        <P>The Service is not directed to children under 18, and we do not knowingly collect their data.</P>
      </div>

      <div>
        <H2>9. Changes &amp; contact</H2>
        <P>
          We may update this policy; the &quot;last updated&quot; date reflects the latest version. Questions or requests:{" "}
          <a href={`mailto:${CONTACT}`} className="underline hover:text-ink">{CONTACT}</a>. For payment-related data,
          Paddle is the Merchant of Record and its privacy policy also applies.
        </P>
      </div>
    </LegalShell>
  );
}
