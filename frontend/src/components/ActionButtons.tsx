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

const BASE_BTN = "w-full sm:w-auto flex items-center justify-center rounded-full font-semibold transition-all duration-150";

const PRIMARY_STYLES: Record<string, string> = {
  buy:     `${BASE_BTN} bg-green-500/80 hover:bg-green-500 active:bg-green-600 backdrop-blur-sm border border-green-400/30 text-white px-8 py-3.5 text-base`,
  consider:`${BASE_BTN} bg-amber-500/80 hover:bg-amber-500 active:bg-amber-600 backdrop-blur-sm border border-amber-400/30 text-white px-8 py-3.5 text-base`,
  skip:    `${BASE_BTN} bg-red-500/80   hover:bg-red-500   active:bg-red-600   backdrop-blur-sm border border-red-400/30   text-white px-8 py-3.5 text-base`,
};

const SECONDARY_STYLE =
  `${BASE_BTN} bg-white/[0.06] hover:bg-white/[0.12] active:bg-white/[0.18] backdrop-blur-sm border border-white/[0.1] hover:border-white/[0.2] text-white/60 hover:text-white px-6 py-3 text-sm`;

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
    <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-center gap-3 w-full sm:w-auto">
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
          (isPrimary("consider") ? PRIMARY_STYLES.consider : SECONDARY_STYLE) +
          " disabled:opacity-50"
        }
      >
        {wishlisted ? "Added to Wishlist" : wishlistLoading ? "Adding…" : "Consider"}
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
