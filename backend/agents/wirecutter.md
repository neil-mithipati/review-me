---
name: wirecutter
description: Source agent that retrieves and interprets Wirecutter (NYT) review data for a product. Extracts verdict tier, primary recommendation status, and review blurb via Firecrawl, then maps to a Buy/Consider/Skip verdict with confidence. Invoke when you need the Wirecutter perspective on a product.
---

## Scraping strategy

1. **Search** — `firecrawl.search('site:nytimes.com/wirecutter "{product}"')` with the product name quoted for precision. Prefer roundup "best-X" URLs since Wirecutter covers most products in category roundups rather than standalone reviews.
2. **Extract** — `firecrawl.extract()` on the roundup/review URL with a structured schema to pull `verdict_tier`, `is_primary_recommendation`, and `blurb` for the specific product.

## Tier-to-verdict mapping (applied in Python)

| verdict_tier              | verdict  | confidence |
|--------------------------|----------|------------|
| Our Pick                 | Buy      | high       |
| Also Great               | Buy      | high       |
| Upgrade Pick             | Consider | medium     |
| Budget Pick              | Consider | medium     |
| No Longer Recommended    | Skip     | high       |
| Not Listed               | Consider | low        |

If no page is found, returns `product_found: false` / `Consider` / `low`.
