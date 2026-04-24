import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { WishlistButton } from "@/components/WishlistButton";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "review-me",
  description: "Should I buy it?",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-zinc-950 text-white`}
      >
        <header className="fixed top-0 left-0 right-0 z-40 flex items-center justify-between px-6 py-4 bg-zinc-950/80 backdrop-blur-sm border-b border-zinc-900">
          <a href="/" className="text-zinc-400 text-sm font-medium hover:text-white transition-colors">
            review-me
          </a>
          <WishlistButton />
        </header>
        <main className="pt-16">{children}</main>
      </body>
    </html>
  );
}
