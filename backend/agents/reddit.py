import json
from urllib.parse import quote_plus
import httpx
import anthropic
from firecrawl import FirecrawlApp
from db.database import get_cached, set_cached
from agents._loader import load_system_prompt

SOURCE = "reddit"

SYSTEM_PROMPT = load_system_prompt(SOURCE)


async def run(product: str, firecrawl: FirecrawlApp, claude: anthropic.AsyncAnthropic) -> dict:
    cached = await get_cached(product, SOURCE)
    if cached:
        return cached

    # Reddit blocks Firecrawl — use the Reddit JSON API directly
    url = f"https://www.reddit.com/search.json?q={quote_plus(product)}+review&sort=relevance&t=year&limit=10"
    posts_text = ""
    product_found = False

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                headers={"User-Agent": "review-me/1.0"},
                follow_redirects=True,
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
            posts = data["data"]["children"]
            product_found = len(posts) > 0
            posts_text = "\n\n".join(
                f"Title: {p['data']['title']}\nScore: {p['data']['score']}\n{p['data'].get('selftext', '')[:500]}"
                for p in posts[:8]
            )
    except Exception:
        posts_text = ""
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
                "content": f"Product: {product}\n\nReddit posts:\n{posts_text if posts_text else '(no posts found)'}",
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

    reddit_search_url = f"https://www.reddit.com/search/?q={quote_plus(product)}+review&sort=relevance&t=year"
    result = {
        "product_found": parsed.get("product_found", product_found),
        "source_url": reddit_search_url,
        "sentiment_summary": parsed.get("sentiment_summary", ""),
        "verdict": parsed.get("verdict", "Consider"),
        "confidence": parsed.get("confidence", "low"),
    }

    await set_cached(product, SOURCE, result)
    return result
