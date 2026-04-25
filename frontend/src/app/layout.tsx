import type { Metadata, Viewport } from "next";
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

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased text-white`}
      >
        <header className="fixed top-0 left-0 right-0 z-40 flex items-center justify-between px-6 pb-4 pt-[calc(1rem+env(safe-area-inset-top,0px))] bg-black/25 backdrop-blur-2xl border-b border-cyan-500/20">
          <a href="/" className="text-cyan-400/60 text-sm font-medium hover:text-cyan-300 transition-colors tracking-widest uppercase">
            Signal
          </a>
          <WishlistButton />
        </header>
        <main className="pt-[calc(4rem+env(safe-area-inset-top,0px))]">{children}</main>
      </body>
    </html>
  );
}
