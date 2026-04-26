"use client";

import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ActionButtons } from "@/components/ActionButtons";
import { SourceCard } from "@/components/SourceCard";
import { VerdictCard } from "@/components/VerdictCard";
import { streamReview } from "@/lib/api";
import type { SourceName, SourceState, VerdictState } from "@/lib/types";

const SOURCES: SourceName[] = ["wirecutter", "cnet", "amazon", "reddit"];

const initialSources = (): Record<SourceName, SourceState> => ({
  wirecutter: { status: "loading" },
  cnet: { status: "loading" },
  amazon: { status: "loading" },
  reddit: { status: "loading" },
});

export default function ReviewPage() {
  const params = useParams();
  const reviewId = params.id as string;

  const [productName, setProductName] = useState("");
  const [sources, setSources] = useState<Record<SourceName, SourceState>>(initialSources());
  const [verdict, setVerdict] = useState<VerdictState>({ status: "loading" });
  const cleanupRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    const cleanup = streamReview(
      reviewId,
      (event) => {
        if (!productName && event.data?.product_found != null) {
          // product name comes from search params if available
        }
        setSources((prev) => ({
          ...prev,
          [event.source]: {
            status: event.status,
            data: event.data,
            error: event.error,
          },
        }));
      },
      (event) => {
        setVerdict({ status: "complete", data: event });
      },
      () => {
        // stream done
      },
      () => {
        setVerdict((v) =>
          v.status === "loading" ? { status: "error" } : v
        );
      }
    );
    cleanupRef.current = cleanup;
    return () => cleanup();
  }, [reviewId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Extract product name from URL search params if provided
  useEffect(() => {
    const url = new URL(window.location.href);
    const name = url.searchParams.get("product");
    if (name) setProductName(decodeURIComponent(name));
  }, []);

  return (
    <div className="min-h-screen pt-[calc(3.25rem+env(safe-area-inset-top,0px))] py-5 sm:py-8 px-3 sm:px-4">
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
            reviewId={reviewId}
          />
        )}
      </div>
    </div>
  );
}
