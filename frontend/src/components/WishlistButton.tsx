"use client";

import { useState } from "react";
import { WishlistModal } from "./WishlistModal";

export function WishlistButton() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="text-white/40 hover:text-white transition-colors text-lg"
        aria-label="Open wishlist"
      >
        ★
      </button>
      <WishlistModal isOpen={open} onClose={() => setOpen(false)} />
    </>
  );
}
