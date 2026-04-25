import json
from urllib.parse import quote_plus
import anthropic
from firecrawl import FirecrawlApp
from db.database import get_cached, set_cached

SOURCE = "cnet"

SYSTEM_PROMPT = """You are a product review analyst specializing in CNET reviews.
Given CNET data for a product, map its score to a verdict (Buy/Consider/Skip) and confidence (high/medium/low).

Score bands:
- 8.0+ → verdict: Buy, confidence: high
- 7.0-7.9 → verdict: Consider, confidence: high
- 5.0-6.9 → verdict: Consider, confidence: low
- below 5.0 → verdict: Skip, confidence: high
- no score / product not found → verdict: Consider, confidence: low

Respond with a JSON object only, no explanation."""

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "product_found": {"type": "boolean"},
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
                "content": f"Product: {product}\nCNET data: {json.dumps(raw)}\n\nReturn JSON with keys: verdict, confidence.",
            }
        ],
    )

    try:
        parsed = json.loads(message.content[0].text)
    except (json.JSONDecodeError, IndexError, KeyError):
        parsed = {"verdict": "Consider", "confidence": "low"}

    result = {
        "product_found": raw.get("product_found", False),
        "overall_score": raw.get("overall_score"),
        "pros": raw.get("pros", []),
        "cons": raw.get("cons", []),
        "verdict": parsed.get("verdict", "Consider"),
        "confidence": parsed.get("confidence", "low"),
    }

    await set_cached(product, SOURCE, result)
    return result
