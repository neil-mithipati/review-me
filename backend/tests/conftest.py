import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest

# ── Firecrawl mock helpers ────────────────────────────────────────────────────

class FakeExtractResponse:
    """Mimics firecrawl.v2.types.ExtractResponse"""
    def __init__(self, data):
        self.data = data
        self.success = True
        self.error = None


class FakeScrapeDocument:
    """Mimics firecrawl.v2.types.Document"""
    def __init__(self, markdown: str):
        self.markdown = markdown


def make_firecrawl(extract_data=None, scrape_markdown=""):
    """Returns a mock FirecrawlApp instance."""
    fc = MagicMock()
    fc.extract.return_value = FakeExtractResponse(extract_data or {})
    fc.scrape.return_value = FakeScrapeDocument(scrape_markdown)
    return fc


# ── Claude mock helpers ───────────────────────────────────────────────────────

def make_claude_response(json_text: str):
    msg = MagicMock()
    msg.content = [MagicMock(text=json_text)]
    return msg


def make_claude(json_text: str):
    """Returns an AsyncAnthropic mock that always responds with json_text."""
    claude = MagicMock()
    claude.messages = MagicMock()
    claude.messages.create = AsyncMock(return_value=make_claude_response(json_text))
    return claude


# ── Temporary SQLite DB fixture ───────────────────────────────────────────────

@pytest.fixture
async def tmp_db(monkeypatch, tmp_path):
    """Patches DB_PATH to a temp file and initialises the schema."""
    import db.database as dbmod
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(dbmod, "DB_PATH", db_file)
    await dbmod.init_db()
    return db_file
