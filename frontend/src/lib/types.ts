export type Verdict = "Buy" | "Consider" | "Skip";
export type Confidence = "high" | "medium" | "low";
export type SourceName = "wirecutter" | "cnet" | "amazon" | "reddit";
export type SourceStatus = "idle" | "loading" | "complete" | "error";

export type WirecutterData = {
  product_found: boolean;
  source_url?: string;
  verdict_tier: string;
  is_primary_recommendation: boolean;
  blurb: string;
  verdict: Verdict;
  confidence: Confidence;
};

export type CnetData = {
  product_found: boolean;
  source_url?: string;
  overall_score: number | null;
  pros: string[];
  cons: string[];
  verdict: Verdict;
  confidence: Confidence;
};

export type AmazonData = {
  product_found: boolean;
  source_url?: string;
  star_rating: number | null;
  review_count: number | null;
  common_complaints: string[];
  is_amazon_choice: boolean;
  is_best_seller: boolean;
  verdict: Verdict;
  confidence: Confidence;
};

export type RedditData = {
  product_found: boolean;
  source_url?: string;
  sentiment_summary: string;
  verdict: Verdict;
  confidence: Confidence;
};

export type SourceData = WirecutterData | CnetData | AmazonData | RedditData;

export type SourceState = {
  status: SourceStatus;
  data?: SourceData;
  error?: string;
};

export type VerdictData = {
  verdict: Verdict;
  summary: string;
  notable_disagreements?: string;
  buy_link?: string;
  recommended_action: "buy" | "consider" | "skip";
};

export type VerdictState = {
  status: "idle" | "loading" | "complete" | "error";
  data?: VerdictData;
};

export type WishlistItem = {
  id: number;
  product_name: string;
  verdict: string;
  review_id: string;
  created_at: string;
};

export type StartReviewResponse = {
  review_id: string;
  status: "running" | "clarification_needed";
  candidates: string[] | null;
  clarification_question: string | null;
};

export type SSESourceUpdateEvent = {
  source: SourceName;
  status: "loading" | "complete" | "error";
  data?: SourceData;
  error?: string;
};

export type SSEVerdictEvent = VerdictData;
