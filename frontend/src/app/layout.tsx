import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "StockER | Probabilistic Causal Event Forecasting",
  description: "Evidence-scoped causal event forecasting with explicit uncertainty.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className="h-full antialiased"
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
