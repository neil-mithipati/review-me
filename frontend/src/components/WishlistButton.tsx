"use client";

import { useState } from "react";
import { WishlistModal } from "./WishlistModal";

export function WishlistButton() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="text-zinc-400 hover:text-white transition-colors text-xl"
        aria-label="Open wishlist"
      >
        ★
      </button>
      <WishlistModal isOpen={open} onClose={() => setOpen(false)} />
    </>
  );
}
