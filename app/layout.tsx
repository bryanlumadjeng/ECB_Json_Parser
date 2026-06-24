import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "ECB Model Documentation Evaluator",
  description: "Evaluate internal model documentation against ECB supervisory requirements",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <style>{`
          *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
          body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                 background: #f5f7fa; color: #1a1a2e; min-height: 100vh; }
          a { color: #2563eb; text-decoration: none; }
          a:hover { text-decoration: underline; }
        `}</style>
      </head>
      <body>{children}</body>
    </html>
  );
}
