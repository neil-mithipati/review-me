import asyncio
import logging
from urllib.parse import quote_plus
import anthropic
from firecrawl import FirecrawlApp
from db.database import get_cached, set_cached

logger = logging.getLogger(__name__)

SOURCE = "cnet"

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "product_found": {"type": "boolean"},
        "overall_score": {"type": "number", "description": "Numeric score from 0 to 10"},
        "pros":          {"type": "array", "items": {"type": "string"}},
        "cons":          {"type": "array", "items": {"type": "string"}},
    },
    "required": ["product_found"],
}

_FALLBACK_URL = "https://www.cnet.com/search/?query={}"


def _apply_rules(raw: dict) -> tuple[str, str]:
    if not raw.get("product_found"):
        return "Consider", "low"
    score = raw.get("overall_score")
    if score is None:
        return "Consider", "low"
    if score >= 8.0:
        return "Buy", "high"
    if score >= 7.0:
        return "Consider", "high"
    if score >= 5.0:
        return "Consider", "low"
    return "Skip", "high"


def _parse_data(raw) -> dict:
    if isinstance(raw, list):
        return raw[0] if raw else {}
    return raw if isinstance(raw, dict) else {}


async def run(product: str, firecrawl: FirecrawlApp, claude: anthropic.AsyncAnthropic) -> dict:
    cached = await get_cached(product, SOURCE)
    if cached:
        return cached

    fallback_url = _FALLBACK_URL.format(quote_plus(product))
    top_review_url = fallback_url

    # Step 1: Find the dedicated review page URL via search
    try:
        search_data = await asyncio.to_thread(
            firecrawl.search,
            f"site:cnet.com {product} review",
        )
        items = search_data.web or []

        for item in items[:6]:
            url = getattr(item, "url", "") or ""
            # Prefer dedicated /review/ pages; skip "best-X" roundups
            if top_review_url == fallback_url and "/review" in url and "best-" not in url:
                top_review_url = url

        if top_review_url == fallback_url and items:
            top_review_url = getattr(items[0], "url", fallback_url) or fallback_url
    except Exception as e:
        logger.warning("CNET search failed for '%s': %s", product, e)

    # Step 2: Extract structured review data from the actual page
    raw = {}
    if top_review_url != fallback_url:
        try:
            extract_result = await asyncio.to_thread(
                firecrawl.extract,
                urls=[top_review_url],
                prompt=(
                    f"Extract the CNET review for '{product}': "
                    "the numeric overall score (0–10), list of pros, and list of cons."
                ),
                schema=EXTRACT_SCHEMA,
            )
            raw = _parse_data(extract_result.data if hasattr(extract_result, "data") else {})
        except Exception as e:
            logger.warning("CNET extract failed for '%s': %s", product, e)

    if not raw:
        raw = {"product_found": top_review_url != fallback_url}

    verdict, confidence = _apply_rules(raw)

    result = {
        "product_found": raw.get("product_found", False),
        "source_url": top_review_url,
        "overall_score": raw.get("overall_score"),
        "pros": raw.get("pros", []),
        "cons": raw.get("cons", []),
        "verdict": verdict,
        "confidence": confidence,
    }

    await set_cached(product, SOURCE, result)
    return result
