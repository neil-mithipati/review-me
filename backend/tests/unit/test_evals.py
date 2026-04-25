"""Unit tests for the LLM judge eval pipeline."""
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import make_claude

AMAZON_DATA = {
    "product_found": True,
    "star_rating": 4.7,
    "review_count": 20000,
    "common_complaints": [],
    "is_amazon_choice": True,
    "is_best_seller": False,
}

REDDIT_DATA = {
    "product_found": True,
    "sentiment_summary": "Community loves it. Best ANC headphones on the market.",
}


@pytest.mark.asyncio
async def test_run_evals_calls_all_three_judges(tmp_db):
    claude = make_claude('{"label": "faithful", "score": 1.0, "explanation": "ok"}')

    from evals import run_evals
    results = await run_evals(
        review_id="rev-001",
        product="Sony WH-1000XM5",
        source="amazon",
        source_data=AMAZON_DATA,
        verdict="Buy",
        confidence="high",
        claude=claude,
    )

    assert set(results.keys()) == {"faithfulness", "correctness", "relevance"}
    # Claude was called once per judge
    assert claude.messages.create.await_count == 3


@pytest.mark.asyncio
async def test_eval_results_stored_in_db(tmp_db):
    claude = make_claude('{"label": "faithful", "score": 1.0, "explanation": "grounded"}')

    from evals import run_evals, get_evals_for_review
    await run_evals(
        review_id="rev-002",
        product="AirPods Pro",
        source="reddit",
        source_data=REDDIT_DATA,
        verdict="Buy",
        confidence="high",
        claude=claude,
    )

    rows = await get_evals_for_review("rev-002")
    assert len(rows) == 3
    judges = {r["judge"] for r in rows}
    assert judges == {"faithfulness", "correctness", "relevance"}


@pytest.mark.asyncio
async def test_eval_scores_stored_correctly(tmp_db):
    def side_effect(**kwargs):
        from tests.conftest import make_claude_response
        msg = kwargs["messages"][0]["content"]
        # Return different scores per judge based on system prompt content
        system_text = kwargs["system"][0]["text"]
        if "faithfulness" in system_text.lower():
            return make_claude_response('{"label": "faithful", "score": 1.0, "explanation": "ok"}')
        elif "correctness" in system_text.lower():
            return make_claude_response('{"label": "incorrect", "score": 0.0, "explanation": "wrong"}')
        else:
            return make_claude_response('{"label": "relevant", "score": 1.0, "explanation": "found"}')

    claude = make_claude("{}")
    claude.messages.create = AsyncMock(side_effect=side_effect)

    from evals import run_evals, get_evals_for_review
    await run_evals("rev-003", "product", "amazon", AMAZON_DATA, "Buy", "high", claude)

    rows = await get_evals_for_review("rev-003")
    scores = {r["judge"]: r["score"] for r in rows}
    assert scores["faithfulness"] == 1.0
    assert scores["correctness"] == 0.0
    assert scores["relevance"] == 1.0


@pytest.mark.asyncio
async def test_judge_failure_does_not_raise(tmp_db):
    """A judge crashing must not bubble up — it logs and continues."""
    claude = make_claude("{}")
    claude.messages.create = AsyncMock(side_effect=Exception("Claude API down"))

    from evals import run_evals
    results = await run_evals("rev-004", "product", "cnet", {}, "Consider", "low", claude)

    assert set(results.keys()) == {"faithfulness", "correctness", "relevance"}
    for r in results.values():
        assert r["label"] == "error"


@pytest.mark.asyncio
async def test_malformed_judge_response_returns_unknown(tmp_db):
    claude = make_claude("this is not JSON")

    from evals import run_evals
    results = await run_evals("rev-005", "product", "wirecutter", {}, "Buy", "high", claude)

    for r in results.values():
        assert r["score"] == 0.0


@pytest.mark.asyncio
async def test_get_evals_for_unknown_review_returns_empty(tmp_db):
    from evals import get_evals_for_review
    rows = await get_evals_for_review("does-not-exist")
    assert rows == []


@pytest.mark.asyncio
async def test_evals_run_for_all_four_sources(tmp_db):
    """Verify evals can be stored for all 4 sources without collision."""
    claude = make_claude('{"label": "faithful", "score": 1.0, "explanation": "ok"}')

    from evals import run_evals, get_evals_for_review
    for source in ["wirecutter", "cnet", "amazon", "reddit"]:
        await run_evals("rev-multi", "Dyson V15", source, {}, "Buy", "high", claude)

    rows = await get_evals_for_review("rev-multi")
    # 4 sources × 3 judges = 12 rows
    assert len(rows) == 12
    sources_seen = {r["source"] for r in rows}
    assert sources_seen == {"wirecutter", "cnet", "amazon", "reddit"}
