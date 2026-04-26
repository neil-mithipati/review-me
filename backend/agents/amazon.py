import logging
from urllib.parse import quote_plus
import anthropic
from firecrawl import FirecrawlApp
from db.database import get_cached, set_cached

logger = logging.getLogger(__name__)

SOURCE = "amazon"

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "product_found": {"type": "boolean"},
        "source_url": {"type": "string", "description": "Direct URL to the specific Amazon product listing page"},
        "star_rating": {"type": "number", "description": "Rating from 0 to 5"},
        "review_count": {"type": "integer"},
        "common_complaints": {"type": "array", "items": {"type": "string"}},
        "is_amazon_choice": {"type": "boolean"},
        "is_best_seller": {"type": "boolean"},
    },
    "required": ["product_found"],
}

_CONFIDENCE_UP = {"low": "medium", "medium": "high", "high": "high"}


def _apply_rules(raw: dict) -> tuple[str, str]:
    """Pure Python verdict mapping — mirrors the rules in amazon.md."""
    if not raw.get("product_found"):
        return "Consider", "low"

    rating = raw.get("star_rating")
    count = raw.get("review_count") or 0

    if rating is None:
        verdict, confidence = "Consider", "low"
    elif rating >= 4.5 and count >= 500:
        verdict, confidence = "Buy", "high"
    elif rating >= 4.0 and count >= 100:
        verdict, confidence = "Consider", "medium"
    elif rating >= 4.0:
        verdict, confidence = "Consider", "low"
    else:
        verdict, confidence = "Skip", "medium"

    # Badges raise confidence one level but never change the verdict tier
    if raw.get("is_amazon_choice") or raw.get("is_best_seller"):
        confidence = _CONFIDENCE_UP[confidence]

    return verdict, confidence


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
        logger.warning("Amazon Firecrawl failed for '%s': %s", product, e)
        raw = {"product_found": False, "error": str(e)}

    verdict, confidence = _apply_rules(raw)

    result = {
        "product_found": raw.get("product_found", False),
        "source_url": raw.get("source_url") or url,
        "star_rating": raw.get("star_rating"),
        "review_count": raw.get("review_count"),
        "common_complaints": raw.get("common_complaints", []),
        "is_amazon_choice": raw.get("is_amazon_choice", False),
        "is_best_seller": raw.get("is_best_seller", False),
        "verdict": verdict,
        "confidence": confidence,
    }

    await set_cached(product, SOURCE, result)
    return result
