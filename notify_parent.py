import os

import requests
from dotenv import load_dotenv

from config import load_family
from firestore_client import get_db

load_dotenv()

CARTESIA_API_KEY = os.environ["CARTESIA_API_KEY"]
CARTESIA_AGENT_ID = os.environ["CARTESIA_AGENT_ID"]

CARTESIA_URL = "https://api.cartesia.ai/twilio/call/outbound"


def load_ready_books(family_id: str) -> list[dict]:
    """Load recommendations with status 'ready' from Firestore."""
    db = get_db()
    docs = (
        db.collection("families")
        .document(family_id)
        .collection("recommendations")
        .where("status", "==", "ready")
        .stream()
    )
    books = []
    for doc in docs:
        data = doc.to_dict()
        books.append({
            "title": data["title"],
            "author": data["author"],
            "branch": data.get("branch", ""),
            "why": data.get("why", ""),
        })
    return books


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


def write_to_firestore(phone_number: str, books_context: str) -> None:
    """Write book context to Firestore so the voice agent can read it."""
    from google.cloud import firestore as fs
    db = get_db()
    db.collection("pending_calls").document(phone_number).set({
        "books_context": books_context,
        "created_at": fs.SERVER_TIMESTAMP,
    })
    print(f"Book context written to Firestore: pending_calls/{phone_number}")


def trigger_call(books: list[dict], phone_number: str) -> None:
    """Write context to Firestore, then POST to Cartesia outbound call API."""
    books_context = format_books_context(books)

    write_to_firestore(phone_number, books_context)

    headers = {
        "X-API-Key": CARTESIA_API_KEY,
        "Cartesia-Version": "2025-04-16",
        "Content-Type": "application/json",
    }
    body = {
        "target_numbers": [phone_number],
        "agent_id": CARTESIA_AGENT_ID,
    }
    resp = requests.post(CARTESIA_URL, headers=headers, json=body)
    resp.raise_for_status()
    print(f"Call triggered successfully. Response: {resp.status_code}")
    print(resp.json())


def main():
    family = load_family()
    family_id = family.get("family_id", "leo")
    phone_number = family["phone_number"]

    books = load_ready_books(family_id)
    if not books:
        print("No books are ready for pickup. No call needed.")
        return

    print(f"Found {len(books)} book(s) ready for pickup:")
    for b in books:
        print(f'  - "{b["title"]}" by {b["author"]}')

    trigger_call(books, phone_number)


if __name__ == "__main__":
    main()
