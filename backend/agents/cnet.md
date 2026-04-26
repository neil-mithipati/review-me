---
name: cnet
description: Source agent that retrieves and interprets CNET review data for a product. Extracts numeric score, pros, and cons via Firecrawl, then maps the score band to a Buy/Consider/Skip verdict with confidence. Invoke when you need the CNET critic perspective on a product.
---

## Scraping strategy

1. **Search** — `firecrawl.search("site:cnet.com {product} review")` to locate the dedicated review page. Prefer URLs containing `/review` over roundup "best-X" articles.
2. **Extract** — `firecrawl.extract()` on the review URL with a structured schema to pull `overall_score`, `pros`, and `cons` from the actual page.

## Score-to-verdict mapping (applied in Python)

| overall_score | verdict  | confidence |
|--------------|----------|------------|
| 8.0 – 10.0   | Buy      | high       |
| 7.0 – 7.9    | Consider | high       |
| 5.0 – 6.9    | Consider | low        |
| below 5.0    | Skip     | high       |
| null         | Consider | low        |

If no review page is found, returns `product_found: false` / `Consider` / `low`.
