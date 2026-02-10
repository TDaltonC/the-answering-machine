import asyncio
import os
from datetime import datetime, timezone

import requests
from browser_use import Agent, Browser
from browser_use.llm import ChatAnthropic
from dotenv import load_dotenv

from config import load_family
from firestore_client import get_db
from parsing import parse_agent_picks

load_dotenv()

CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY", "")
CARTESIA_AGENT_ID = os.getenv("CARTESIA_AGENT_ID", "")


def build_task(family: dict, summaries: list[str]) -> str:
    child = family["child_name"]
    age = family["child_age"]
    persona = f"{age}-year-old boy, showing signs of being nerdy"
    summary_block = "\n".join(f"  - {s}" for s in summaries)
    return f"""\
You are a children's librarian helping pick books for a kid.

## Who the books are for
{persona}

## What they've been interested in lately
{summary_block}

## STEP 1 — Brainstorm candidates in your head
Before you interact with the browser, think of 8-10 children's books that would be
a great fit. Consider picture books, early readers, and engaging non-fiction
appropriate for the age. Keep this ranked list in your memory — you'll work through
it in order. Do NOT call the "done" action yet. You are nowhere near done.

## STEP 2 — Search SFPL catalog
Now go to https://sfpl.org and search for your #1 candidate using the search bar.

For each search:
a) Type the book title into the search box and submit.
b) Look at the results list. Find the matching book.
c) CLICK INTO the book's detail page to check its availability status.
d) If the detail page shows "Available" copies at any branch → this book is CONFIRMED.
   Record it as a winner and note which branch has it.
e) If it shows "All copies in use" or no results → SKIP it and search your next candidate.
f) Go back to the search bar and repeat with the next candidate.

IMPORTANT RULES:
- You must CLICK INTO each book's detail page. Do NOT judge availability from the
  search results list alone — it is not reliable.
- NEVER report a book you did not actually find and verify on sfpl.org.
- If you run out of candidates, brainstorm a few more and keep searching.

## STEP 3 — Report your final picks (this is the ONLY time you should call "done")
Aim for 3 confirmed books, but 2 is acceptable if the browser crashes or the site
becomes unresponsive. Call "done" with:

FINAL PICKS:
1. "Title" by Author — Why it fits + which SFPL branch has it available
2. "Title" by Author — Why it fits + which SFPL branch has it available
3. "Title" by Author — Why it fits + which SFPL branch has it available

Only include books you personally verified as available on sfpl.org in Step 2.
Do NOT call "done" until you have at least 2 confirmed books.
"""


def save_recommendations(family_id: str, agent_result) -> None:
    """Parse agent picks and write to Firestore as recommendations."""
    text = agent_result.final_result()
    books = parse_agent_picks(text)
    if not books:
        print("Warning: could not parse any books from agent result")
        return

    db = get_db()
    recs_ref = db.collection("families").document(family_id).collection("recommendations")

    # Delete stale "recommended" docs from previous runs
    stale = recs_ref.where("status", "==", "recommended").stream()
    for doc in stale:
        doc.reference.delete()

    now = datetime.now(timezone.utc)
    for book in books:
        recs_ref.add({
            "title": book["title"],
            "author": book["author"],
            "why": book["why"],
            "branch": "",
            "status": "recommended",
            "searched_at": now,
            "updated_at": now,
        })

    print(f"Saved {len(books)} recommendations to Firestore")


def sync_call_summaries(family_id: str) -> int:
    """Fetch recent calls from Cartesia, backfill any missing summaries to Firestore."""
    if not CARTESIA_API_KEY or not CARTESIA_AGENT_ID:
        print("Cartesia credentials not set, skipping call sync")
        return 0

    resp = requests.get(
        "https://api.cartesia.ai/agents/calls",
        params={"agent_id": CARTESIA_AGENT_ID, "expand": "transcript", "limit": 20},
        headers={"X-API-Key": CARTESIA_API_KEY, "Cartesia-Version": "2025-04-16"},
        timeout=10,
    )
    resp.raise_for_status()
    calls = resp.json().get("data", [])

    db = get_db()
    summaries_ref = db.collection("families").document(family_id).collection("summaries")

    # Get existing call_ids from Firestore
    existing_docs = summaries_ref.stream()
    existing_ids = set()
    for doc in existing_docs:
        d = doc.to_dict()
        # Check both doc ID and call_id field
        existing_ids.add(doc.id)
        if d.get("call_id"):
            existing_ids.add(d["call_id"])

    backfilled = 0
    for call in calls:
        call_id = call["id"]
        if call_id in existing_ids:
            continue
        if call.get("status") != "completed":
            continue

        summary = call.get("summary", "")
        if not summary:
            continue

        # Extract topics from transcript (user turns only)
        user_texts = [
            t["text"] for t in call.get("transcript", []) if t.get("role") == "user"
        ]

        summaries_ref.document(call_id).set({
            "summary_text": summary,
            "topics": [],
            "mode": "standard",
            "call_id": call_id,
            "source": "cartesia_backfill",
            "created_at": datetime.fromisoformat(call["start_time"].replace("Z", "+00:00")),
            "user_turns": user_texts,
        })
        print(f"  Backfilled summary for call {call_id}")
        backfilled += 1

    return backfilled


def load_summaries(family_id: str) -> list[str]:
    """Load summaries from Firestore."""
    try:
        db = get_db()
        docs = (
            db.collection("families")
            .document(family_id)
            .collection("summaries")
            .order_by("created_at", direction="DESCENDING")
            .limit(5)
            .stream()
        )
        summaries = [doc.to_dict().get("summary_text", "") for doc in docs]
        summaries = [s for s in summaries if s]  # drop blanks
        if summaries:
            print(f"Loaded {len(summaries)} summaries from Firestore")
            return summaries
    except Exception as e:
        print(f"Warning: could not load summaries from Firestore: {e}")

    return []


async def main():
    family = load_family()
    family_id = family.get("family_id", "leo")

    # Sync any missed call summaries from Cartesia before loading
    print("Syncing call summaries from Cartesia...")
    backfilled = sync_call_summaries(family_id)
    print(f"Synced {backfilled} new summaries from Cartesia")

    summaries = load_summaries(family_id)
    if not summaries:
        print("No summaries found — nothing to search for. Exiting.")
        return

    task = build_task(family, summaries)

    browser = Browser()
    llm = ChatAnthropic(model="claude-sonnet-4-5-20250929")

    agent = Agent(task=task, llm=llm, browser=browser)
    result = await agent.run()
    save_recommendations(family_id, result)


if __name__ == "__main__":
    asyncio.run(main())
