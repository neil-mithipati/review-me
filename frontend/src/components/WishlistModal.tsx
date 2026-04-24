"use client";

import { useEffect, useState } from "react";
import { getWishlist, removeFromWishlist } from "@/lib/api";
import type { WishlistItem } from "@/lib/types";

const VERDICT_CHIP: Record<string, string> = {
  Buy: "bg-green-500/20 text-green-400",
  Consider: "bg-amber-500/20 text-amber-400",
  Skip: "bg-red-500/20 text-red-400",
};

type Props = {
  isOpen: boolean;
  onClose: () => void;
};

export function WishlistModal({ isOpen, onClose }: Props) {
  const [items, setItems] = useState<WishlistItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    getWishlist()
      .then(setItems)
      .finally(() => setLoading(false));
  }, [isOpen]);

  async function handleRemove(id: number) {
    await removeFromWishlist(id);
    setItems((prev) => prev.filter((i) => i.id !== id));
  }

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 w-full max-w-md max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-white font-semibold text-lg">Your Wishlist ★</h2>
          <button
            onClick={onClose}
            className="text-zinc-500 hover:text-white transition-colors text-xl leading-none"
          >
            ×
          </button>
        </div>

        <div className="flex-1 overflow-y-auto space-y-3">
          {loading && (
            <p className="text-zinc-500 text-sm text-center py-8">Loading…</p>
          )}

          {!loading && items.length === 0 && (
            <p className="text-zinc-500 text-sm text-center py-8">
              Your wishlist is empty
            </p>
          )}

          {items.map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between bg-zinc-800 rounded-xl px-4 py-3"
            >
              <div>
                <p className="text-white text-sm font-medium">{item.product_name}</p>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full mt-1 inline-block ${
                    VERDICT_CHIP[item.verdict] ?? VERDICT_CHIP.Consider
                  }`}
                >
                  {item.verdict}
                </span>
              </div>
              <button
                onClick={() => handleRemove(item.id)}
                className="text-zinc-500 hover:text-red-400 text-xs transition-colors ml-4"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
