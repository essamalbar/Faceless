import type { Metadata } from "next";
import { LegalShell, H2, P, UL } from "@/components/site-chrome";

export const metadata: Metadata = {
  title: "Terms of Service",
  description:
    "The terms governing your use of Faceless Lab — an AI studio for Arabic songs. Covers accounts, subscriptions billed via Paddle, credits, acceptable use, content ownership, and liability.",
  alternates: { canonical: "/terms" },
};

const CONTACT = "support@faceless-lab.com";

export default function TermsPage() {
  return (
    <LegalShell eyebrow="LEGAL" title="Terms of Service" updated="12 August 2026">
      <div className="rounded-xl border border-accent/25 bg-accent/[0.05] px-5 py-4 text-[13px] text-ink/80 leading-relaxed">
        This is a plain-language template provided for transparency. It is not legal advice; please have it reviewed by a
        qualified lawyer for your jurisdiction before relying on it.
      </div>

      <div>
        <H2>1. Who we are &amp; acceptance</H2>
        <P>
          Faceless Lab (&quot;Faceless Lab&quot;, &quot;we&quot;, &quot;us&quot;) is an AI content studio that generates
          original Arabic songs. It is operated as a sole proprietorship based in Dubai, United Arab Emirates.
          By creating an account or using the service (the &quot;Service&quot;), you agree to these Terms. If you do not
          agree, do not use the Service.
        </P>
      </div>

      <div>
        <H2>2. Eligibility &amp; accounts</H2>
        <P>
          You must be at least 18 years old and able to form a binding contract. You are responsible for your account,
          for keeping your credentials secure, and for all activity under your account. Provide accurate information and
          keep it up to date.
        </P>
      </div>

      <div>
        <H2>3. Subscriptions, billing &amp; Merchant of Record</H2>
        <P>
          Paid plans are sold on a recurring monthly subscription. <strong>Our order process and payments are conducted
          by our online reseller and Merchant of Record, Paddle.com</strong>, which handles billing, invoicing, payment
          methods, and applicable taxes. Your purchase is subject to Paddle&apos;s buyer terms in addition to these Terms.
        </P>
        <UL>
          <li>Plans (billed monthly, in USD): Silver $9, Gold $29, Platinum $79.</li>
          <li>Subscriptions renew automatically each month until cancelled.</li>
          <li>You can cancel at any time from the app; cancellation stops future renewals.</li>
          <li>See our <a href="/refund" className="underline hover:text-ink">Refund &amp; Cancellation Policy</a>.</li>
        </UL>
      </div>

      <div>
        <H2>4. Credits</H2>
        <P>
          Each plan grants a monthly allowance of credits. One credit is consumed when you approve a full generation
          (for example, a complete song). Generating drafts (lyrics and cover prompts) is free and does not
          consume credits. Credits are for use within the Service, have no cash value, and are not transferable. Unless
          stated otherwise, unused credits do not roll over between billing periods.
        </P>
      </div>

      <div>
        <H2>5. Acceptable use</H2>
        <P>You agree not to use the Service to create, upload, or distribute content that:</P>
        <UL>
          <li>is unlawful, or infringes anyone&apos;s intellectual-property, privacy, or other rights;</li>
          <li>sexualizes minors, or depicts real people without their consent in a deceptive or harmful way;</li>
          <li>is hateful, harassing, or incites violence; or</li>
          <li>impersonates others or is intended to defraud or deceive.</li>
        </UL>
        <P>
          We screen inputs and may refuse, remove, or suspend content or accounts that violate these rules. Copyright and
          takedown requests are handled per our{" "}
          <a href="/refund" className="underline hover:text-ink">policies</a> and via {CONTACT}.
        </P>
      </div>

      <div>
        <H2>6. Your content &amp; ownership</H2>
        <P>
          You retain ownership of the content you generate, subject to your having the rights to any material you submit
          as input. You are responsible for ensuring your inputs and your use of the outputs are lawful. You grant us a
          limited license to process, store, and deliver your content solely to operate and improve the Service.
        </P>
        <P>
          Outputs are produced by AI models and may be imperfect, inaccurate, or resemble existing works. You are
          responsible for reviewing outputs before publishing or distributing them.
        </P>
      </div>

      <div>
        <H2>7. Third-party services</H2>
        <P>
          The Service relies on third parties including Paddle (payments), and AI/model and infrastructure providers used
          to generate and deliver content. Their availability and terms may affect the Service.
        </P>
      </div>

      <div>
        <H2>8. Termination</H2>
        <P>
          You may stop using the Service and cancel your subscription at any time. We may suspend or terminate access for
          violations of these Terms or misuse of the Service. You can export or delete your data from within the app.
        </P>
      </div>

      <div>
        <H2>9. Disclaimers &amp; limitation of liability</H2>
        <P>
          The Service is provided &quot;as is&quot; without warranties of any kind. To the maximum extent permitted by
          law, we are not liable for indirect, incidental, or consequential damages, and our total liability is limited
          to the amount you paid for the Service in the three months before the claim.
        </P>
      </div>

      <div>
        <H2>10. Changes &amp; governing law</H2>
        <P>
          We may update these Terms; material changes will be reflected by the &quot;last updated&quot; date above. These
          Terms are governed by the laws of the United Arab Emirates (Emirate of Dubai), without regard to conflict-of-law
          rules.
        </P>
      </div>

      <div>
        <H2>11. Contact</H2>
        <P>
          Questions about these Terms: <a href={`mailto:${CONTACT}`} className="underline hover:text-ink">{CONTACT}</a>.
          Billing questions are handled by Paddle, our Merchant of Record.
        </P>
      </div>
    </LegalShell>
  );
}
