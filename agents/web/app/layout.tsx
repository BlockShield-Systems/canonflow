import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CANONFLOW — Agentic Cinema Pipeline",
  description:
    "Canon-validated beat-to-prompt pipeline. 44 beats, 111 shots, ClickHouse-backed continuity state.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
