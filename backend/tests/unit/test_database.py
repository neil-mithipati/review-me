"""Unit tests for SQLite cache and wishlist operations."""
import pytest
import db.database as dbmod


@pytest.mark.asyncio
async def test_cache_miss_returns_none(tmp_db):
    result = await dbmod.get_cached("product", "wirecutter")
    assert result is None


@pytest.mark.asyncio
async def test_cache_set_and_get(tmp_db):
    data = {"verdict": "Buy", "confidence": "high"}
    await dbmod.set_cached("Sony WH-1000XM5", "wirecutter", data)
    result = await dbmod.get_cached("Sony WH-1000XM5", "wirecutter")
    assert result == data


@pytest.mark.asyncio
async def test_cache_key_is_normalised(tmp_db):
    data = {"verdict": "Buy"}
    await dbmod.set_cached("  Sony WH-1000XM5  ", "amazon", data)
    # Different whitespace / casing should still hit
    result = await dbmod.get_cached("sony wh-1000xm5", "amazon")
    assert result == data


@pytest.mark.asyncio
async def test_cache_upserts_on_duplicate(tmp_db):
    await dbmod.set_cached("product", "cnet", {"verdict": "Consider"})
    await dbmod.set_cached("product", "cnet", {"verdict": "Buy"})
    result = await dbmod.get_cached("product", "cnet")
    assert result["verdict"] == "Buy"


@pytest.mark.asyncio
async def test_cache_expired_returns_none(tmp_db, monkeypatch):
    from datetime import datetime, timedelta
    await dbmod.set_cached("product", "reddit", {"verdict": "Skip"})

    # Patch _now() to return a time far in the future
    future = datetime.utcnow() + timedelta(hours=200)
    monkeypatch.setattr(dbmod, "_now", lambda: future)

    result = await dbmod.get_cached("product", "reddit")
    assert result is None


@pytest.mark.asyncio
async def test_wishlist_add_and_list(tmp_db):
    item = await dbmod.add_to_wishlist("AirPods Pro", "Buy", "review-123")
    assert item["product_name"] == "AirPods Pro"
    assert item["verdict"] == "Buy"

    items = await dbmod.get_wishlist()
    assert len(items) == 1
    assert items[0]["id"] == item["id"]


@pytest.mark.asyncio
async def test_wishlist_remove(tmp_db):
    item = await dbmod.add_to_wishlist("Dyson V15", "Consider", "review-456")
    removed = await dbmod.remove_from_wishlist(item["id"])
    assert removed is True
    items = await dbmod.get_wishlist()
    assert items == []


@pytest.mark.asyncio
async def test_wishlist_remove_nonexistent(tmp_db):
    removed = await dbmod.remove_from_wishlist(9999)
    assert removed is False


@pytest.mark.asyncio
async def test_wishlist_ordered_newest_first(tmp_db):
    await dbmod.add_to_wishlist("Product A", "Buy", "r1")
    await dbmod.add_to_wishlist("Product B", "Skip", "r2")
    items = await dbmod.get_wishlist()
    assert items[0]["product_name"] == "Product B"
