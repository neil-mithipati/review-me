"""Unit tests for the Amazon source agent."""
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import make_claude, make_firecrawl


@pytest.mark.asyncio
async def test_uses_extract_with_keyword_args():
    fc = make_firecrawl({"product_found": True, "star_rating": 4.6,
                          "review_count": 20000, "common_complaints": [],
                          "is_amazon_choice": True, "is_best_seller": False})
    claude = make_claude('{"verdict": "Buy", "confidence": "high"}')

    with patch("agents.amazon.get_cached", new_callable=AsyncMock, return_value=None), \
         patch("agents.amazon.set_cached", new_callable=AsyncMock):
        from agents.amazon import run
        await run("Sony WH-1000XM5", fc, claude)

    call = fc.extract.call_args
    assert "prompt" in call.kwargs
    assert "schema" in call.kwargs


@pytest.mark.asyncio
@pytest.mark.parametrize("rating,count,expected_verdict,expected_conf", [
    (4.7, 2000, "Buy",     "high"),
    (4.5, 500,  "Buy",     "high"),
    (4.5, 499,  "Consider","low"),   # not enough reviews
    (4.2, 500,  "Consider","medium"),
    (4.0, 100,  "Consider","medium"),
    (3.9, 100,  "Skip",    "medium"),
    (3.0, 5000, "Skip",    "medium"),
])
async def test_rating_mapping(rating, count, expected_verdict, expected_conf):
    fc = make_firecrawl({"product_found": True, "star_rating": rating,
                          "review_count": count, "common_complaints": [],
                          "is_amazon_choice": False, "is_best_seller": False})
    claude = make_claude(f'{{"verdict": "{expected_verdict}", "confidence": "{expected_conf}"}}')

    with patch("agents.amazon.get_cached", new_callable=AsyncMock, return_value=None), \
         patch("agents.amazon.set_cached", new_callable=AsyncMock):
        from agents.amazon import run
        result = await run("test product", fc, claude)

    assert result["verdict"] == expected_verdict
    assert result["confidence"] == expected_conf


@pytest.mark.asyncio
async def test_badges_preserved():
    fc = make_firecrawl({"product_found": True, "star_rating": 4.6,
                          "review_count": 1000, "common_complaints": ["Heavy"],
                          "is_amazon_choice": True, "is_best_seller": True})
    claude = make_claude('{"verdict": "Buy", "confidence": "high"}')

    with patch("agents.amazon.get_cached", new_callable=AsyncMock, return_value=None), \
         patch("agents.amazon.set_cached", new_callable=AsyncMock):
        from agents.amazon import run
        result = await run("test product", fc, claude)

    assert result["is_amazon_choice"] is True
    assert result["is_best_seller"] is True
    assert result["common_complaints"] == ["Heavy"]


@pytest.mark.asyncio
async def test_not_found_returns_low_confidence():
    fc = make_firecrawl({"product_found": False})
    claude = make_claude('{"verdict": "Consider", "confidence": "low"}')

    with patch("agents.amazon.get_cached", new_callable=AsyncMock, return_value=None), \
         patch("agents.amazon.set_cached", new_callable=AsyncMock):
        from agents.amazon import run
        result = await run("test product", fc, claude)

    assert result["confidence"] == "low"
