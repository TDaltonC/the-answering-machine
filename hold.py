import asyncio
import os
from datetime import datetime, timezone

from browser_use import Agent, Browser
from browser_use.llm import ChatAnthropic
from dotenv import load_dotenv

from config import load_family
from firestore_client import get_db

load_dotenv()

SFPL_USERNAME = os.environ["SFPL_USERNAME"]
SFPL_PASSWORD = os.environ["SFPL_PASSWORD"]


def load_recommendations(family_id: str) -> list[dict]:
    """Load recommendations with status 'recommended' from Firestore."""
    db = get_db()
    docs = (
        db.collection("families")
        .document(family_id)
        .collection("recommendations")
        .where("status", "==", "recommended")
        .stream()
    )
    recs = []
    for doc in docs:
        data = doc.to_dict()
        data["doc_id"] = doc.id
        recs.append(data)
    return recs


def format_books_for_prompt(recs: list[dict]) -> str:
    """Format recommendation docs into text for the agent prompt."""
    lines = []
    for i, rec in enumerate(recs, 1):
        lines.append(f'{i}. "{rec["title"]}" by {rec["author"]}')
    return "\n".join(lines)


def update_statuses_after_hold(family_id: str, recs: list[dict]) -> None:
    """Update all recommendation docs to hold_placed after the agent runs."""
    db = get_db()
    now = datetime.now(timezone.utc)
    for rec in recs:
        db.collection("families").document(family_id).collection(
            "recommendations"
        ).document(rec["doc_id"]).update({
            "status": "hold_placed",
            "updated_at": now,
        })
    print(f"Updated {len(recs)} recommendations to hold_placed")


def build_task(books_text: str, preferred_branch: str) -> str:
    return f"""\
You need to log into the San Francisco Public Library website and place holds on books.

## STEP 1 — Log in
Go to https://sfpl.org and log in:
- Click "Log In" in the top navigation
- Username/Barcode: {SFPL_USERNAME}
- Password/PIN: {SFPL_PASSWORD}
- After logging in, confirm you see your account (e.g. your name or "My Account").
  If login fails, report the error and call "done" immediately.

## STEP 2 — Place holds on these books
{books_text}

For each book:
a) Search for the book title using the search bar.
b) Click into the correct book from the results.
c) Click the "Place a Hold" button (or similar).
d) If it asks you to choose a pickup location, select "{preferred_branch}" as the branch.
e) Confirm the hold was placed successfully.
f) Move on to the next book.

If a hold can't be placed (already on hold, not available, etc.), note the reason
and move on.

## STEP 3 — Report results (this is the ONLY time you should call "done")
After attempting all books, call "done" with a summary:

HOLD RESULTS:
1. "Title" — Hold placed successfully (pickup at BRANCH) / Failed: reason
2. "Title" — Hold placed successfully (pickup at BRANCH) / Failed: reason
3. "Title" — Hold placed successfully (pickup at BRANCH) / Failed: reason

Do NOT call "done" until you have attempted holds for all books.
"""


async def main():
    family = load_family()
    family_id = family.get("family_id", "leo")

    recs = load_recommendations(family_id)
    if not recs:
        print("No recommendations with status 'recommended' found. Nothing to hold.")
        return

    print(f"Found {len(recs)} recommendations to place holds for:")
    for rec in recs:
        print(f'  - "{rec["title"]}" by {rec["author"]}')

    books_text = format_books_for_prompt(recs)
    task = build_task(books_text, family["preferred_branch"])

    browser = Browser()
    llm = ChatAnthropic(model="claude-sonnet-4-5-20250929")

    agent = Agent(task=task, llm=llm, browser=browser)
    result = await agent.run()

    hold_results = result.final_result()
    print(hold_results)

    update_statuses_after_hold(family_id, recs)


if __name__ == "__main__":
    asyncio.run(main())
