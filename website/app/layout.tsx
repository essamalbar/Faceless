import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Faceless — AI Arabic horror shorts",
  description:
    "Write a one-line premise. The AI turns it into a full Arabic script, then generates a cinematic short. Free to write, subscribe to render.",
  openGraph: {
    title: "Faceless — AI Arabic horror shorts",
    description:
      "Write a premise. AI generates a full Arabic short. Free to try.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-bg text-ink antialiased">{children}</body>
    </html>
  );
}
