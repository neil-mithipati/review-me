"use client";

import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { SearchInput } from "@/components/SearchInput";
import { WishlistButton } from "@/components/WishlistButton";
import { startReview } from "@/lib/api";

export function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const isReviewPage = pathname?.startsWith("/review/");
  const [loading, setLoading] = useState(false);

  async function handleSearch(query: string) {
    setLoading(true);
    try {
      const res = await startReview(query);
      if (res.status === "running") {
        router.push(`/review/${res.review_id}`);
      } else {
        router.push("/");
      }
    } catch {
      router.push("/");
    } finally {
      setLoading(false);
    }
  }

  if (!isReviewPage) {
    return (
      <div className="fixed top-[calc(1rem+env(safe-area-inset-top,0px))] right-4 z-40">
        <WishlistButton />
      </div>
    );
  }

  return (
    <header className="fixed top-0 left-0 right-0 z-40 flex items-center gap-6 px-4 sm:px-6 py-3 pt-[calc(0.75rem+env(safe-area-inset-top,0px))] bg-black/30 backdrop-blur-2xl border-b border-white/[0.06]">
      <a href="/" className="app-title text-xl font-bold tracking-tight select-none shrink-0">
        Signal
      </a>
      <div className="w-48 sm:w-64 shrink-0">
        <SearchInput onSubmit={handleSearch} loading={loading} compact />
      </div>
      <div className="ml-auto shrink-0">
        <WishlistButton />
      </div>
    </header>
  );
}
