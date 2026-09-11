import type { Metadata } from "next";

import { AuthProvider } from "@/lib/auth-context";
import { ThemeProvider } from "@/components/common/theme-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "WillChain SL",
  description: "Secure digital will management",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <ThemeProvider><AuthProvider>{children}</AuthProvider></ThemeProvider>
      </body>
    </html>
  );
}
