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

SOURCE = "wirecutter"

SYSTEM_PROMPT = load_system_prompt(SOURCE)

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "product_found": {"type": "boolean"},
        "source_url": {"type": "string", "description": "Direct URL to the specific Wirecutter review page for this product"},
        "verdict_tier": {
            "type": "string",
            "description": "One of: Our Pick, Also Great, Upgrade Pick, Budget Pick, No Longer Recommended, Not Listed",
        },
        "is_primary_recommendation": {"type": "boolean"},
        "blurb": {"type": "string", "description": "Brief review excerpt"},
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

    url = f"https://www.wirecutter.com/search/?q={quote_plus(product)}"
    try:
        extract_result = firecrawl.extract(
            urls=[url],
            prompt=f"Find the Wirecutter review for '{product}'. Extract the verdict tier (Our Pick, Also Great, Upgrade Pick, Budget Pick, No Longer Recommended, or Not Listed), whether it is the primary recommendation, and any review blurb.",
            schema=EXTRACT_SCHEMA,
            allow_external_links=True,
            enable_web_search=True,
        )
        raw = _parse_data(extract_result.data if hasattr(extract_result, "data") else {})
    except Exception as e:
        raw = {"product_found": False, "error": str(e)}

    message = await claude.messages.create(
        model="claude-haiku-4-5-20251001",
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
                "content": f"Product: {product}\nWirecutter data: {json.dumps(raw)}",
            }
        ],
    )

    raw_text = message.content[0].text
    try:
        parsed = _parse_json(raw_text)
    except (json.JSONDecodeError, IndexError, KeyError):
        logger.warning("Wirecutter agent JSON parse failed for '%s'. Raw: %s", product, raw_text)
        parsed = {"verdict": "Consider", "confidence": "low"}

    result = {
        "product_found": raw.get("product_found", False),
        "source_url": raw.get("source_url") or url,
        "verdict_tier": raw.get("verdict_tier", "Not Listed"),
        "is_primary_recommendation": raw.get("is_primary_recommendation", False),
        "blurb": raw.get("blurb", ""),
        "verdict": parsed.get("verdict", "Consider"),
        "confidence": parsed.get("confidence", "low"),
    }

    await set_cached(product, SOURCE, result)
    return result
