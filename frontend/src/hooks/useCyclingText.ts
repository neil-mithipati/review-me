"use client";

import { useEffect, useState } from "react";

export function useCyclingText(items: string[], interval = 2000): string {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (items.length <= 1) return;
    const timer = setInterval(() => {
      setIndex((i) => (i + 1) % items.length);
    }, interval);
    return () => clearInterval(timer);
  }, [items, interval]);

  return items[index] ?? "";
}
