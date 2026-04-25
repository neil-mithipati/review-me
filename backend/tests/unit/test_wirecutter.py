"""Unit tests for the Wirecutter source agent."""
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import FakeExtractResponse, make_claude, make_firecrawl


@pytest.mark.asyncio
async def test_uses_extract_with_keyword_args():
    """extract() must be called with keyword arguments, not a positional dict."""
    fc = make_firecrawl({"product_found": True, "verdict_tier": "Our Pick",
                          "is_primary_recommendation": True, "blurb": "Great headphones."})
    claude = make_claude('{"verdict": "Buy", "confidence": "high"}')

    with patch("agents.wirecutter.get_cached", new_callable=AsyncMock, return_value=None), \
         patch("agents.wirecutter.set_cached", new_callable=AsyncMock):
        from agents.wirecutter import run
        await run("Sony WH-1000XM5", fc, claude)

    fc.extract.assert_called_once()
    call = fc.extract.call_args
    # Must use keyword args (prompt=, schema=), not positional dict
    assert "prompt" in call.kwargs
    assert "schema" in call.kwargs


@pytest.mark.asyncio
async def test_parses_extract_response_data_attribute():
    """Agent must read .data from ExtractResponse, not call .get('data')."""
    extract_data = {"product_found": True, "verdict_tier": "Also Great",
                    "is_primary_recommendation": False, "blurb": "Good pick."}
    fc = make_firecrawl(extract_data)
    claude = make_claude('{"verdict": "Buy", "confidence": "high"}')

    with patch("agents.wirecutter.get_cached", new_callable=AsyncMock, return_value=None), \
         patch("agents.wirecutter.set_cached", new_callable=AsyncMock):
        from agents.wirecutter import run
        result = await run("AirPods Pro", fc, claude)

    assert result["verdict_tier"] == "Also Great"
    assert result["verdict"] == "Buy"


@pytest.mark.asyncio
@pytest.mark.parametrize("tier,expected_verdict,expected_conf", [
    ("Our Pick",              "Buy",     "high"),
    ("Also Great",            "Buy",     "high"),
    ("Upgrade Pick",          "Consider","medium"),
    ("Budget Pick",           "Consider","medium"),
    ("No Longer Recommended", "Skip",    "high"),
    ("Not Listed",            "Consider","low"),
])
async def test_verdict_tier_mapping(tier, expected_verdict, expected_conf):
    fc = make_firecrawl({"product_found": True, "verdict_tier": tier,
                          "is_primary_recommendation": False, "blurb": ""})
    claude = make_claude(f'{{"verdict": "{expected_verdict}", "confidence": "{expected_conf}"}}')

    with patch("agents.wirecutter.get_cached", new_callable=AsyncMock, return_value=None), \
         patch("agents.wirecutter.set_cached", new_callable=AsyncMock):
        from agents.wirecutter import run
        result = await run("test product", fc, claude)

    assert result["verdict"] == expected_verdict
    assert result["confidence"] == expected_conf


@pytest.mark.asyncio
async def test_cache_hit_skips_firecrawl(tmp_db):
    cached = {"verdict": "Buy", "confidence": "high", "verdict_tier": "Our Pick",
              "product_found": True, "is_primary_recommendation": True, "blurb": ""}
    fc = make_firecrawl()
    claude = make_claude("{}")

    with patch("agents.wirecutter.get_cached", new_callable=AsyncMock, return_value=cached):
        from agents.wirecutter import run
        result = await run("Sony WH-1000XM5", fc, claude)

    fc.extract.assert_not_called()
    claude.messages.create.assert_not_called()
    assert result["verdict"] == "Buy"


@pytest.mark.asyncio
async def test_firecrawl_error_returns_fallback():
    fc = make_firecrawl()
    fc.extract.side_effect = Exception("Firecrawl timeout")
    claude = make_claude('{"verdict": "Consider", "confidence": "low"}')

    with patch("agents.wirecutter.get_cached", new_callable=AsyncMock, return_value=None), \
         patch("agents.wirecutter.set_cached", new_callable=AsyncMock):
        from agents.wirecutter import run
        result = await run("test product", fc, claude)

    assert result["verdict"] in ("Buy", "Consider", "Skip")


@pytest.mark.asyncio
async def test_malformed_claude_response_returns_fallback():
    fc = make_firecrawl({"product_found": False, "verdict_tier": "Not Listed",
                          "is_primary_recommendation": False, "blurb": ""})
    claude = make_claude("this is not json at all")

    with patch("agents.wirecutter.get_cached", new_callable=AsyncMock, return_value=None), \
         patch("agents.wirecutter.set_cached", new_callable=AsyncMock):
        from agents.wirecutter import run
        result = await run("test product", fc, claude)

    assert result["verdict"] in ("Buy", "Consider", "Skip")
    assert result["confidence"] in ("high", "medium", "low")


@pytest.mark.asyncio
async def test_result_is_cached_after_fetch():
    fc = make_firecrawl({"product_found": True, "verdict_tier": "Our Pick",
                          "is_primary_recommendation": True, "blurb": ""})
    claude = make_claude('{"verdict": "Buy", "confidence": "high"}')
    mock_set = AsyncMock()

    with patch("agents.wirecutter.get_cached", new_callable=AsyncMock, return_value=None), \
         patch("agents.wirecutter.set_cached", mock_set):
        from agents.wirecutter import run
        await run("Sony WH-1000XM5", fc, claude)

    mock_set.assert_awaited_once()
    args = mock_set.call_args
    assert args.args[0].lower().strip() == "sony wh-1000xm5"
    assert args.args[1] == "wirecutter"
