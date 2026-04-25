"use client";

import { useCyclingText } from "@/hooks/useCyclingText";
import { LOADING_VERBS } from "@/lib/loadingVerbs";
import type {
  AmazonData,
  CnetData,
  RedditData,
  SourceName,
  SourceState,
  WirecutterData,
} from "@/lib/types";

const SOURCE_META: Record<SourceName, { label: string; url: string }> = {
  wirecutter: { label: "Wirecutter", url: "https://www.wirecutter.com" },
  cnet:       { label: "CNET",       url: "https://www.cnet.com" },
  amazon:     { label: "Amazon",     url: "https://www.amazon.com" },
  reddit:     { label: "Reddit",     url: "https://www.reddit.com" },
};

const VERDICT_CHIP: Record<string, string> = {
  Buy:     "bg-green-500/20 text-green-400",
  Consider:"bg-amber-500/20 text-amber-400",
  Skip:    "bg-red-500/20 text-red-400",
};

function StarRating({ rating }: { rating: number }) {
  const full = Math.floor(rating);
  const half = rating - full >= 0.5;
  return (
    <span className="text-amber-400 text-sm">
      {"★".repeat(full)}
      {half ? "½" : ""}
      {"☆".repeat(5 - full - (half ? 1 : 0))}
      <span className="text-white/40 ml-1">{rating.toFixed(1)}</span>
    </span>
  );
}

function WirecutterContent({ data }: { data: WirecutterData }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="bg-white/[0.08] text-white/70 text-xs px-2 py-0.5 rounded">
          {data.verdict_tier || "Not Listed"}
        </span>
        {data.is_primary_recommendation && (
          <span className="text-green-400 text-xs">✓ Top Pick</span>
        )}
      </div>
      {data.blurb && (
        <p className="text-white/40 text-xs leading-relaxed line-clamp-3">{data.blurb}</p>
      )}
    </div>
  );
}

function CnetContent({ data }: { data: CnetData }) {
  return (
    <div className="space-y-2">
      {data.overall_score != null && (
        <p className="text-white text-lg font-bold">
          {data.overall_score.toFixed(1)}{" "}
          <span className="text-zinc-500 text-sm font-normal">/ 10</span>
        </p>
      )}
      {data.pros.length > 0 && (
        <ul className="space-y-0.5">
          {data.pros.slice(0, 2).map((p, i) => (
            <li key={i} className="text-green-400 text-xs">+ {p}</li>
          ))}
        </ul>
      )}
      {data.cons.length > 0 && (
        <ul className="space-y-0.5">
          {data.cons.slice(0, 2).map((c, i) => (
            <li key={i} className="text-red-400 text-xs">− {c}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function AmazonContent({ data }: { data: AmazonData }) {
  return (
    <div className="space-y-2">
      {data.star_rating != null && <StarRating rating={data.star_rating} />}
      {data.review_count != null && (
        <p className="text-white/40 text-xs">{data.review_count.toLocaleString()} reviews</p>
      )}
      <div className="flex gap-2">
        {data.is_amazon_choice && (
          <span className="bg-amber-500/20 text-amber-400 text-xs px-2 py-0.5 rounded">
            Amazon&apos;s Choice
          </span>
        )}
        {data.is_best_seller && (
          <span className="bg-orange-500/20 text-orange-400 text-xs px-2 py-0.5 rounded">
            Best Seller
          </span>
        )}
      </div>
      {data.common_complaints.length > 0 && (
        <p className="text-white/30 text-xs line-clamp-2">{data.common_complaints[0]}</p>
      )}
    </div>
  );
}

function RedditContent({ data }: { data: RedditData }) {
  return (
    <p className="text-white/40 text-xs leading-relaxed line-clamp-4">
      {data.sentiment_summary || "No community data available."}
    </p>
  );
}

type Props = {
  source: SourceName;
  state: SourceState;
  productName?: string;
};

export function SourceCard({ source, state, productName }: Props) {
  const { label, url } = SOURCE_META[source];
  const verb = useCyclingText(LOADING_VERBS[source] ?? [], 2000);

  const sourceUrl = (state.status === "complete" && state.data && "source_url" in state.data && state.data.source_url)
    ? state.data.source_url
    : productName
      ? `${url}/search?q=${encodeURIComponent(productName)}`
      : url;

  return (
    <a
      href={sourceUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="group glass rounded-xl p-4 sm:p-5 flex flex-col gap-2 sm:gap-3 min-h-[160px] sm:min-h-[180px] transition-all duration-200 ease-out hover:bg-white/[0.08] hover:border-white/[0.18] hover:-translate-y-0.5 hover:shadow-xl hover:shadow-black/40 active:bg-white/[0.1] cursor-pointer"
    >
      <div className="flex items-center justify-between">
        <span className="text-white/80 font-semibold text-sm transition-colors duration-200 group-hover:text-white">
          {label}
        </span>
        {state.status === "complete" && state.data && (
          <span
            className={`text-xs px-2 py-0.5 rounded-full font-medium ${
              VERDICT_CHIP[state.data.verdict] ?? VERDICT_CHIP.Consider
            }`}
          >
            {state.data.verdict}
          </span>
        )}
      </div>

      {(state.status === "loading" || state.status === "idle") && (
        <div className="flex-1 flex flex-col gap-2 justify-center">
          <div className="h-2.5 bg-white/[0.06] rounded animate-pulse w-3/4" />
          <div className="h-2.5 bg-white/[0.06] rounded animate-pulse w-1/2" />
          <p className="text-white/25 text-xs italic mt-1 transition-opacity duration-500">{verb}</p>
        </div>
      )}

      {state.status === "error" && (
        <p className="text-white/25 text-xs">Unable to retrieve</p>
      )}

      {state.status === "complete" && state.data && (
        <div className="flex-1">
          {source === "wirecutter" && (
            <WirecutterContent data={state.data as WirecutterData} />
          )}
          {source === "cnet" && <CnetContent data={state.data as CnetData} />}
          {source === "amazon" && <AmazonContent data={state.data as AmazonData} />}
          {source === "reddit" && <RedditContent data={state.data as RedditData} />}
        </div>
      )}
    </a>
  );
}
