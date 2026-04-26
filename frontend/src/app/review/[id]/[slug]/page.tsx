"use client";

import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ActionButtons } from "@/components/ActionButtons";
import { SourceCard } from "@/components/SourceCard";
import { VerdictCard } from "@/components/VerdictCard";
import { getReviewById, streamReview } from "@/lib/api";
import type { SourceName, SourceState, VerdictState } from "@/lib/types";

const SOURCES: SourceName[] = ["wirecutter", "cnet", "amazon", "reddit"];

const initialSources = (): Record<SourceName, SourceState> => ({
  wirecutter: { status: "loading" },
  cnet: { status: "loading" },
  amazon: { status: "loading" },
  reddit: { status: "loading" },
});

export default function ReviewPage() {
  const { id: shortId } = useParams<{ id: string; slug: string }>();

  const [productName, setProductName] = useState("");
  const [sources, setSources] = useState<Record<SourceName, SourceState>>(initialSources());
  const [verdict, setVerdict] = useState<VerdictState>({ status: "loading" });
  const [notFound, setNotFound] = useState(false);
  const cleanupRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    let cancelled = false;

    getReviewById(shortId).then((result) => {
      if (cancelled) return;

      if (!result) {
        setNotFound(true);
        return;
      }

      setProductName(result.product_name);

      if (result.status === "complete") {
        // Hydrate from stored results (shared link)
        const hydratedSources = {} as Record<SourceName, SourceState>;
        for (const source of SOURCES) {
          const data = result.source_data[source];
          hydratedSources[source] = data
            ? { status: "complete", data }
            : { status: "error", error: "No data available" };
        }
        setSources(hydratedSources);
        setVerdict({ status: "complete", data: result.verdict_data });
      } else {
        // Review still in progress — stream live results
        const cleanup = streamReview(
          result.review_id,
          (event) => {
            setSources((prev) => ({
              ...prev,
              [event.source]: { status: event.status, data: event.data, error: event.error },
            }));
          },
          (event) => {
            setVerdict({ status: "complete", data: event });
          },
          () => {},
          () => {
            setVerdict((v) => (v.status === "loading" ? { status: "error" } : v));
          }
        );
        cleanupRef.current = cleanup;
      }
    });

    return () => {
      cancelled = true;
      cleanupRef.current?.();
    };
  }, [shortId]);

  if (notFound) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="text-center space-y-3">
          <p className="text-white/50 text-lg">Review not found.</p>
          <a href="/" className="text-cyan-400 text-sm hover:text-cyan-300 transition-colors">
            Search for a product →
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen pt-[calc(5rem+env(safe-area-inset-top,0px))] pb-8 px-3 sm:px-4">
      <div className="max-w-4xl mx-auto flex flex-col gap-4 sm:gap-6">
        <VerdictCard verdict={verdict} productName={productName} />

        <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-4">
          {SOURCES.map((source) => (
            <SourceCard key={source} source={source} state={sources[source]} productName={productName} />
          ))}
        </div>

        {verdict.status === "complete" && verdict.data && (
          <ActionButtons
            verdictData={verdict.data}
            productName={productName}
            reviewId={shortId}
          />
        )}
      </div>
    </div>
  );
}
