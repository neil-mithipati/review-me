"""Integration tests for FastAPI endpoints.

These tests use the real FastAPI app with mocked agent functions,
so they test the API contract without hitting external services.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

import db.database as dbmod


# Patch out agent runs and lifespan startup so we can test cleanly
MOCK_SOURCE_RESULT = {
    "wirecutter": {"verdict": "Buy",     "confidence": "high", "product_found": True},
    "cnet":       {"verdict": "Buy",     "confidence": "high", "product_found": True},
    "amazon":     {"verdict": "Buy",     "confidence": "high", "product_found": True},
    "reddit":     {"verdict": "Buy",     "confidence": "high", "product_found": True},
}

MOCK_VERDICT = {
    "verdict": "Buy",
    "summary": "Great product all around.",
    "notable_disagreements": None,
    "buy_link": "https://www.amazon.com/s?k=test+product",
    "recommended_action": "buy",
}


@pytest.fixture(autouse=True)
async def patch_db(monkeypatch, tmp_path):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(dbmod, "DB_PATH", db_file)
    await dbmod.init_db()


@pytest.fixture
def app_with_mocks(monkeypatch, tmp_path):
    """Returns the FastAPI app with external dependencies mocked."""
    import main

    # Provide mock clients
    monkeypatch.setattr(main, "firecrawl_client", MagicMock())
    monkeypatch.setattr(main, "claude_client", MagicMock())

    return main.app


@pytest.fixture
async def client(app_with_mocks):
    async with AsyncClient(
        transport=ASGITransport(app=app_with_mocks), base_url="http://test"
    ) as c:
        yield c


# ── POST /api/review ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_start_review_returns_review_id(client):
    with patch("main.resolve_category", new_callable=AsyncMock, return_value=(False, [])):
        resp = await client.post("/api/review", json={"query": "Sony WH-1000XM5"})

    assert resp.status_code == 200
    data = resp.json()
    assert "review_id" in data
    assert data["status"] == "running"
    assert data["candidates"] is None


@pytest.mark.asyncio
async def test_empty_query_returns_400(client):
    resp = await client.post("/api/review", json={"query": ""})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_ambiguous_query_returns_clarification(client):
    candidates = ["Sony WH-1000XM5", "Bose QC45", "Apple AirPods Pro"]
    with patch("main.resolve_category", new_callable=AsyncMock, return_value=(True, candidates)):
        resp = await client.post("/api/review", json={"query": "headphones"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "clarification_needed"
    assert data["candidates"] == candidates
    assert data["clarification_question"] is not None


# ── POST /api/review/{id}/clarify ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_clarify_starts_review(client):
    with patch("main.resolve_category", new_callable=AsyncMock, return_value=(True, ["Bose QC45"])):
        create_resp = await client.post("/api/review", json={"query": "headphones"})
    review_id = create_resp.json()["review_id"]

    with patch("main.run_review", new_callable=AsyncMock):
        resp = await client.post(f"/api/review/{review_id}/clarify", json={"choice": "Bose QC45"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"


@pytest.mark.asyncio
async def test_clarify_unknown_id_returns_404(client):
    resp = await client.post("/api/review/does-not-exist/clarify", json={"choice": "something"})
    assert resp.status_code == 404


# ── GET /api/review/{id}/stream ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stream_unknown_id_returns_404(client):
    resp = await client.get("/api/review/does-not-exist/stream")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stream_returns_sse_content_type(client):
    import main
    from main import ReviewSession

    session = ReviewSession(review_id="test-123", product_name="test product")
    for source in ["wirecutter", "cnet", "amazon", "reddit"]:
        session.source_status[source] = "complete"
        session.source_data[source] = MOCK_SOURCE_RESULT[source]
    session.verdict_status = "complete"
    session.verdict_data = MOCK_VERDICT
    main.reviews["test-123"] = session

    resp = await client.get("/api/review/test-123/stream")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    body = resp.text
    assert "source_update" in body
    assert "verdict" in body
    assert "done" in body


# ── Wishlist endpoints ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_wishlist_initially_empty(client):
    resp = await client.get("/api/wishlist")
    assert resp.status_code == 200
    assert resp.json() == {"items": []}


@pytest.mark.asyncio
async def test_add_to_wishlist(client):
    resp = await client.post("/api/wishlist", json={
        "product_name": "AirPods Pro",
        "verdict": "Buy",
        "review_id": "review-abc",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["product_name"] == "AirPods Pro"
    assert data["verdict"] == "Buy"
    assert "id" in data


@pytest.mark.asyncio
async def test_wishlist_persists_items(client):
    await client.post("/api/wishlist", json={"product_name": "Test", "verdict": "Buy", "review_id": "r1"})
    resp = await client.get("/api/wishlist")
    assert len(resp.json()["items"]) == 1


@pytest.mark.asyncio
async def test_delete_wishlist_item(client):
    add_resp = await client.post("/api/wishlist", json={"product_name": "Test", "verdict": "Buy", "review_id": "r1"})
    item_id = add_resp.json()["id"]

    del_resp = await client.delete(f"/api/wishlist/{item_id}")
    assert del_resp.status_code == 200
    assert del_resp.json() == {"success": True}

    list_resp = await client.get("/api/wishlist")
    assert list_resp.json()["items"] == []


@pytest.mark.asyncio
async def test_delete_nonexistent_item_returns_404(client):
    resp = await client.delete("/api/wishlist/9999")
    assert resp.status_code == 404


# ── run_review retry logic ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_source_retried_when_eval_scores_zero(monkeypatch, tmp_path):
    """run_source retries once when any eval judge scores 0 (non-error label)."""
    import main
    from main import ReviewSession, run_review
    from tests.conftest import make_claude

    db_file = tmp_path / "retry_test.db"
    monkeypatch.setattr(dbmod, "DB_PATH", db_file)
    await dbmod.init_db()

    call_counts = {"amazon": 0}

    async def fake_amazon(product, fc, claude):
        call_counts["amazon"] += 1
        return {"verdict": "Buy", "confidence": "high", "product_found": True,
                "star_rating": 4.8, "review_count": 5000,
                "common_complaints": [], "is_amazon_choice": False, "is_best_seller": False}

    stub_result = {"verdict": "Buy", "confidence": "high", "product_found": True}

    # Use setitem to patch individual entries in the SOURCE_AGENTS dict
    monkeypatch.setitem(main.SOURCE_AGENTS, "amazon", fake_amazon)
    for source in ["wirecutter", "cnet", "reddit"]:
        monkeypatch.setitem(main.SOURCE_AGENTS, source, AsyncMock(return_value=stub_result))

    # Eval always returns score 0 with a non-error label → triggers retry
    fail_claude = make_claude('{"label": "unrelated", "score": 0.0, "explanation": "wrong product"}')
    monkeypatch.setattr(main, "firecrawl_client", MagicMock())
    monkeypatch.setattr(main, "claude_client", fail_claude)
    monkeypatch.setattr(main, "orchestrator", MagicMock(run=AsyncMock(return_value={
        "verdict": "Buy", "summary": "ok",
        "notable_disagreements": None, "buy_link": None, "recommended_action": "buy",
    })))

    session = ReviewSession(review_id="retry-test", product_name="Sony WH-1000XM5")
    main.reviews["retry-test"] = session

    await run_review(session)

    # Amazon agent should have been called twice: initial + 1 retry
    assert call_counts["amazon"] == 2


# ── Integration: real agent pipeline (skipped without API keys) ───────────────

@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_review_pipeline_real_apis():
    """Runs a real review end-to-end. Requires ANTHROPIC_API_KEY and FIRECRAWL_API_KEY."""
    import os
    if not os.environ.get("ANTHROPIC_API_KEY") or not os.environ.get("FIRECRAWL_API_KEY"):
        pytest.skip("API keys not set")

    import asyncio
    import anthropic
    from firecrawl import FirecrawlApp
    import agents.amazon as amazon_agent

    fc = FirecrawlApp(api_key=os.environ["FIRECRAWL_API_KEY"])
    claude = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    with patch("agents.amazon.get_cached", new_callable=AsyncMock, return_value=None), \
         patch("agents.amazon.set_cached", new_callable=AsyncMock):
        result = await amazon_agent.run("Sony WH-1000XM5", fc, claude)

    assert result["product_found"] is True
    assert result["verdict"] in ("Buy", "Consider", "Skip")
    assert result["star_rating"] is not None
    assert result["star_rating"] >= 1.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reddit_agent_real_api():
    """Runs the Reddit agent against the real Reddit JSON API."""
    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    from unittest.mock import MagicMock
    import anthropic
    import agents.reddit as reddit_agent

    claude = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    with patch("agents.reddit.get_cached", new_callable=AsyncMock, return_value=None), \
         patch("agents.reddit.set_cached", new_callable=AsyncMock):
        result = await reddit_agent.run("Sony WH-1000XM5", MagicMock(), claude)

    assert result["verdict"] in ("Buy", "Consider", "Skip")
    assert result["confidence"] in ("high", "medium", "low")
    assert isinstance(result["sentiment_summary"], str)
