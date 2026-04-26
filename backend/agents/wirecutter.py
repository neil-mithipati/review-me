import asyncio
import logging
from urllib.parse import quote_plus
import anthropic
from firecrawl import FirecrawlApp
from db.database import get_cached, set_cached
from agents._loader import load_system_prompt

logger = logging.getLogger(__name__)

SOURCE = "wirecutter"

SYSTEM_PROMPT = load_system_prompt(SOURCE)

VERDICT_TOOL = {
    "name": "submit_verdict",
    "description": "Submit the Wirecutter review verdict for this product based on the search result snippets.",
    "input_schema": {
        "type": "object",
        "properties": {
            "product_found":            {"type": "boolean"},
            "source_url":               {"type": "string", "description": "Direct URL to the Wirecutter review or roundup page where this product appears"},
            "verdict_tier":             {"type": "string", "description": "One of: Our Pick, Also Great, Upgrade Pick, Budget Pick, No Longer Recommended, Not Listed"},
            "is_primary_recommendation":{"type": "boolean"},
            "blurb":                    {"type": "string", "description": "Brief excerpt describing the product's standing"},
            "verdict":                  {"type": "string", "enum": ["Buy", "Consider", "Skip"]},
            "confidence":               {"type": "string", "enum": ["high", "medium", "low"]},
        },
        "required": ["product_found", "verdict", "confidence"],
    },
}

_FALLBACK_URL = "https://www.nytimes.com/wirecutter/search/?q={}"


async def run(product: str, firecrawl: FirecrawlApp, claude: anthropic.AsyncAnthropic) -> dict:
    cached = await get_cached(product, SOURCE)
    if cached:
        return cached

    fallback_url = _FALLBACK_URL.format(quote_plus(product))
    snippets_text = ""
    top_review_url = fallback_url

    try:
        search_data = await asyncio.to_thread(
            firecrawl.search,
            f"site:nytimes.com/wirecutter {product}",
        )
        items = search_data.web or []

        rows = []
        for item in items[:6]:
            url = getattr(item, "url", "") or ""
            title = getattr(item, "title", "") or ""
            desc = getattr(item, "description", "") or ""
            rows.append(f"URL: {url}\nTitle: {title}\nSnippet: {desc}")
            if top_review_url == fallback_url and url:
                top_review_url = url

        snippets_text = "\n\n".join(rows)
    except Exception as e:
        logger.warning("Wirecutter search failed for '%s': %s", product, e)

    message = await claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        tools=[VERDICT_TOOL],
        tool_choice={"type": "any"},
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{
            "role": "user",
            "content": (
                f"Product: {product}\n\n"
                f"Wirecutter search result snippets:\n"
                f"{snippets_text if snippets_text else '(no results found)'}"
            ),
        }],
    )

    tool_block = next((b for b in message.content if b.type == "tool_use"), None)
    parsed = tool_block.input if tool_block else {
        "product_found": False,
        "verdict": "Consider",
        "confidence": "low",
    }

    result = {
        "product_found": parsed.get("product_found", False),
        "source_url": parsed.get("source_url") or top_review_url,
        "verdict_tier": parsed.get("verdict_tier", "Not Listed"),
        "is_primary_recommendation": parsed.get("is_primary_recommendation", False),
        "blurb": parsed.get("blurb", ""),
        "verdict": parsed.get("verdict", "Consider"),
        "confidence": parsed.get("confidence", "low"),
    }

    await set_cached(product, SOURCE, result)
    return result
