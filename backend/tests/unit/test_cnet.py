"""Unit tests for the CNET source agent."""
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import make_claude, make_firecrawl


@pytest.mark.asyncio
async def test_uses_extract_with_keyword_args():
    fc = make_firecrawl({"product_found": True, "overall_score": 8.5, "pros": [], "cons": []})
    claude = make_claude('{"verdict": "Buy", "confidence": "high"}')

    with patch("agents.cnet.get_cached", new_callable=AsyncMock, return_value=None), \
         patch("agents.cnet.set_cached", new_callable=AsyncMock):
        from agents.cnet import run
        await run("Sony WH-1000XM5", fc, claude)

    call = fc.extract.call_args
    assert "prompt" in call.kwargs
    assert "schema" in call.kwargs


@pytest.mark.asyncio
@pytest.mark.parametrize("score,expected_verdict,expected_conf", [
    (9.0, "Buy",     "high"),
    (8.0, "Buy",     "high"),
    (7.5, "Consider","high"),
    (7.0, "Consider","high"),
    (6.0, "Consider","low"),
    (5.0, "Consider","low"),
    (4.9, "Skip",    "high"),
    (0.0, "Skip",    "high"),
])
async def test_score_band_mapping(score, expected_verdict, expected_conf):
    fc = make_firecrawl({"product_found": True, "overall_score": score, "pros": [], "cons": []})
    claude = make_claude(f'{{"verdict": "{expected_verdict}", "confidence": "{expected_conf}"}}')

    with patch("agents.cnet.get_cached", new_callable=AsyncMock, return_value=None), \
         patch("agents.cnet.set_cached", new_callable=AsyncMock):
        from agents.cnet import run
        result = await run("test product", fc, claude)

    assert result["verdict"] == expected_verdict
    assert result["confidence"] == expected_conf


@pytest.mark.asyncio
async def test_handles_empty_list_response():
    """Firecrawl sometimes returns [] for CNET — must not crash."""
    fc = make_firecrawl([])   # list response
    claude = make_claude('{"verdict": "Consider", "confidence": "low"}')

    with patch("agents.cnet.get_cached", new_callable=AsyncMock, return_value=None), \
         patch("agents.cnet.set_cached", new_callable=AsyncMock):
        from agents.cnet import run
        result = await run("test product", fc, claude)

    assert result["verdict"] in ("Buy", "Consider", "Skip")


@pytest.mark.asyncio
async def test_cache_hit_skips_api_calls():
    cached = {"verdict": "Buy", "confidence": "high", "overall_score": 8.5,
              "product_found": True, "pros": [], "cons": []}
    fc = make_firecrawl()
    claude = make_claude("{}")

    with patch("agents.cnet.get_cached", new_callable=AsyncMock, return_value=cached):
        from agents.cnet import run
        result = await run("test product", fc, claude)

    fc.extract.assert_not_called()
    assert result["verdict"] == "Buy"


@pytest.mark.asyncio
async def test_pros_and_cons_preserved():
    fc = make_firecrawl({"product_found": True, "overall_score": 8.2,
                          "pros": ["Great sound", "Long battery"],
                          "cons": ["Expensive"]})
    claude = make_claude('{"verdict": "Buy", "confidence": "high"}')

    with patch("agents.cnet.get_cached", new_callable=AsyncMock, return_value=None), \
         patch("agents.cnet.set_cached", new_callable=AsyncMock):
        from agents.cnet import run
        result = await run("test product", fc, claude)

    assert result["pros"] == ["Great sound", "Long battery"]
    assert result["cons"] == ["Expensive"]
