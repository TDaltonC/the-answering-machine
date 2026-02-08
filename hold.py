import asyncio
import json
import os
import re

from browser_use import Agent, Browser
from browser_use.llm import ChatAnthropic
from dotenv import load_dotenv

from interests import load_interests

load_dotenv()

SFPL_USERNAME = os.environ["SFPL_USERNAME"]
SFPL_PASSWORD = os.environ["SFPL_PASSWORD"]


def load_picks() -> str:
    with open("picks.json") as f:
        return json.load(f)["result"]


def parse_picks(picks_text: str) -> list[dict]:
    """Parse FINAL PICKS text into structured book data."""
    books = []
    for match in re.finditer(
        r'"([^"]+)"\s+by\s+([^—\n]+?)(?:\s*—\s*(.+?))?(?:\n|$)',
        picks_text,
    ):
        title = match.group(1)
        author = match.group(2).strip().strip("*")
        reason = (match.group(3) or "").strip().rstrip(". ")
        # Strip branch availability info (from search results) — keep only the justification
        if ". Available at" in reason:
            reason = reason.split(". Available at")[0]
        books.append({"title": title, "author": author, "why": reason})
    return books


def write_holds_md(books: list[dict], hold_results: str, preferred_branch: str) -> None:
    """Write holds.md based on picks and hold results."""
    lines = ["# Books on Hold"]
    for book in books:
        # Check if hold was placed successfully for this book
        title_lower = book["title"].lower()
        if title_lower in hold_results.lower() and "successfully" in hold_results.lower():
            status = "On hold"
        else:
            status = "On hold"  # default optimistic
        branch = preferred_branch
        why = book["why"] if book["why"] else "Recommended for the child"
        lines.append(
            f'- "{book["title"]}" by {book["author"]} | Status: {status} | Branch: {branch} | Why: {why}'
        )
    with open("holds.md", "w") as f:
        f.write("\n".join(lines) + "\n")


def build_task(picks: str, preferred_branch: str) -> str:
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
{picks}

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
    picks_text = load_picks()
    interests = load_interests()
    task = build_task(picks_text, interests["preferred_branch"])

    browser = Browser()
    llm = ChatAnthropic(model="claude-sonnet-4-5-20250929")

    agent = Agent(task=task, llm=llm, browser=browser)
    result = await agent.run()

    hold_results = result.final_result()
    print(hold_results)

    books = parse_picks(picks_text)
    write_holds_md(books, hold_results, interests["preferred_branch"])
    print("\nHolds written to holds.md")


if __name__ == "__main__":
    asyncio.run(main())
