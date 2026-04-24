"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { addToWishlist } from "@/lib/api";
import type { VerdictData } from "@/lib/types";

type Props = {
  verdictData: VerdictData;
  productName: string;
  reviewId: string;
};

const PRIMARY_STYLES: Record<string, string> = {
  buy: "bg-green-500 hover:bg-green-400 text-white px-8 py-3 rounded-full text-base font-semibold",
  consider: "bg-amber-500 hover:bg-amber-400 text-white px-8 py-3 rounded-full text-base font-semibold",
  skip: "bg-red-500 hover:bg-red-400 text-white px-8 py-3 rounded-full text-base font-semibold",
};

const SECONDARY_STYLE =
  "border border-zinc-600 text-zinc-400 hover:text-zinc-200 hover:border-zinc-400 px-6 py-2 rounded-full text-sm transition-colors";

export function ActionButtons({ verdictData, productName, reviewId }: Props) {
  const router = useRouter();
  const [wishlisted, setWishlisted] = useState(false);
  const [wishlistLoading, setWishlistLoading] = useState(false);
  const { recommended_action, verdict, buy_link } = verdictData;

  async function handleConsider() {
    if (wishlisted || wishlistLoading) return;
    setWishlistLoading(true);
    try {
      await addToWishlist(productName, verdict, reviewId);
      setWishlisted(true);
    } finally {
      setWishlistLoading(false);
    }
  }

  function handleBuy() {
    const url = buy_link ?? `https://www.amazon.com/s?k=${encodeURIComponent(productName)}`;
    window.open(url, "_blank", "noopener,noreferrer");
  }

  function handleSkip() {
    router.push("/");
  }

  const isPrimary = (action: string) => recommended_action === action;

  return (
    <div className="flex flex-wrap items-center justify-center gap-4">
      <button
        onClick={handleBuy}
        className={isPrimary("buy") ? PRIMARY_STYLES.buy : SECONDARY_STYLE}
      >
        Buy
      </button>

      <button
        onClick={handleConsider}
        disabled={wishlisted || wishlistLoading}
        className={
          isPrimary("consider")
            ? `${PRIMARY_STYLES.consider} disabled:opacity-60`
            : `${SECONDARY_STYLE} disabled:opacity-60`
        }
      >
        {wishlisted ? "Added to Wishlist ★" : wishlistLoading ? "Adding…" : "Consider"}
      </button>

      <button
        onClick={handleSkip}
        className={isPrimary("skip") ? PRIMARY_STYLES.skip : SECONDARY_STYLE}
      >
        Skip
      </button>
    </div>
  );
}
