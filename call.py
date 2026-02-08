import os
import re

import requests
from dotenv import load_dotenv

load_dotenv()

CARTESIA_API_KEY = os.environ["CARTESIA_API_KEY"]
CARTESIA_AGENT_ID = os.environ["CARTESIA_AGENT_ID"]
PHONE_NUMBER = os.environ["PHONE_NUMBER"]

CARTESIA_URL = "https://api.cartesia.ai/twilio/call/outbound"


def parse_holds_md() -> list[dict]:
    """Parse holds.md and return books that are ready for pickup."""
    try:
        with open("holds.md") as f:
            content = f.read()
    except FileNotFoundError:
        return []

    ready = []
    for match in re.finditer(
        r'-\s+"([^"]+)"\s+by\s+([^|]+)\|\s*Status:\s*([^|]+)\|\s*Branch:\s*([^|]+)\|\s*Why:\s*(.+)',
        content,
    ):
        title = match.group(1).strip()
        author = match.group(2).strip()
        status = match.group(3).strip()
        branch = match.group(4).strip()
        why = match.group(5).strip()

        if status.lower() == "ready for pickup":
            ready.append({
                "title": title,
                "author": author,
                "branch": branch,
                "why": why,
            })
    return ready


def format_books_context(books: list[dict]) -> str:
    """Format books into a readable string for the voice agent."""
    lines = []
    for i, b in enumerate(books, 1):
        lines.append(f'{i}. "{b["title"]}" by {b["author"]} — {b["why"]}')
    branch = books[0]["branch"]
    return (
        f"Books ready for pickup at {branch}:\n"
        + "\n".join(lines)
    )


def trigger_call(books: list[dict]) -> None:
    """POST to Cartesia outbound call API with book metadata."""
    headers = {
        "X-API-Key": CARTESIA_API_KEY,
        "Cartesia-Version": "2025-04-16",
        "Content-Type": "application/json",
    }
    books_context = format_books_context(books)
    body = {
        "target_numbers": [PHONE_NUMBER],
        "agent_id": CARTESIA_AGENT_ID,
        "metadata": {
            "books_context": books_context,
        },
    }
    print(f"\nMetadata books_context:\n{books_context}\n")
    resp = requests.post(CARTESIA_URL, headers=headers, json=body)
    resp.raise_for_status()
    print(f"Call triggered successfully. Response: {resp.status_code}")
    print(resp.json())


def main():
    books = parse_holds_md()
    if not books:
        print("No books are ready for pickup. No call needed.")
        return

    print(f"Found {len(books)} book(s) ready for pickup:")
    for b in books:
        print(f'  - "{b["title"]}" by {b["author"]} at {b["branch"]}')

    trigger_call(books)


if __name__ == "__main__":
    main()
