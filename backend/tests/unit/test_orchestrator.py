"""Unit tests for the orchestrator agent."""
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import make_claude


FULL_SOURCES = {
    "wirecutter": {"verdict": "Buy",     "confidence": "high", "verdict_tier": "Our Pick", "product_found": True},
    "cnet":       {"verdict": "Buy",     "confidence": "high", "overall_score": 9.0, "product_found": True},
    "amazon":     {"verdict": "Buy",     "confidence": "high", "star_rating": 4.7, "product_found": True},
    "reddit":     {"verdict": "Buy",     "confidence": "high", "sentiment_summary": "Loved.", "product_found": True},
}

MIXED_SOURCES = {
    "wirecutter": {"verdict": "Buy",     "confidence": "high"},
    "cnet":       {"verdict": "Skip",    "confidence": "high"},
    "amazon":     {"verdict": "Consider","confidence": "medium"},
    "reddit":     {"verdict": "Buy",     "confidence": "low"},
}


@pytest.mark.asyncio
async def test_unanimous_buy_returns_buy():
    claude = make_claude('{"verdict": "Buy", "summary": "Excellent headphones.", "notable_disagreements": null, "recommended_action": "buy"}')

    from agents.orchestrator import run
    result = await run("Sony WH-1000XM5", FULL_SOURCES, claude)

    assert result["verdict"] == "Buy"
    assert result["recommended_action"] == "buy"


@pytest.mark.asyncio
async def test_buy_verdict_includes_amazon_link():
    claude = make_claude('{"verdict": "Buy", "summary": "Great.", "notable_disagreements": null, "recommended_action": "buy"}')

    from agents.orchestrator import run
    result = await run("Sony WH-1000XM5", FULL_SOURCES, claude)

    assert result["buy_link"] is not None
    assert "amazon.com" in result["buy_link"]
    assert "Sony" in result["buy_link"] or "WH-1000XM5" in result["buy_link"]


@pytest.mark.asyncio
async def test_skip_verdict_has_no_buy_link():
    claude = make_claude('{"verdict": "Skip", "summary": "Not recommended.", "notable_disagreements": null, "recommended_action": "skip"}')
    sources = {k: {**v, "verdict": "Skip"} for k, v in FULL_SOURCES.items()}

    from agents.orchestrator import run
    result = await run("bad product", sources, claude)

    assert result["buy_link"] is None


@pytest.mark.asyncio
async def test_notable_disagreements_surfaced():
    claude = make_claude(
        '{"verdict": "Consider", "summary": "Mixed reviews.", '
        '"notable_disagreements": "Wirecutter says Buy but CNET says Skip.", '
        '"recommended_action": "consider"}'
    )

    from agents.orchestrator import run
    result = await run("test product", MIXED_SOURCES, claude)

    assert result["notable_disagreements"] is not None
    assert len(result["notable_disagreements"]) > 0


@pytest.mark.asyncio
async def test_handles_errored_sources():
    """Orchestrator must still return a verdict when some sources failed."""
    partial_sources = {
        "wirecutter": {"verdict": "Buy", "confidence": "high"},
        "cnet":       {"error": "not supported"},
        "amazon":     {"verdict": "Buy", "confidence": "high"},
        "reddit":     {"error": "network error"},
    }
    claude = make_claude('{"verdict": "Buy", "summary": "Based on available sources.", "notable_disagreements": null, "recommended_action": "buy"}')

    from agents.orchestrator import run
    result = await run("test product", partial_sources, claude)

    assert result["verdict"] in ("Buy", "Consider", "Skip")


@pytest.mark.asyncio
async def test_all_errored_sources_returns_consider():
    """If all sources fail, orchestrator should return a fallback."""
    all_errored = {s: {"error": "failed"} for s in ["wirecutter", "cnet", "amazon", "reddit"]}
    claude = make_claude("this is not json")  # Simulate Claude also failing to parse

    from agents.orchestrator import run
    result = await run("test product", all_errored, claude)

    assert result["verdict"] in ("Buy", "Consider", "Skip")
    assert result["summary"] != ""


@pytest.mark.asyncio
async def test_all_source_results_sent_to_claude():
    """All 4 source results must appear in the message sent to Claude."""
    claude = make_claude('{"verdict": "Buy", "summary": "Great.", "notable_disagreements": null, "recommended_action": "buy"}')

    from agents.orchestrator import run
    await run("Sony WH-1000XM5", FULL_SOURCES, claude)

    call = claude.messages.create.call_args
    user_content = call.kwargs["messages"][0]["content"]
    for source in ["WIRECUTTER", "CNET", "AMAZON", "REDDIT"]:
        assert source in user_content
