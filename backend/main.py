import asyncio
import json
import logging
import os
import uuid

logger = logging.getLogger(__name__)
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Optional

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from firecrawl import FirecrawlApp
from pydantic import BaseModel

from agents import amazon, cnet, orchestrator, reddit, wirecutter
from evals import get_evals_for_review, run_evals
from db.database import (
    add_to_wishlist,
    get_wishlist,
    init_db,
    remove_from_wishlist,
)

load_dotenv()

SOURCES = ["wirecutter", "cnet", "amazon", "reddit"]
SOURCE_AGENTS = {
    "wirecutter": wirecutter.run,
    "cnet": cnet.run,
    "amazon": amazon.run,
    "reddit": reddit.run,
}

firecrawl_client: Optional[FirecrawlApp] = None
claude_client: Optional[anthropic.AsyncAnthropic] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global firecrawl_client, claude_client
    await init_db()
    firecrawl_client = FirecrawlApp(api_key=os.environ["FIRECRAWL_API_KEY"])
    claude_client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    yield


app = FastAPI(lifespan=lifespan)
_raw_origins = os.environ.get("ALLOWED_ORIGINS", "*")
_allowed_origins = [o.strip() for o in _raw_origins.split(",")] if _raw_origins != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory review sessions
reviews: dict[str, "ReviewSession"] = {}


@dataclass
class ReviewSession:
    review_id: str
    product_name: str
    source_status: dict = field(default_factory=lambda: {s: "loading" for s in SOURCES})
    source_data: dict = field(default_factory=lambda: {s: None for s in SOURCES})
    source_error: dict = field(default_factory=lambda: {s: None for s in SOURCES})
    verdict_status: str = "loading"
    verdict_data: Optional[dict] = None
    subscriber_queues: list = field(default_factory=list)

    def broadcast(self, event_type: str, data: dict):
        for q in self.subscriber_queues:
            q.put_nowait({"type": event_type, "data": data})

    def broadcast_done(self):
        for q in self.subscriber_queues:
            q.put_nowait(None)


# ── Pydantic models ──────────────────────────────────────────────────────────

class ReviewRequest(BaseModel):
    query: str

class ClarifyRequest(BaseModel):
    choice: str

class WishlistRequest(BaseModel):
    product_name: str
    verdict: str
    review_id: str


# ── Helpers ──────────────────────────────────────────────────────────────────

async def resolve_category(query: str) -> tuple[bool, list[str]]:
    """Returns (is_ambiguous, candidates). Candidates are empty when not ambiguous."""
    message = await claude_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        messages=[
            {
                "role": "user",
                "content": (
                    f"The user searched for: '{query}'\n\n"
                    "Is this a specific product (e.g. 'Sony WH-1000XM5') or a vague category "
                    "(e.g. 'headphones', 'vacuum cleaner')?\n\n"
                    "If specific: respond with JSON: {\"ambiguous\": false}\n"
                    "If vague: respond with JSON: {\"ambiguous\": true, \"candidates\": [\"Product A\", \"Product B\", \"Product C\"]}\n"
                    "Candidates should be 2-3 popular, concrete products in that category.\n"
                    "Respond with JSON only."
                ),
            }
        ],
    )
    try:
        parsed = json.loads(message.content[0].text)
        if parsed.get("ambiguous"):
            return True, parsed.get("candidates", [])
    except (json.JSONDecodeError, IndexError, KeyError):
        pass
    return False, []


MAX_SOURCE_RETRIES = 1


