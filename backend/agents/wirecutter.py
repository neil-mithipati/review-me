import json
from urllib.parse import quote_plus
import anthropic
from firecrawl import FirecrawlApp
from db.database import get_cached, set_cached

SOURCE = "wirecutter"

SYSTEM_PROMPT = """You are a product review analyst specializing in Wirecutter (NYT).
Given Wirecutter data for a product, map it to a verdict (Buy/Consider/Skip) and confidence (high/medium/low).

Mapping rules:
- "Our Pick" or "Also Great" → verdict: Buy, confidence: high
- "Upgrade Pick" or "Budget Pick" → verdict: Consider, confidence: medium
- "No Longer Recommended" → verdict: Skip, confidence: high
- "Not Listed" or product_found=false → verdict: Consider, confidence: low

Respond with a JSON object only, no explanation."""

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "product_found": {"type": "boolean"},
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
                "content": f"Product: {product}\nWirecutter data: {json.dumps(raw)}\n\nReturn JSON with keys: verdict, confidence.",
            }
        ],
    )

    try:
        parsed = json.loads(message.content[0].text)
    except (json.JSONDecodeError, IndexError, KeyError):
        parsed = {"verdict": "Consider", "confidence": "low"}

    result = {
        "product_found": raw.get("product_found", False),
        "verdict_tier": raw.get("verdict_tier", "Not Listed"),
        "is_primary_recommendation": raw.get("is_primary_recommendation", False),
        "blurb": raw.get("blurb", ""),
        "verdict": parsed.get("verdict", "Consider"),
        "confidence": parsed.get("confidence", "low"),
    }

    await set_cached(product, SOURCE, result)
    return result
