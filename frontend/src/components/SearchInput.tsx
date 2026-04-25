"use client";

import { FormEvent, useEffect, useState } from "react";

// "I'm feeling lucky" has 3 slots out of 11 (~27%) — highest weight of any single item
const PLACEHOLDERS = [
  "I'm feeling lucky",
  "I'm feeling lucky",
  "I'm feeling lucky",
  "asking for a friend (it's me)",
  "my cart has been open for 3 days",
  "please talk me out of this",
  "it's an investment, not a purchase",
  "I've watched 12 YouTube videos about…",
  "my credit card is already out",
  "3am, bad idea, or…",
  "just doing research, I swear",
];

function pickRandom(exclude?: string): string {
  let pick: string;
  do {
    pick = PLACEHOLDERS[Math.floor(Math.random() * PLACEHOLDERS.length)];
  } while (pick === exclude && PLACEHOLDERS.length > 1);
  return pick;
}

type Props = {
  onSubmit: (query: string) => void;
  initialValue?: string;
  loading?: boolean;
};

export function SearchInput({ onSubmit, initialValue = "", loading = false }: Props) {
  const [value, setValue] = useState(initialValue);
  const [placeholder, setPlaceholder] = useState("I'm feeling lucky");

  useEffect(() => {
    // Randomize only on the client to avoid SSR/client hydration mismatch
    setPlaceholder(pickRandom());
    const timer = setInterval(() => {
      setPlaceholder((prev) => pickRandom(prev));
    }, 10000);
    return () => clearInterval(timer);
  }, []);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = value.trim();
    if (trimmed) onSubmit(trimmed);
  }

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-xl">
      <div className="relative">
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={placeholder}
          disabled={loading}
          className="w-full bg-cyan-950/20 backdrop-blur-xl border border-cyan-500/20 text-cyan-50 placeholder-cyan-300/25 rounded-full px-6 py-4 text-base focus:outline-none focus:border-cyan-400/50 focus:bg-cyan-950/30 transition-all duration-150 disabled:opacity-50 pr-14"
        />
        {loading && (
          <div className="absolute right-5 top-1/2 -translate-y-1/2 pointer-events-none">
            <span className="inline-block w-4 h-4 border-2 border-white/20 border-t-white/60 rounded-full animate-spin" />
          </div>
        )}
      </div>
    </form>
  );
}