async def run_review(session: ReviewSession):
    product = session.product_name

    async def run_source(source_name: str, retries_remaining: int = MAX_SOURCE_RETRIES):
        try:
            result = await SOURCE_AGENTS[source_name](product, firecrawl_client, claude_client)
            session.source_status[source_name] = "complete"
            session.source_data[source_name] = result
            session.broadcast(
                "source_update",
                {"source": source_name, "status": "complete", "data": result, "error": None},
            )
            eval_results = await run_evals(
                review_id=session.review_id,
                product=product,
                source=source_name,
                source_data=result,
                verdict=result.get("verdict", "Consider"),
                confidence=result.get("confidence", "low"),
                claude=claude_client,
            )
            # Retry if any eval scored 0 due to a genuine quality failure (not an API error)
            any_failed = any(
                r.get("score", 1.0) == 0.0 and r.get("label") != "error"
                for r in eval_results.values()
            )
            if any_failed and retries_remaining > 0:
                logger.info("Retrying source %s for %s — eval quality check failed", source_name, product)
                await run_source(source_name, retries_remaining - 1)
        except Exception as e:
            session.source_status[source_name] = "error"
            session.source_error[source_name] = str(e)
            session.broadcast(
                "source_update",
                {"source": source_name, "status": "error", "data": None, "error": str(e)},
            )
            asyncio.create_task(run_evals(
                review_id=session.review_id,
                product=product,
                source=source_name,
                source_data={"product_found": False, "error": str(e)},
                verdict="Consider",
                confidence="low",
                claude=claude_client,
            ))

    await asyncio.gather(*[run_source(s) for s in SOURCES])

    # Build source results for orchestrator (include errors as dicts)
    source_results = {}
    for s in SOURCES:
        if session.source_data[s]:
            source_results[s] = session.source_data[s]
        else:
            source_results[s] = {"error": session.source_error[s] or "no data"}

    try:
        verdict = await orchestrator.run(product, source_results, claude_client)
        session.verdict_status = "complete"
        session.verdict_data = verdict
        session.broadcast("verdict", verdict)
    except Exception as e:
        session.verdict_status = "error"
        session.broadcast("verdict", {"error": str(e)})

    session.broadcast_done()


# ── Routes ───────────────────────────────────────────────────────────────────

@app.post("/api/review")
async def start_review(body: ReviewRequest):
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    is_ambiguous, candidates = await resolve_category(query)
    review_id = str(uuid.uuid4())

    if is_ambiguous:
        # Store a pending session — no agents started yet
        session = ReviewSession(review_id=review_id, product_name=query)
        reviews[review_id] = session
        return {
            "review_id": review_id,
            "status": "clarification_needed",
            "candidates": candidates,
            "clarification_question": f"Which '{query}' did you mean?",
        }

    session = ReviewSession(review_id=review_id, product_name=query)
    reviews[review_id] = session
    asyncio.create_task(run_review(session))

    return {
        "review_id": review_id,
        "status": "running",
        "candidates": None,
        "clarification_question": None,
    }


@app.post("/api/review/{review_id}/clarify")
async def clarify_review(review_id: str, body: ClarifyRequest):
    if review_id not in reviews:
        raise HTTPException(status_code=404, detail="Review not found")

    session = reviews[review_id]
    session.product_name = body.choice.strip()
    asyncio.create_task(run_review(session))

    return {
        "review_id": review_id,
        "status": "running",
        "candidates": None,
        "clarification_question": None,
    }


@app.get("/api/review/{review_id}/stream")
async def stream_review(review_id: str):
    if review_id not in reviews:
        raise HTTPException(status_code=404, detail="Review not found")

    session = reviews[review_id]

    async def event_generator():
        # Immediately emit current state for all sources so late clients catch up
        for source_name in SOURCES:
            status = session.source_status[source_name]
            data = session.source_data[source_name]
            error = session.source_error[source_name]
            event_data = {
                "source": source_name,
                "status": status,
                "data": data,
                "error": error,
            }
            yield f"event: source_update\ndata: {json.dumps(event_data)}\n\n"

        if session.verdict_status == "complete" and session.verdict_data:
            yield f"event: verdict\ndata: {json.dumps(session.verdict_data)}\n\n"
            yield "event: done\ndata: {}\n\n"
            return

        # Subscribe to new events
        queue: asyncio.Queue = asyncio.Queue()
        session.subscriber_queues.append(queue)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue

                if event is None:
                    yield "event: done\ndata: {}\n\n"
                    break

                yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
        finally:
            if queue in session.subscriber_queues:
                session.subscriber_queues.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/wishlist")
async def list_wishlist():
    items = await get_wishlist()
    return {"items": items}


@app.post("/api/wishlist")
async def create_wishlist_item(body: WishlistRequest):
    item = await add_to_wishlist(body.product_name, body.verdict, body.review_id)
    return item


@app.delete("/api/wishlist/{item_id}")
async def delete_wishlist_item(item_id: int):
    removed = await remove_from_wishlist(item_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"success": True}


@app.get("/api/review/{review_id}/evals")
async def get_review_evals(review_id: str):
    evals = await get_evals_for_review(review_id)
    return {"review_id": review_id, "evals": evals}
