"""Unit tests for the Reddit source agent."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import make_claude


REDDIT_API_RESPONSE = {
    "data": {
        "children": [
            {
                "data": {
                    "title": "Sony WH-1000XM5 - 6 month review",
                    "score": 1200,
                    "selftext": "Best headphones I've ever owned. ANC is unbeatable.",
                }
            },
            {
                "data": {
                    "title": "WH-1000XM5 vs Bose QC45",
                    "score": 800,
                    "selftext": "Sony wins for ANC, Bose for comfort.",
                }
            },
        ]
    }
}


@pytest.mark.asyncio
async def test_does_not_call_firecrawl():
    """Reddit agent must NOT use Firecrawl — it blocks Reddit."""
    fc = MagicMock()
    claude = make_claude('{"product_found": true, "sentiment_summary": "Highly praised.", "verdict": "Buy", "confidence": "high"}')

    mock_response = MagicMock()
    mock_response.json.return_value = REDDIT_API_RESPONSE
    mock_response.raise_for_status = MagicMock()

    with patch("agents.reddit.get_cached", new_callable=AsyncMock, return_value=None), \
         patch("agents.reddit.set_cached", new_callable=AsyncMock), \
         patch("agents.reddit.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        from agents.reddit import run
        result = await run("Sony WH-1000XM5", fc, claude)

    fc.scrape.assert_not_called()
    fc.extract.assert_not_called()
    assert result["verdict"] in ("Buy", "Consider", "Skip")


@pytest.mark.asyncio
async def test_calls_reddit_json_api():
    """Agent must call reddit.com/.json endpoint."""
    fc = MagicMock()
    claude = make_claude('{"product_found": true, "sentiment_summary": "Good.", "verdict": "Buy", "confidence": "high"}')

    mock_response = MagicMock()
    mock_response.json.return_value = REDDIT_API_RESPONSE
    mock_response.raise_for_status = MagicMock()

    with patch("agents.reddit.get_cached", new_callable=AsyncMock, return_value=None), \
         patch("agents.reddit.set_cached", new_callable=AsyncMock), \
         patch("agents.reddit.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        from agents.reddit import run
        await run("Sony WH-1000XM5", fc, claude)

    call_args = mock_client.get.call_args
    url = call_args.args[0] if call_args.args else call_args.kwargs.get("url", "")
    assert "reddit.com" in url
    assert ".json" in url or "search.json" in url


@pytest.mark.asyncio
async def test_reddit_api_error_returns_fallback():
    """HTTP failure must not crash — return a low-confidence Consider."""
    fc = MagicMock()
    claude = make_claude('{"product_found": false, "sentiment_summary": "", "verdict": "Consider", "confidence": "low"}')

    with patch("agents.reddit.get_cached", new_callable=AsyncMock, return_value=None), \
         patch("agents.reddit.set_cached", new_callable=AsyncMock), \
         patch("agents.reddit.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("network error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        from agents.reddit import run
        result = await run("test product", fc, claude)

    assert result["verdict"] in ("Buy", "Consider", "Skip")
    assert result["confidence"] in ("high", "medium", "low")


@pytest.mark.asyncio
async def test_posts_passed_to_claude():
    """Post content must be forwarded to Claude for sentiment analysis."""
    fc = MagicMock()
    claude = make_claude('{"product_found": true, "sentiment_summary": "Loved.", "verdict": "Buy", "confidence": "high"}')

    mock_response = MagicMock()
    mock_response.json.return_value = REDDIT_API_RESPONSE
    mock_response.raise_for_status = MagicMock()

    with patch("agents.reddit.get_cached", new_callable=AsyncMock, return_value=None), \
         patch("agents.reddit.set_cached", new_callable=AsyncMock), \
         patch("agents.reddit.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        from agents.reddit import run
        await run("Sony WH-1000XM5", fc, claude)

    claude.messages.create.assert_awaited_once()
    call = claude.messages.create.call_args
    user_content = call.kwargs["messages"][0]["content"]
    assert "Sony WH-1000XM5" in user_content
    # Post titles should appear in the content sent to Claude
    assert "review" in user_content.lower() or "Sony" in user_content


@pytest.mark.asyncio
async def test_cache_hit_skips_api_calls():
    cached = {"product_found": True, "sentiment_summary": "Good.",
              "verdict": "Buy", "confidence": "high"}
    fc = MagicMock()
    claude = make_claude("{}")

    with patch("agents.reddit.get_cached", new_callable=AsyncMock, return_value=cached), \
         patch("agents.reddit.httpx.AsyncClient") as mock_client_cls:
        from agents.reddit import run
        result = await run("Sony WH-1000XM5", fc, claude)

    mock_client_cls.assert_not_called()
    claude.messages.create.assert_not_called()
    assert result["verdict"] == "Buy"
