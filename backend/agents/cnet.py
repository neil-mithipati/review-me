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

SOURCE = "cnet"

SYSTEM_PROMPT = load_system_prompt(SOURCE)

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "product_found": {"type": "boolean"},
        "source_url": {"type": "string", "description": "Direct URL to the specific CNET review page for this product"},
        "overall_score": {"type": "number", "description": "Score from 0 to 10"},
        "pros": {"type": "array", "items": {"type": "string"}},
        "cons": {"type": "array", "items": {"type": "string"}},
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

    url = f"https://www.cnet.com/search/?query={quote_plus(product)}"
    try:
        extract_result = firecrawl.extract(
            urls=[url],
            prompt=f"Find the CNET review for '{product}'. Extract the overall score (0-10), pros, and cons.",
            schema=EXTRACT_SCHEMA,
            allow_external_links=True,
            enable_web_search=True,
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
                "content": f"Product: {product}\nCNET data: {json.dumps(raw)}",
            }
        ],
    )

    raw_text = message.content[0].text
    try:
        parsed = _parse_json(raw_text)
    except (json.JSONDecodeError, IndexError, KeyError):
        logger.warning("CNET agent JSON parse failed for '%s'. Raw: %s", product, raw_text)
        parsed = {"verdict": "Consider", "confidence": "low"}

    result = {
        "product_found": raw.get("product_found", False),
        "source_url": raw.get("source_url") or url,
        "overall_score": raw.get("overall_score"),
        "pros": raw.get("pros", []),
        "cons": raw.get("cons", []),
        "verdict": parsed.get("verdict", "Consider"),
        "confidence": parsed.get("confidence", "low"),
    }

    await set_cached(product, SOURCE, result)
    return result
