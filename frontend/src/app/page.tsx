"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { SearchInput } from "@/components/SearchInput";
import { clarifyReview, startReview } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [clarification, setClarification] = useState<{
    reviewId: string;
    question: string;
    candidates: string[];
  } | null>(null);
  const [clarifyLoading, setClarifyLoading] = useState(false);

  async function handleSearch(query: string) {
    setLoading(true);
    setError(null);
    setClarification(null);
    try {
      const res = await startReview(query);
      if (res.status === "running") {
        router.push(`/review/${res.review_id}`);
      } else if (res.status === "clarification_needed") {
        setClarification({
          reviewId: res.review_id,
          question: res.clarification_question ?? `Which "${query}" did you mean?`,
          candidates: res.candidates ?? [],
        });
        setLoading(false);
      }
    } catch {
      setError("Something went wrong. Is the backend running?");
      setLoading(false);
    }
  }

  async function handleClarify(choice: string) {
    if (!clarification) return;
    setClarifyLoading(true);
    try {
      await clarifyReview(clarification.reviewId, choice);
      router.push(`/review/${clarification.reviewId}`);
    } catch {
      setError("Something went wrong.");
      setClarifyLoading(false);
    }
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-xl flex flex-col items-center gap-6">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-white mb-2">review-me</h1>
          <p className="text-zinc-400 text-lg">Should I buy it?</p>
        </div>

        <SearchInput onSubmit={handleSearch} loading={loading} />

        {error && (
          <p className="text-red-400 text-sm">{error}</p>
        )}

        {clarification && (
          <div className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl p-6 space-y-4">
            <p className="text-zinc-300 text-sm">{clarification.question}</p>
            <div className="flex flex-col gap-2">
              {clarification.candidates.map((candidate) => (
                <button
                  key={candidate}
                  onClick={() => handleClarify(candidate)}
                  disabled={clarifyLoading}
                  className="text-left bg-zinc-800 hover:bg-zinc-700 text-white rounded-xl px-4 py-3 text-sm transition-colors disabled:opacity-50"
                >
                  {candidate}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
