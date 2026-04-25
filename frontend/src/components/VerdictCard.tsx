"use client";

import { useCyclingText } from "@/hooks/useCyclingText";
import { LOADING_VERBS } from "@/lib/loadingVerbs";
import type { VerdictState } from "@/lib/types";

const VERDICT_STYLES: Record<string, { chip: string; glow: string; border: string }> = {
  Buy:     { chip: "bg-green-500/20 text-green-400 border-green-500/30", glow: "shadow-green-500/10",  border: "border-green-500/20" },
  Consider:{ chip: "bg-amber-500/20 text-amber-400 border-amber-500/30", glow: "shadow-amber-500/10",  border: "border-amber-500/20" },
  Skip:    { chip: "bg-red-500/20   text-red-400   border-red-500/30",   glow: "shadow-red-500/10",    border: "border-red-500/20"   },
};

type Props = {
  verdict: VerdictState;
  productName: string;
};

export function VerdictCard({ verdict, productName }: Props) {
  const loadingVerb = useCyclingText(LOADING_VERBS.orchestrator, 2500);

  if (verdict.status === "loading" || verdict.status === "idle") {
    return (
      <div className="glass rounded-2xl p-5 sm:p-8 w-full">
        <p className="text-xs text-white/30 uppercase tracking-widest mb-4">synthesizing verdict</p>
        <div className="h-10 bg-white/[0.06] rounded-lg w-32 mb-4 animate-pulse" />
        <p className="text-white/30 text-sm italic transition-opacity duration-500">{loadingVerb}</p>
      </div>
    );
  }

  if (verdict.status === "error" || !verdict.data) {
    return (
      <div className="glass rounded-2xl p-5 sm:p-8 w-full">
        <p className="text-white/40">Unable to generate a verdict. Please try again.</p>
      </div>
    );
  }

  const { data } = verdict;
  const style = VERDICT_STYLES[data.verdict] ?? VERDICT_STYLES.Consider;

  return (
    <div className={`glass rounded-2xl p-5 sm:p-8 w-full shadow-xl ${style.glow} border ${style.border}`}>
      {productName && (
        <p className="text-white/40 text-sm mb-3">{productName}</p>
      )}
      <span
        className={`inline-block border rounded-full px-6 py-2 text-2xl font-bold mb-5 ${style.chip}`}
      >
        {data.verdict}
      </span>
      <p className="text-white/80 text-base leading-relaxed mb-4">{data.summary}</p>
      {data.notable_disagreements && (
        <div className="border-l-2 border-white/10 pl-4 mt-4">
          <p className="text-white/40 text-sm italic">{data.notable_disagreements}</p>
        </div>
      )}
    </div>
  );
}
