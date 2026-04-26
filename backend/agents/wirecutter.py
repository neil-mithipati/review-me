import asyncio
import logging
from urllib.parse import quote_plus
import anthropic
from firecrawl import FirecrawlApp
from db.database import get_cached, set_cached

logger = logging.getLogger(__name__)

SOURCE = "wirecutter"

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "product_found": {"type": "boolean"},
        "verdict_tier": {
            "type": "string",
            "description": (
                "One of: Our Pick, Also Great, Upgrade Pick, Budget Pick, "
                "No Longer Recommended, Not Listed"
            ),
        },
        "is_primary_recommendation": {"type": "boolean"},
        "blurb": {"type": "string", "description": "Brief excerpt about the product's standing"},
    },
    "required": ["product_found"],
}

_TIER_MAP = {
    "Our Pick":              ("Buy",     "high"),
    "Also Great":            ("Buy",     "high"),
    "Upgrade Pick":          ("Consider","medium"),
    "Budget Pick":           ("Consider","medium"),
    "No Longer Recommended": ("Skip",    "high"),
    "Not Listed":            ("Consider","low"),
}

_FALLBACK_URL = "https://www.nytimes.com/wirecutter/search/?q={}"


def _apply_rules(raw: dict) -> tuple[str, str]:
    if not raw.get("product_found"):
        return "Consider", "low"
    tier = raw.get("verdict_tier", "Not Listed")
    return _TIER_MAP.get(tier, ("Consider", "low"))


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

    # Step 1: Find the most relevant Wirecutter roundup or review page
    try:
        search_data = await asyncio.to_thread(
            firecrawl.search,
            # Quote the product name for a more precise match
            f'site:nytimes.com/wirecutter "{product}"',
        )
        items = search_data.web or []

        for item in items[:6]:
            url = getattr(item, "url", "") or ""
            # Wirecutter covers most products inside "best-X" roundup articles
            if top_review_url == fallback_url and ("best-" in url or "/reviews/" in url):
                top_review_url = url

        if top_review_url == fallback_url and items:
            top_review_url = getattr(items[0], "url", fallback_url) or fallback_url
    except Exception as e:
        logger.warning("Wirecutter search failed for '%s': %s", product, e)

    # Step 2: Extract structured verdict data from the actual page
    raw = {}
    if top_review_url != fallback_url:
        try:
            extract_result = await asyncio.to_thread(
                firecrawl.extract,
                urls=[top_review_url],
                prompt=(
                    f"Find '{product}' on this Wirecutter page. "
                    "Extract its verdict tier (Our Pick, Also Great, Upgrade Pick, Budget Pick, "
                    "No Longer Recommended, or Not Listed), whether it is the primary "
                    "recommendation on the page, and a short blurb describing its standing."
                ),
                schema=EXTRACT_SCHEMA,
            )
            raw = _parse_data(extract_result.data if hasattr(extract_result, "data") else {})
        except Exception as e:
            logger.warning("Wirecutter extract failed for '%s': %s", product, e)

    if not raw:
        raw = {"product_found": top_review_url != fallback_url}

    verdict, confidence = _apply_rules(raw)

    result = {
        "product_found": raw.get("product_found", False),
        "source_url": top_review_url,
        "verdict_tier": raw.get("verdict_tier", "Not Listed"),
        "is_primary_recommendation": raw.get("is_primary_recommendation", False),
        "blurb": raw.get("blurb", ""),
        "verdict": verdict,
        "confidence": confidence,
    }

    await set_cached(product, SOURCE, result)
    return result
