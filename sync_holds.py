import asyncio
import os
import re
from datetime import datetime, timezone

from browser_use import Agent, Browser
from browser_use.llm import ChatAnthropic
from dotenv import load_dotenv

from config import load_family
from firestore_client import get_db

load_dotenv()

SFPL_USERNAME = os.environ["SFPL_USERNAME"]
SFPL_PASSWORD = os.environ["SFPL_PASSWORD"]

def map_sfpl_status(status_text: str) -> str | None:
    """Map SFPL status text to our status lifecycle value."""
    s = status_text.lower()
    if "ready for pickup" in s:
        return "ready"
    if "in transit" in s:
        return "in_transit"
    if any(kw in s for kw in ("on hold", "processing", "not ready")):
        return "hold_placed"
    return None


def load_active_holds(family_id: str) -> list[dict]:
    """Load recommendations with active hold statuses from Firestore."""
    db = get_db()
    recs = []
    for status in ("hold_placed", "in_transit"):
        docs = (
            db.collection("families")
            .document(family_id)
            .collection("recommendations")
            .where("status", "==", status)
            .stream()
        )
        for doc in docs:
            data = doc.to_dict()
            data["doc_id"] = doc.id
            recs.append(data)
    return recs


def update_statuses_from_sync(family_id: str, recs: list[dict], agent_text: str) -> None:
    """Parse agent output and update recommendation statuses."""
    db = get_db()
    now = datetime.now(timezone.utc)

    # Parse agent results: - "Title" by Author | Status: <status> | Branch: <branch>
    parsed = {}
    for match in re.finditer(
        r'-\s+"([^"]+)"\s+by\s+([^|]+)\|\s*Status:\s*([^|]+)\|\s*Branch:\s*([^|\n]+)',
        agent_text,
    ):
        title = match.group(1).strip().lower()
        status_text = match.group(3).strip().lower()
        parsed[title] = status_text

    updated = 0
    for rec in recs:
        title_lower = rec["title"].lower()
        if title_lower not in parsed:
            continue
        new_status = map_sfpl_status(parsed[title_lower])
        if new_status and new_status != rec.get("status"):
            db.collection("families").document(family_id).collection(
                "recommendations"
            ).document(rec["doc_id"]).update({
                "status": new_status,
                "updated_at": now,
            })
            updated += 1
            print(f'  "{rec["title"]}": {rec.get("status")} → {new_status}')

    print(f"Updated {updated} recommendation statuses")


def build_task() -> str:
    return f"""\
You need to log into the San Francisco Public Library website and check the status of my holds.

## STEP 1 — Log in
Go to https://sfpl.org and log in:
- Click "Log In" in the top navigation
- Username/Barcode: {SFPL_USERNAME}
- Password/PIN: {SFPL_PASSWORD}
- After logging in, confirm you see your account.
  If login fails, report the error and call "done" immediately.

## STEP 2 — Check hold statuses
Navigate to your holds page (usually under "My Account" → "Holds" or similar).

For each book on hold, note:
- The book title
- The current status (e.g. "On hold", "In transit", "Ready for pickup", "Suspended", etc.)
- The pickup branch

## STEP 3 — Report results (this is the ONLY time you should call "done")
Call "done" with a report in EXACTLY this format, one line per book:

HOLD STATUSES:
- "Title" by Author | Status: <status> | Branch: <branch>
- "Title" by Author | Status: <status> | Branch: <branch>

Use these exact status values: "On hold", "In transit", "Ready for pickup", or whatever
the site shows. Do NOT call "done" until you have checked all holds.
"""


async def main():
    family = load_family()
    family_id = family.get("family_id", "leo")

    recs = load_active_holds(family_id)
    if not recs:
        print("No active holds to sync.")
        return

    print(f"Found {len(recs)} active holds to check:")
    for rec in recs:
        print(f'  - "{rec["title"]}" ({rec.get("status")})')

    task = build_task()

    browser = Browser()
    llm = ChatAnthropic(model="claude-sonnet-4-5-20250929")

    agent = Agent(task=task, llm=llm, browser=browser)
    result = await agent.run()

    agent_text = result.final_result()
    print(agent_text)
    update_statuses_from_sync(family_id, recs, agent_text)


if __name__ == "__main__":
    asyncio.run(main())
