import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "cipher",
  description: "Verified developer profiles built from code, challenge data, and reviewed career history."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          {children}
        </div>
      </body>
    </html>
  );
}
