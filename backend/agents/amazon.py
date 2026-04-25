import json
from urllib.parse import quote_plus
import anthropic
from firecrawl import FirecrawlApp
from db.database import get_cached, set_cached

SOURCE = "amazon"

SYSTEM_PROMPT = """You are a product review analyst specializing in Amazon customer data.
Given Amazon data for a product, map it to a verdict (Buy/Consider/Skip) and confidence (high/medium/low).

Mapping rules:
- star_rating >= 4.5 AND review_count >= 500 → verdict: Buy, confidence: high
- star_rating >= 4.0 AND review_count >= 100 → verdict: Consider, confidence: medium
- star_rating >= 4.0 but review_count < 100 → verdict: Consider, confidence: low
- star_rating < 4.0 → verdict: Skip, confidence: medium
- product_found=false → verdict: Consider, confidence: low

Respond with a JSON object only, no explanation."""

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "product_found": {"type": "boolean"},
        "star_rating": {"type": "number", "description": "Rating from 0 to 5"},
        "review_count": {"type": "integer"},
        "common_complaints": {"type": "array", "items": {"type": "string"}},
        "is_amazon_choice": {"type": "boolean"},
        "is_best_seller": {"type": "boolean"},
    },
    "required": ["product_found"],
}


def _parse_data(raw) -> dict:
    if isinstance(raw, list):
        return raw[0] if raw else {}
    return raw if isinstance(raw, dict) else {}


async def run(product: str, firecrawl: FirecrawlApp, claude: anthropic.AsyncAnthropic) -> dict:
    cached = await get_cached(product, SOURCE)
    if cached:
        return cached

    url = f"https://www.amazon.com/s?k={quote_plus(product)}"
    try:
        extract_result = firecrawl.extract(
            urls=[url],
            prompt=f"Find the top Amazon listing for '{product}'. Extract the star rating, number of reviews, common complaints from reviews, and whether it has Amazon's Choice or Best Seller badge.",
            schema=EXTRACT_SCHEMA,
            allow_external_links=True,
        )
        raw = _parse_data(extract_result.data if hasattr(extract_result, "data") else {})
    except Exception as e:
        raw = {"product_found": False, "error": str(e)}

    message = await claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": f"Product: {product}\nAmazon data: {json.dumps(raw)}\n\nReturn JSON with keys: verdict, confidence.",
            }
        ],
    )

    try:
        parsed = json.loads(message.content[0].text)
    except (json.JSONDecodeError, IndexError, KeyError):
        parsed = {"verdict": "Consider", "confidence": "low"}

    result = {
        "product_found": raw.get("product_found", False),
        "star_rating": raw.get("star_rating"),
        "review_count": raw.get("review_count"),
        "common_complaints": raw.get("common_complaints", []),
        "is_amazon_choice": raw.get("is_amazon_choice", False),
        "is_best_seller": raw.get("is_best_seller", False),
        "verdict": parsed.get("verdict", "Consider"),
        "confidence": parsed.get("confidence", "low"),
    }

    await set_cached(product, SOURCE, result)
    return result
