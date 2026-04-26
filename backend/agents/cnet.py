import asyncio
import logging
from urllib.parse import quote_plus
import anthropic
from firecrawl import FirecrawlApp
from db.database import get_cached, set_cached
from agents._loader import load_system_prompt

logger = logging.getLogger(__name__)

SOURCE = "cnet"

SYSTEM_PROMPT = load_system_prompt(SOURCE)

VERDICT_TOOL = {
    "name": "submit_verdict",
    "description": "Submit the CNET review verdict for this product based on the search result snippets.",
    "input_schema": {
        "type": "object",
        "properties": {
            "product_found": {"type": "boolean"},
            "source_url":    {"type": "string", "description": "Direct URL to the specific CNET review page"},
            "overall_score": {"type": "number", "description": "Score from 0 to 10, if mentioned in the snippets"},
            "pros":          {"type": "array", "items": {"type": "string"}},
            "cons":          {"type": "array", "items": {"type": "string"}},
            "verdict":       {"type": "string", "enum": ["Buy", "Consider", "Skip"]},
            "confidence":    {"type": "string", "enum": ["high", "medium", "low"]},
        },
        "required": ["product_found", "verdict", "confidence"],
    },
}

_FALLBACK_URL = "https://www.cnet.com/search/?query={}"


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
            f"site:cnet.com {product} review",
        )
        items = search_data.web or []

        rows = []
        for item in items[:6]:
            url = getattr(item, "url", "") or ""
            title = getattr(item, "title", "") or ""
            desc = getattr(item, "description", "") or ""
            rows.append(f"URL: {url}\nTitle: {title}\nSnippet: {desc}")
            # Use the first URL that looks like a dedicated review page
            if top_review_url == fallback_url and "/review" in url and "best-" not in url:
                top_review_url = url

        # Fall back to the first result if no dedicated review page found
        if top_review_url == fallback_url and items:
            top_review_url = getattr(items[0], "url", fallback_url) or fallback_url

        snippets_text = "\n\n".join(rows)
    except Exception as e:
        logger.warning("CNET search failed for '%s': %s", product, e)

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
                f"CNET search result snippets:\n"
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
        "overall_score": parsed.get("overall_score"),
        "pros": parsed.get("pros", []),
        "cons": parsed.get("cons", []),
        "verdict": parsed.get("verdict", "Consider"),
        "confidence": parsed.get("confidence", "low"),
    }

    await set_cached(product, SOURCE, result)
    return result
