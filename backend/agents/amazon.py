import json
import logging
import re
from urllib.parse import quote_plus
import anthropic
from firecrawl import FirecrawlApp
from db.database import get_cached, set_cached
from agents._loader import load_system_prompt

logger = logging.getLogger(__name__)


def _parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text.strip())

SOURCE = "amazon"

SYSTEM_PROMPT = load_system_prompt(SOURCE)

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
                "content": f"Product: {product}\nAmazon data: {json.dumps(raw)}",
            }
        ],
    )

    raw_text = message.content[0].text
    try:
        parsed = _parse_json(raw_text)
    except (json.JSONDecodeError, IndexError, KeyError):
        logger.warning("Amazon agent JSON parse failed for '%s'. Raw: %s", product, raw_text)
        parsed = {"verdict": "Consider", "confidence": "low"}

    result = {
        "product_found": raw.get("product_found", False),
        "source_url": raw.get("source_url") or url,
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
