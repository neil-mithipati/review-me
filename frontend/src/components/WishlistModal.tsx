"use client";

import { useEffect, useRef, useState } from "react";
import { getWishlist, removeFromWishlist } from "@/lib/api";
import type { WishlistItem } from "@/lib/types";

const VERDICT_CHIP: Record<string, string> = {
  Buy:     "bg-green-500/20 text-green-400",
  Consider:"bg-amber-500/20 text-amber-400",
  Skip:    "bg-red-500/20   text-red-400",
};

type Props = {
  isOpen: boolean;
  onClose: () => void;
};

export function WishlistModal({ isOpen, onClose }: Props) {
  const [items, setItems] = useState<WishlistItem[]>([]);
  const [loading, setLoading] = useState(false);
  const modalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    getWishlist()
      .then(setItems)
      .finally(() => setLoading(false));
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" || !modalRef.current?.contains(e.target as Node)) {
        onClose();
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  async function handleRemove(id: number) {
    await removeFromWishlist(id);
    setItems((prev) => prev.filter((i) => i.id !== id));
  }

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        ref={modalRef}
        className="glass-heavy rounded-2xl p-6 w-full max-w-md max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-white font-semibold text-lg">Wishlist</h2>
          <button
            onClick={onClose}
            className="text-white/30 hover:text-white transition-colors text-xl leading-none w-7 h-7 flex items-center justify-center"
          >
            ×
          </button>
        </div>

        <div className="flex-1 overflow-y-auto space-y-2">
          {loading && (
            <p className="text-white/30 text-sm text-center py-8">Loading…</p>
          )}

          {!loading && items.length === 0 && (
            <p className="text-white/30 text-sm text-center py-8">
              Your wishlist is empty
            </p>
          )}

          {items.map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between bg-white/[0.05] border border-white/[0.08] rounded-xl px-4 py-3"
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
                className="text-white/25 hover:text-red-400 text-xs transition-colors ml-4"
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
