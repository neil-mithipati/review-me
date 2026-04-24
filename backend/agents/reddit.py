import json
from urllib.parse import quote_plus
import anthropic
from firecrawl import FirecrawlApp
from db.database import get_cached, set_cached

SOURCE = "reddit"

SYSTEM_PROMPT = """You are a product review analyst specializing in Reddit community sentiment.
Analyze the Reddit search results and posts about the given product.

Return a JSON object with:
- product_found: boolean (true if relevant posts were found)
- sentiment_summary: 1-2 sentence summary of community opinion
- verdict: "Buy", "Consider", or "Skip" based on overall sentiment
- confidence: "high" (many posts, clear consensus), "medium" (moderate discussion), "low" (few posts or mixed)

Focus on recent, high-karma posts. Weight negative safety/quality issues heavily.
Respond with a JSON object only, no explanation."""


async def run(product: str, firecrawl: FirecrawlApp, claude: anthropic.AsyncAnthropic) -> dict:
    cached = await get_cached(product, SOURCE)
    if cached:
        return cached

    url = f"https://www.reddit.com/search/?q={quote_plus(product)}+review&sort=relevance&t=year"
    try:
        scrape_result = firecrawl.scrape_url(url, params={"formats": ["markdown"]})
        markdown = scrape_result.get("markdown", "") if isinstance(scrape_result, dict) else ""
        # Truncate to avoid excessive token usage
        markdown = markdown[:8000] if len(markdown) > 8000 else markdown
        product_found = bool(markdown and len(markdown) > 200)
    except Exception as e:
        markdown = ""
        product_found = False

    message = await claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
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
                "content": f"Product: {product}\n\nReddit search results:\n{markdown if markdown else '(no results found)'}",
            }
        ],
    )

    try:
        parsed = json.loads(message.content[0].text)
    except (json.JSONDecodeError, IndexError, KeyError):
        parsed = {
            "product_found": product_found,
            "sentiment_summary": "Unable to determine community sentiment.",
            "verdict": "Consider",
            "confidence": "low",
        }

    result = {
        "product_found": parsed.get("product_found", product_found),
        "sentiment_summary": parsed.get("sentiment_summary", ""),
        "verdict": parsed.get("verdict", "Consider"),
        "confidence": parsed.get("confidence", "low"),
    }

    await set_cached(product, SOURCE, result)
    return result
