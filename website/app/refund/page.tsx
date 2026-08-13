import type { Metadata } from "next";
import { LegalShell, H2, P, UL } from "@/components/site-chrome";

export const metadata: Metadata = {
  title: "Refund & Cancellation Policy",
  description:
    "How cancellations and refunds work at Faceless Lab: cancel anytime to stop renewals, automatic credit refunds when a generation fails, and how to request a refund through Paddle, our Merchant of Record.",
  alternates: { canonical: "/refund" },
};

const CONTACT = "support@faceless-lab.com";

export default function RefundPage() {
  return (
    <LegalShell eyebrow="LEGAL" title="Refund & Cancellation Policy" updated="12 August 2026">
      <div className="rounded-xl border border-accent/25 bg-accent/[0.05] px-5 py-4 text-[13px] text-ink/80 leading-relaxed">
        Plain-language template for transparency, not legal advice. Please have it reviewed for your jurisdiction. Because
        Paddle is our Merchant of Record, Paddle&apos;s buyer terms and refund handling also apply to your purchase.
      </div>

      <div>
        <H2>Cancelling your subscription</H2>
        <UL>
          <li>You can cancel at any time from the app&apos;s billing settings.</li>
          <li>Cancellation stops future monthly renewals. You keep access to any remaining paid time and unused credits until the end of the current billing period.</li>
          <li>We don&apos;t charge cancellation fees.</li>
        </UL>
      </div>

      <div>
        <H2>Refund on failed generations</H2>
        <P>
          You should only pay for output that actually delivers. If a generation fails after a credit is charged, the
          Service <strong>automatically returns that credit</strong> to your balance. If you believe a credit was charged
          for a failed generation and not returned, contact us and we&apos;ll make it right.
        </P>
      </div>

      <div>
        <H2>Subscription refunds</H2>
        <P>
          Subscriptions provide access to a monthly credit allowance (a digital service). Because access and credits are
          delivered immediately:
        </P>
        <UL>
          <li>Credits already used to generate content are generally non-refundable.</li>
          <li>If you were charged in error, charged twice, or could not use the Service due to a fault on our side, you may request a refund.</li>
          <li>We consider reasonable refund requests made shortly after a charge in good faith.</li>
        </UL>
      </div>

      <div>
        <H2>How to request a refund</H2>
        <P>
          Email <a href={`mailto:${CONTACT}`} className="underline hover:text-ink">{CONTACT}</a> with the email on your
          account and the approximate charge date. Refunds are issued through <strong>Paddle</strong>, our Merchant of
          Record, back to your original payment method. Paddle may also be contacted directly via the receipt it sends
          you for any billing or payment question.
        </P>
      </div>

      <div>
        <H2>Chargebacks</H2>
        <P>
          If you have a billing concern, please contact us first — we can usually resolve it faster than a chargeback.
          Fraudulent chargebacks may result in loss of access.
        </P>
      </div>
    </LegalShell>
  );
}
