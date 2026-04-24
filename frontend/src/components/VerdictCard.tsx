"use client";

import { useCyclingText } from "@/hooks/useCyclingText";
import { LOADING_VERBS } from "@/lib/loadingVerbs";
import type { VerdictState } from "@/lib/types";

const VERDICT_STYLES: Record<string, string> = {
  Buy: "bg-green-500/20 text-green-400 border-green-500/30",
  Consider: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  Skip: "bg-red-500/20 text-red-400 border-red-500/30",
};

type Props = {
  verdict: VerdictState;
  productName: string;
};

export function VerdictCard({ verdict, productName }: Props) {
  const loadingVerb = useCyclingText(LOADING_VERBS.orchestrator, 2500);

  if (verdict.status === "loading" || verdict.status === "idle") {
    return (
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-8 w-full animate-pulse">
        <p className="text-xs text-zinc-500 uppercase tracking-widest mb-4">synthesizing verdict</p>
        <div className="h-10 bg-zinc-800 rounded-lg w-32 mb-4" />
        <p className="text-zinc-500 text-sm italic transition-opacity duration-500">{loadingVerb}</p>
      </div>
    );
  }

  if (verdict.status === "error" || !verdict.data) {
    return (
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-8 w-full">
        <p className="text-zinc-400">Unable to generate a verdict. Please try again.</p>
      </div>
    );
  }

  const { data } = verdict;
  const verdictStyle = VERDICT_STYLES[data.verdict] ?? VERDICT_STYLES.Consider;

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-8 w-full">
      {productName && (
        <p className="text-zinc-400 text-sm mb-3">{productName}</p>
      )}
      <span
        className={`inline-block border rounded-full px-6 py-2 text-2xl font-bold mb-5 ${verdictStyle}`}
      >
        {data.verdict}
      </span>
      <p className="text-zinc-200 text-base leading-relaxed mb-4">{data.summary}</p>
      {data.notable_disagreements && (
        <div className="border-l-2 border-zinc-600 pl-4 mt-4">
          <p className="text-zinc-400 text-sm italic">{data.notable_disagreements}</p>
        </div>
      )}
    </div>
  );
}
