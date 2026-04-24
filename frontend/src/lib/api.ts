import type {
  SSESourceUpdateEvent,
  SSEVerdictEvent,
  StartReviewResponse,
  WishlistItem,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export async function startReview(query: string): Promise<StartReviewResponse> {
  const res = await fetch(`${BASE_URL}/api/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) throw new Error(`Failed to start review: ${res.statusText}`);
  return res.json();
}

export function streamReview(
  reviewId: string,
  onSourceUpdate: (event: SSESourceUpdateEvent) => void,
  onVerdict: (event: SSEVerdictEvent) => void,
  onDone: () => void,
  onError: (error: string) => void
): () => void {
  const es = new EventSource(`${BASE_URL}/api/review/${reviewId}/stream`);

  es.addEventListener("source_update", (e: MessageEvent) => {
    try {
      onSourceUpdate(JSON.parse(e.data));
    } catch {
      // ignore malformed events
    }
  });

  es.addEventListener("verdict", (e: MessageEvent) => {
    try {
      onVerdict(JSON.parse(e.data));
    } catch {
      // ignore malformed events
    }
  });

  es.addEventListener("done", () => {
    onDone();
    es.close();
  });

  es.addEventListener("error", (e: Event) => {
    const msg = e instanceof MessageEvent ? e.data : "Stream error";
    onError(msg);
    es.close();
  });

  es.onerror = () => {
    if (es.readyState === EventSource.CLOSED) {
      onDone();
    }
  };

  return () => es.close();
}

export async function clarifyReview(
  reviewId: string,
  choice: string
): Promise<StartReviewResponse> {
  const res = await fetch(`${BASE_URL}/api/review/${reviewId}/clarify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ choice }),
  });
  if (!res.ok) throw new Error(`Failed to clarify: ${res.statusText}`);
  return res.json();
}

export async function getWishlist(): Promise<WishlistItem[]> {
  const res = await fetch(`${BASE_URL}/api/wishlist`);
  if (!res.ok) throw new Error("Failed to fetch wishlist");
  const data = await res.json();
  return data.items;
}

export async function addToWishlist(
  productName: string,
  verdict: string,
  reviewId: string
): Promise<WishlistItem> {
  const res = await fetch(`${BASE_URL}/api/wishlist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ product_name: productName, verdict, review_id: reviewId }),
  });
  if (!res.ok) throw new Error("Failed to add to wishlist");
  return res.json();
}

export async function removeFromWishlist(id: number): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/wishlist/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to remove from wishlist");
}
