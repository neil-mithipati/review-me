"use client";

import { FormEvent, useState } from "react";

type Props = {
  onSubmit: (query: string) => void;
  initialValue?: string;
  loading?: boolean;
};

export function SearchInput({ onSubmit, initialValue = "", loading = false }: Props) {
  const [value, setValue] = useState(initialValue);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = value.trim();
    if (trimmed) onSubmit(trimmed);
  }

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-xl flex gap-2">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Search for a product..."
        disabled={loading}
        className="flex-1 bg-zinc-800 border border-zinc-700 text-white placeholder-zinc-500 rounded-full px-5 py-3 text-base focus:outline-none focus:border-zinc-500 disabled:opacity-50"
      />
      <button
        type="submit"
        disabled={loading || !value.trim()}
        className="bg-white text-zinc-900 font-semibold rounded-full px-6 py-3 text-sm hover:bg-zinc-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
      >
        {loading ? (
          <span className="inline-block w-4 h-4 border-2 border-zinc-400 border-t-zinc-900 rounded-full animate-spin" />
        ) : (
          "Search"
        )}
      </button>
    </form>
  );
}
