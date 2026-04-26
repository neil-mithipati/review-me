import asyncio
import json
import logging
from urllib.parse import quote_plus
import anthropic
from firecrawl import FirecrawlApp
from db.database import get_cached, set_cached
from agents._loader import load_system_prompt

logger = logging.getLogger(__name__)

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

VERDICT_TOOL = {
    "name": "submit_verdict",
    "description": "Submit the final Buy/Consider/Skip verdict for this product based on the CNET data.",
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict":    {"type": "string", "enum": ["Buy", "Consider", "Skip"]},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        },
        "required": ["verdict", "confidence"],
    },
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
        extract_result = await asyncio.to_thread(
            firecrawl.extract,
            urls=[url],
            prompt=f"Find the CNET review for '{product}'. Extract the overall score (0-10), pros, and cons.",
            schema=EXTRACT_SCHEMA,
            allow_external_links=True,
            enable_web_search=True,
        )
        raw = _parse_data(extract_result.data if hasattr(extract_result, "data") else {})
    except Exception as e:
        logger.warning("CNET Firecrawl failed for '%s': %s", product, e)
        raw = {"product_found": False, "error": str(e)}

    message = await claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        tools=[VERDICT_TOOL],
        tool_choice={"type": "any"},
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": f"Product: {product}\nCNET data: {json.dumps(raw)}"}],
    )

    tool_block = next((b for b in message.content if b.type == "tool_use"), None)
    parsed = tool_block.input if tool_block else {"verdict": "Consider", "confidence": "low"}

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
